"""CI gate for the OIS environment contract and secret hygiene."""
from __future__ import annotations
import os
import re
from pathlib import Path
from ois.config.settings import validate_startup

SECRET_NAME=re.compile(r"(^|_)(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)(_|$)",re.I)

def check_example() -> list[str]:
    errors=[]
    path=Path(".env.example")
    for line_no,line in enumerate(path.read_text().splitlines(),1):
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key,value=line.split("=",1)
        if SECRET_NAME.search(key) and value.strip():
            errors.append(f".env.example:{line_no}: secret-like variable must be empty")
    return errors

def main()->int:
    errors=check_example()
    try: validate_startup(os.environ)
    except Exception as exc: errors.append(f"configuration: {exc}")
    if errors:
        for error in errors: print(f"FAIL {error}")
        return 1
    print("PASS OIS environment contract")
    return 0

if __name__=="__main__": raise SystemExit(main())
