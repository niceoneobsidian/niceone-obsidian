"""P0 repository scanner; intended to run before commit and in CI."""
from __future__ import annotations
import hashlib,re
from dataclasses import dataclass
from pathlib import Path
PATTERNS=(
("private-key",re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
("aws-access-key",re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
("github-token",re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
("stripe-secret",re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")),
("google-api-key",re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
("ois-api-key",re.compile(r"\bodk_(?:deve|test|stag|prod)_[A-Za-z0-9_-]{32,}\b")))
@dataclass(frozen=True,slots=True)
class Finding: detector:str; path:str; line:int; fingerprint:str
class SecretScanner:
    def scan_text(self,text,path="<memory>"):
        out=[]
        for n,line in enumerate(text.splitlines(),1):
            for detector,pattern in PATTERNS:
                for match in pattern.finditer(line): out.append(Finding(detector,path,n,hashlib.sha256(match.group().encode()).hexdigest()[:16]))
        return out
    def scan_path(self,root:Path):
        out=[]; ignored={".git",".venv","node_modules","__pycache__"}
        for path in root.rglob("*"):
            if path.is_file() and not any(p in ignored for p in path.parts):
                try: out.extend(self.scan_text(path.read_text(encoding="utf-8"),path.relative_to(root).as_posix()))
                except (OSError,UnicodeDecodeError): pass
        return out
