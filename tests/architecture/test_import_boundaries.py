import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]


def imports(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_application_does_not_import_infrastructure():
    application = ROOT / "ois" / "application"
    forbidden = ("psycopg", "redis", "boto3")
    for path in application.rglob("*.py"):
        assert not any(name.startswith(forbidden) for name in imports(path)), path
