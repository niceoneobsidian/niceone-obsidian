from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from typing import Any, Dict, List, Optional, TypedDict

import redis.asyncio as redis
from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger('ois.production_kernel')
tracer = trace.get_tracer('ois.kernel.core')
meter = metrics.get_meter('ois.kernel.core')
recovery_counter = meter.create_counter('ois_recovery_events_total')

class KernelPanicException(Exception): pass
class FencingTokenMismatch(KernelPanicException): pass
class EvidenceVerificationFailure(KernelPanicException): pass

class WorkflowState(TypedDict, total=False):
    tenant_id: str
    thread_id: str
    workflow_version: str
    current_state: str
    execution_plan: List[str]
    proposed_side_effect: Dict[str, Any]
    side_effect_hash: str
    resolution: str
    fencing_token: int

class FencedLease:
    RELEASE = """if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"""
    def __init__(self, client: redis.Redis, key: str, ttl_ms: int = 15000):
        self.client, self.key, self.ttl_ms = client, key, ttl_ms
        self.owner = secrets.token_hex(16)
        self.token: Optional[int] = None
    async def acquire(self) -> int:
        token = await self.client.incr(f'{self.key}:counter')
        value = f'{token}:{self.owner}'
        if not await self.client.set(self.key, value, px=self.ttl_ms, nx=True):
            raise KernelPanicException('Execution lease contention')
        self.token = token
        return token
    async def release(self) -> None:
        await self.client.eval(self.RELEASE, 1, self.key, f'{self.token}:{self.owner}')

