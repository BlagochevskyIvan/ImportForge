PYTHON ?= python3
VENV := .venv/bin

.PHONY: help install env db-up db-stop keys migrate migration-check run lint format test test-unit test-db-up test-db-stop

help:
	@printf '%s\n' 'make install       Create .venv and install development dependencies' 'make env           Create .env from .env.example only if absent' 'make db-up         Start development PostgreSQL' 'make keys          Generate local JWT keys without overwriting existing keys' 'make migrate       Apply migrations to DATABASE_URL' 'make migration-check  Compare models with the database schema' 'make run           Run FastAPI with reload' 'make lint          Check Ruff rules and formatting' 'make format        Apply Ruff formatting' 'make test-unit     Run tests that do not need PostgreSQL' 'make test-db-up    Start isolated PostgreSQL for tests' 'make test          Run all tests (test database must be running)'

install:
	$(PYTHON) -m venv .venv
	$(VENV)/python -m pip install -r requirements.txt

env:
	$(PYTHON) -c 'from pathlib import Path; p = Path(".env"); print(".env already exists; kept unchanged") if p.exists() else p.write_text(Path(".env.example").read_text())'

db-up:
	docker compose up -d --wait postgres

db-stop:
	docker compose stop postgres

keys:
	$(VENV)/python -m scripts.generate_keys

migrate:
	$(VENV)/python -m alembic upgrade head

migration-check:
	$(VENV)/python -m alembic check

run:
	$(VENV)/python -m uvicorn src.main:app --reload

lint:
	$(VENV)/ruff check .
	$(VENV)/ruff format --check .

format:
	$(VENV)/ruff format .

test-unit:
	$(VENV)/python -m pytest -m 'not integration'

test-db-up:
	docker compose --profile test up -d --wait postgres_test

test-db-stop:
	docker compose --profile test stop postgres_test

test:
	$(VENV)/python -m pytest
