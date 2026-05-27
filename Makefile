.PHONY: install backend frontend dev test eval clean docker

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install --legacy-peer-deps

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Run 'make backend' and 'make frontend' in separate terminals."

test:
	cd backend && pytest

eval:
	cd backend && python -m eval.runner

docker:
	docker compose up --build

clean:
	rm -rf backend/.pytest_cache backend/**/__pycache__ backend/claims.db
	rm -rf frontend/.next frontend/node_modules
