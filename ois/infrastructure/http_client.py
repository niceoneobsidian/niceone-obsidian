"""Central outbound HTTP fabric for OIS integrations."""
from __future__ import annotations
import time, urllib.error, urllib.request
from dataclasses import dataclass
from threading import Lock
from typing import Mapping
RETRYABLE_STATUS=frozenset({408,425,429,500,502,503,504})
class HttpClientError(RuntimeError): pass
class CircuitOpenError(HttpClientError): pass
@dataclass(frozen=True)
class HttpResponse:
    status:int
    headers:Mapping[str,str]
    body:bytes
class CircuitBreaker:
    def __init__(self,failure_threshold:int=5,reset_timeout_s:float=30.0)->None:
        self.failure_threshold,self.reset_timeout_s=failure_threshold,reset_timeout_s
        self._failures=0; self._opened_at:float|None=None; self._lock=Lock()
    def before_request(self)->None:
        with self._lock:
            if self._opened_at is None:return
            if time.monotonic()-self._opened_at>=self.reset_timeout_s:self._opened_at=None;self._failures=0;return
            raise CircuitOpenError("OIS HTTP circuit breaker is open")
    def success(self)->None:
        with self._lock:self._failures=0;self._opened_at=None
    def failure(self)->None:
        with self._lock:
            self._failures+=1
            if self._failures>=self.failure_threshold:self._opened_at=time.monotonic()
class HttpClient:
    def __init__(self,*,timeout_s:float=30.0,max_retries:int=3,retry_enabled:bool=True,backoff_base_s:float=.25,backoff_max_s:float=10.0,circuit_breaker:CircuitBreaker|None=None)->None:
        self.timeout_s,self.max_retries,self.retry_enabled=timeout_s,max_retries,retry_enabled
        self.backoff_base_s,self.backoff_max_s,self.circuit_breaker=backoff_base_s,backoff_max_s,circuit_breaker
    def request(self,url:str,*,method:str="GET",headers:Mapping[str,str]|None=None,body:bytes|None=None)->HttpResponse:
        method=method.upper(); retryable_method=method in {"GET","HEAD","OPTIONS","PUT","DELETE"}
        attempts=self.max_retries+1 if self.retry_enabled and retryable_method else 1
        for attempt in range(attempts):
            if self.circuit_breaker:self.circuit_breaker.before_request()
            try:
                req=urllib.request.Request(url,data=body,headers=dict(headers or {}),method=method)
                with urllib.request.urlopen(req,timeout=self.timeout_s) as response:
                    result=HttpResponse(response.status,dict(response.headers.items()),response.read())
                if self.circuit_breaker:self.circuit_breaker.success()
                return result
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRYABLE_STATUS or attempt>=attempts-1:
                    if self.circuit_breaker:self.circuit_breaker.failure()
                    raise HttpClientError(f"HTTP {exc.code} from {url}") from exc
            except (urllib.error.URLError,TimeoutError,OSError) as exc:
                if attempt>=attempts-1:
                    if self.circuit_breaker:self.circuit_breaker.failure()
                    raise HttpClientError(f"HTTP transport failure for {url}: {exc}") from exc
            time.sleep(min(self.backoff_base_s*(2**attempt),self.backoff_max_s))
        raise HttpClientError("HTTP request failed")
