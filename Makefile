.PHONY: dev test lint migrate

dev:
	docker compose up --build

down:
	docker compose down

test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && ruff check app/

migrate:
	cd backend && alembic upgrade head

revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"
