VENV := backend/.venv

.PHONY: install dev backend frontend test

install:
	python3 -m venv $(VENV) && $(VENV)/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && BACKEND_URL=http://localhost:8000 npm run dev

# Runs both services; Ctrl-C stops both.
dev:
	$(MAKE) -j2 backend frontend

test:
	cd backend && .venv/bin/python -m pytest -q
