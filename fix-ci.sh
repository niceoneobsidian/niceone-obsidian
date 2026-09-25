#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from pathlib import Path

path = Path("pyproject.toml")
text = path.read_text()

duplicate = '''[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true

'''

if duplicate in text:
    text = text.replace(duplicate, "", 1)
    path.write_text(text)
    print("Removed duplicate [tool.mypy] section")
else:
    print("Duplicate [tool.mypy] section not found")
PY

python - <<'PY'
from pathlib import Path

path = Path("ois/domains/social_intelligence/production_slice.py")
text = path.read_text()

if "import json" not in text:
    text = text.replace("import hashlib\n", "import hashlib\nimport json\n")

old = """def observation_key(post: SocialPost) -> str:
    payload = post.model_dump_json(sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
"""

new = """def observation_key(post: SocialPost) -> str:
    payload = json.dumps(
        post.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
"""

if old in text:
    path.write_text(text.replace(old, new))
    print("Fixed observation_key")
else:
    print("observation_key already fixed or source differs")
PY

python - <<'PY'
import tomllib
from pathlib import Path

with Path("pyproject.toml").open("rb") as file:
    tomllib.load(file)

print("pyproject.toml parses successfully")
PY

ruff check ois scripts tests test_p0_integrated_spine.py --fix
ruff format ois scripts tests test_p0_integrated_spine.py
ruff check ois scripts tests test_p0_integrated_spine.py
ruff format --check ois scripts tests test_p0_integrated_spine.py
python -m mypy ois ops production
python -m pytest -q