class EvidenceLedger:
    def __init__(self, pool: AsyncConnectionPool, signing_key: bytes):
        self.pool, self.signing_key = pool, signing_key
    def sign(self, message: str) -> str:
        return hmac.new(self.signing_key, message.encode(), hashlib.sha256).hexdigest()
    async def append(self, tenant_id: str, thread_id: str, event_type: str, payload_hash: str, context: Dict[str, Any]) -> None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT set_config('app.current_tenant_id', %s, true)", (tenant_id,))
                await cur.execute("SELECT COALESCE(MAX(sequence_no),0), COALESCE((SELECT payload_hash FROM ois_attestation_evidence WHERE tenant_id=%s AND thread_id=%s ORDER BY sequence_no DESC LIMIT 1), repeat('0',64)) FROM ois_attestation_evidence WHERE tenant_id=%s AND thread_id=%s", (tenant_id,thread_id,tenant_id,thread_id))
                seq, previous_hash = await cur.fetchone()
                n = seq + 1
                sig = self.sign(f'{tenant_id}:{thread_id}:{n}:{event_type}:{payload_hash}:{previous_hash}')
                await cur.execute("INSERT INTO ois_attestation_evidence (tenant_id,thread_id,sequence_no,event_type,payload_hash,previous_hash,context_snapshot,attestation_signature) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (tenant_id,thread_id,n,event_type,payload_hash,previous_hash,json.dumps(context,sort_keys=True),sig))
                await conn.commit()

class OISProductionSupervisor:
    def __init__(self, db_pool: AsyncConnectionPool, redis_client: redis.Redis, signing_key: bytes):
        self.pool, self.redis, self.secret = db_pool, redis_client, signing_key
        self.evidence = EvidenceLedger(db_pool, signing_key)
    def _sign_hash(self, content: str) -> str:
        return hmac.new(self.secret, content.encode(), hashlib.sha256).hexdigest()
    async def verify_artifact_promotion_gate(self, tenant_id: str, workflow_name: str, version_tag: str) -> dict:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT set_config('app.current_tenant_id', %s, true)", (tenant_id,))
                await cur.execute("SELECT manifest_payload,provenance_hash,supervisor_promotion_signature FROM ois_artifact_registry WHERE tenant_id=%s AND workflow_name=%s AND version_tag=%s", (tenant_id,workflow_name,version_tag))
                record = await cur.fetchone()
        if not record: raise EvidenceVerificationFailure('Promotion denied: no signed artifact attestation')
        manifest, provenance_hash, signature = record
        expected = self._sign_hash(f'{tenant_id}:{workflow_name}:{version_tag}:{provenance_hash}')
        if not hmac.compare_digest(expected, signature): raise EvidenceVerificationFailure('Registry artifact signature mismatch')
        return manifest
    @staticmethod
    def classify_failure(exc: Exception) -> str:
        if isinstance(exc, FencingTokenMismatch): return 'RC-08'
        if isinstance(exc, EvidenceVerificationFailure): return 'RC-12'
        if isinstance(exc, TimeoutError): return 'RC-01'
        return 'RC-04'
    async def execute_supervisor_pipeline(self, tenant_id: str, thread_id: str, workflow_name: str, version: str, client_input: Dict[str,Any]) -> Dict[str,Any]:
        with tracer.start_as_current_span('supervisor_pipeline', attributes={'tenant_id':tenant_id,'thread_id':thread_id}) as span:
            lease = FencedLease(self.redis, f'lock:lease:execution:{tenant_id}:{thread_id}')
            state: WorkflowState = {'tenant_id':tenant_id,'thread_id':thread_id,'workflow_version':version,'current_state':'EXECUTION','execution_plan':[],'proposed_side_effect':{},'side_effect_hash':'','resolution':'PENDING'}
            try:
                manifest = await self.verify_artifact_promotion_gate(tenant_id, workflow_name, version)
                state['execution_plan'] = manifest.get('routing_dag',['evaluate_step','apply_step'])
                state['fencing_token'] = await lease.acquire()
                from langgraph.graph import END, START, StateGraph
                async def evaluate_step(s: WorkflowState) -> Dict[str,Any]:
                    payload = client_input.get('proposed_side_effect', {'action':'noop'})
                    digest = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    return {'current_state':'APPROVAL_REQUIRED','proposed_side_effect':payload,'side_effect_hash':digest}
                async def apply_step(s: WorkflowState) -> Dict[str,Any]:
                    if s.get('resolution') != 'APPROVED': return {'current_state':'ABORT'}
                    digest = hashlib.sha256(json.dumps(s['proposed_side_effect'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    if not hmac.compare_digest(digest,s['side_effect_hash']): raise FencingTokenMismatch('Side-effect hash changed after approval')
                    return {'current_state':'RESUME'}
                b = StateGraph(WorkflowState)
                b.add_node('evaluate_step',evaluate_step); b.add_node('apply_step',apply_step)
                b.add_edge(START,'evaluate_step'); b.add_edge('evaluate_step','apply_step'); b.add_edge('apply_step',END)
                kernel = b.compile(interrupt_before=['apply_step'])
                await kernel.ainvoke(state, config={'configurable':{'thread_id':thread_id}})
                await self.evidence.append(tenant_id,thread_id,'KERNEL_INTERRUPT_WAITING',state.get('side_effect_hash',''),{'status':'HALTED','fencing_token':state['fencing_token']})
                return {'status':'WAITING_FOR_HUMAN','thread_id':thread_id,'fencing_token':state['fencing_token']}
            except Exception as exc:
                span.record_exception(exc); span.set_status(Status(StatusCode.ERROR,str(exc)))
                await self.execute_12_case_recovery_matrix(tenant_id,thread_id,self.classify_failure(exc),str(exc),state)
                raise
            finally:
                await lease.release()
    async def execute_12_case_recovery_matrix(self, tenant_id: str, thread_id: str, scenario_id: str, diagnostic_log: str, state_dump: Dict[str,Any]) -> None:
        recovery_counter.add(1, {'scenario':scenario_id})
        serialized = json.dumps(state_dump,sort_keys=True,default=str)
        payload_hash = hashlib.sha256(f'{serialized}:{diagnostic_log}'.encode()).hexdigest()
        signature = self._sign_hash(f'{tenant_id}:{thread_id}:{scenario_id}:{payload_hash}')
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT set_config('app.current_tenant_id', %s, true)",(tenant_id,))
                await cur.execute("INSERT INTO ois_kernel_dead_letter_queue (tenant_id,thread_id,last_scenario_id,error_diagnostic_log,frozen_context_data,cryptographic_seal_signature) VALUES (%s,%s,%s,%s,%s,%s)",(tenant_id,thread_id,scenario_id,diagnostic_log,serialized,signature))
                await conn.commit()
