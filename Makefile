VENV := backend/.venv

.PHONY: install dev backend worker frontend test

install:
	python3 -m venv $(VENV) && $(VENV)/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --timeout-graceful-shutdown 5 --port 8000

# Runs the queued jobs (each in a fresh process, so it always runs the current code).
worker:
	cd backend && .venv/bin/python -m app.worker

frontend:
	cd frontend && BACKEND_URL=http://localhost:8000 npm run dev

# Runs the API, the worker and the frontend; Ctrl-C stops all three.
dev:
	$(MAKE) -j3 backend worker frontend

# Backend (pytest) then frontend API routes (vitest).
test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm test
