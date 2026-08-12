.PHONY: dev backend frontend docker-up docker-down seed test

dev: docker-up

backend:
	uvicorn backend.app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

seed:
	python backend/seed.py

test:
	cd backend && pytest
