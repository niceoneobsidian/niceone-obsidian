"""P2: provider abstraction plus local/cloud adapters."""
from __future__ import annotations
from typing import Protocol
import shutil,subprocess
class SecretProvider(Protocol):
    name:str
    def get(self,metadata,context)->str: ...
    def set(self,metadata,value,context)->None: ...
    def delete(self,metadata,context)->None: ...
class SecretBroker:
    def __init__(self,providers,policy=None,audit=None): self.providers=dict(providers); self.policy=policy; self.audit=audit
    def get(self,metadata,context):
        if self.policy: self.policy.authorize_secret(metadata,context)
        provider=self.providers.get(metadata.provider)
        if not provider: raise KeyError(f"provider not configured: {metadata.provider}")
        value=provider.get(metadata,context)
        if self.audit: self.audit.record("secret.read",context.actor_id,metadata.id)
        return value
class LocalKeychainProvider:
    name="local-keychain"
    def _run(self,*args,input_value=None):
        binary="security" if shutil.which("security") else "secret-tool" if shutil.which("secret-tool") else None
        if not binary: raise RuntimeError("no supported OS keychain CLI")
        p=subprocess.run((binary,*args),input=input_value,text=True,capture_output=True,check=False)
        if p.returncode: raise RuntimeError(p.stderr.strip() or "keychain operation failed")
        return p.stdout.strip()
    def get(self,name,context=None):
        if shutil.which("security"): return self._run("find-generic-password","-a","ois","-s",name,"-w")
        return self._run("lookup","service","ois","attribute",name)
    def set(self,name,value,context=None):
        if shutil.which("security"): self._run("add-generic-password","-U","-a","ois","-s",name,"-w",value)
        else: self._run("store","--label",f"OIS:{name}","service","ois","attribute",name,input_value=value)
    def delete(self,name,context=None):
        if shutil.which("security"): self._run("delete-generic-password","-a","ois","-s",name)
        else: self._run("clear","service","ois","attribute",name)
class _ClientAdapter:
    def __init__(self,client=None): self.client=client
    def _need(self):
        if self.client is None: raise RuntimeError(f"configure {self.name} SDK/client")
class InfisicalProvider(_ClientAdapter):
    name="infisical"
    def get(self,m,c): self._need(); return str(self.client.get_secret(m.name))
    def set(self,m,v,c): self._need(); self.client.set_secret(m.name,v)
    def delete(self,m,c): self._need(); self.client.delete_secret(m.name)
class VaultProvider(_ClientAdapter):
    name="vault"
    def get(self,m,c): self._need(); return str(self.client.secrets.kv.v2.read_secret_version(path=m.reference)["data"]["data"]["value"])
    def set(self,m,v,c): self._need(); self.client.secrets.kv.v2.create_or_update_secret(path=m.reference,secret={"value":v})
    def delete(self,m,c): self._need(); self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=m.reference)
class AwsSecretsManagerProvider(_ClientAdapter):
    name="aws"
    def get(self,m,c): self._need(); return str(self.client.get_secret_value(SecretId=m.reference)["SecretString"])
    def set(self,m,v,c): self._need(); self.client.put_secret_value(SecretId=m.reference,SecretString=v)
    def delete(self,m,c): self._need(); self.client.delete_secret(SecretId=m.reference,RecoveryWindowInDays=7)
class AzureKeyVaultProvider(_ClientAdapter):
    name="azure"
    def get(self,m,c): self._need(); return str(self.client.get_secret(m.reference).value)
    def set(self,m,v,c): self._need(); self.client.set_secret(m.reference,v)
    def delete(self,m,c): self._need(); self.client.begin_delete_secret(m.reference)
class GcpSecretManagerProvider(_ClientAdapter):
    name="gcp"
    def get(self,m,c): self._need(); return self.client.access_secret_version(name=m.reference).payload.data.decode()
    def set(self,m,v,c): self._need(); self.client.add_secret_version(parent=m.reference,payload={"data":v.encode()})
    def delete(self,m,c): self._need(); self.client.delete_secret(name=m.reference)
