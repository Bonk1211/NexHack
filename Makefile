.PHONY: install run

install:
	cd backend && test -d .venv || uv venv
	cd backend && uv pip install -e '.[dev]'
	cd frontend && npm install

run:
	cd backend && uv run uvicorn app.main:app --reload & \
	cd frontend && npm run dev
