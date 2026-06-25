# DocuMind - Makefile
# Run commands with: make <command>
# e.g. make up, make down, make logs

.PHONY: up down build logs shell db-shell test clean

# ── Docker ─────────────────────────────────────
up:
	docker-compose up

up-d:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose up --build

rebuild:
	docker-compose down && docker-compose up --build

# ── Logs ───────────────────────────────────────
logs:
	docker-compose logs -f app

logs-db:
	docker-compose logs -f db

logs-all:
	docker-compose logs -f

# ── Shell access ───────────────────────────────
shell:
	docker-compose exec app bash

db-shell:
	docker-compose exec db psql -U postgres -d documind

redis-shell:
	docker-compose exec redis redis-cli

# ── Tests ──────────────────────────────────────
test:
	docker-compose exec app pytest tests/ -v

# ── Cleanup ────────────────────────────────────
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
