.PHONY: infra-up infra-down test integration verify-all clean

export OIS_DATABASE_URL ?= postgresql://ois_admin:ois_local_only@localhost:5432/ois_kernel_db
export OIS_REDIS_URL ?= redis://localhost:6379/0

infra-up:
	docker compose -f infra/docker-compose.yml up -d --wait

infra-down:
	docker compose -f infra/docker-compose.yml down

# Fast deterministic tests; does not require Docker services.
test:
	python -m pytest -q tests/unit tests/integration -m 'not runtime'

# Real PostgreSQL + Redis conformance. The integration test is skipped when URLs are absent.
integration: infra-up
	python -m pytest -q tests/integration/test_persistence_coordination.py

verify-all: infra-up
	python -m pytest -q tests/integration/test_persistence_coordination.py

clean: infra-down
	docker compose -f infra/docker-compose.yml down -v
