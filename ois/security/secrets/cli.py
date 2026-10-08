"""P0/P3 operator surface. Secret values are never printed."""
from __future__ import annotations
import argparse,json,os
from pathlib import Path
from .scanner import SecretScanner
def main(argv=None):
    p=argparse.ArgumentParser(prog="ois secrets"); s=p.add_subparsers(dest="command",required=True)
    q=s.add_parser("scan"); q.add_argument("path",nargs="?",default="."); q.add_argument("--json",action="store_true")
    d=s.add_parser("doctor"); d.add_argument("--json",action="store_true")
    r=s.add_parser("run"); r.add_argument("--secret",action="append",default=[]); r.add_argument("command",nargs=argparse.REMAINDER)
    a=p.parse_args(argv)
    if a.command=="scan":
        findings=SecretScanner().scan_path(Path(a.path))
        data=[{"detector":x.detector,"path":x.path,"line":x.line,"fingerprint":x.fingerprint} for x in findings]
        print(json.dumps(data,indent=2) if a.json else "\n".join(f"{x['path']}:{x['line']} {x['detector']} [{x['fingerprint']}]" for x in data))
        return 1 if findings else 0
    if a.command=="run":
        from .runtime_cli import run_command
        command = list(a.command)
        if command and command[0] == "--": command = command[1:]
        return run_command(a.secret, command)
    if a.command=="doctor":
        data={"environment":os.getenv("OIS_ENV","development"),"secret_files_allowed":False,"raw_secret_logging":False}
        print(json.dumps(data,indent=2) if a.json else data); return 0
    raise SystemExit("secrets run requires configured SecretRuntime, broker and policy")
