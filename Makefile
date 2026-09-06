.PHONY: infra-up infra-down test integration verify-all clean

export OIS_DATABASE_URL ?= postgresql://ois_admin:ois_local_only@localhost:5432/ois_kernel_db
export OIS_REDIS_URL ?= redis://localhost:6379/0

infra-up:
	docker compose -f infra/docker-compose.yml up -d --wait

infra-down:
	docker compose -f infra/docker-compose.yml down

# Fast deterministic repository tests; Docker services are not required.
test:
	python -m pytest -q

# Real PostgreSQL + Redis conformance lifecycle.
integration: infra-up
	python -m pytest -q tests/integration/test_persistence_coordination.py

verify-all: infra-up
	python -m pytest -q

clean:
	docker compose -f infra/docker-compose.yml down -v
