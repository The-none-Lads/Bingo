.PHONY: help install install-dev test test-unit test-integration test-coverage lint format clean run backend frontend run-prod

help:
	@echo "Bingo Application - Available Commands:"
	@echo ""
	@echo "  make install          - Install production dependencies"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage    - Run tests with coverage report"
	@echo "  make lint             - Run linters (flake8, mypy)"
	@echo "  make format           - Format code (black, isort)"
	@echo "  make format-check     - Check code formatting without changes"
	@echo "  make clean            - Clean up generated files"
	@echo "  make run              - Run the backend server"
	@echo ""

install:
	pip install -r backend/requirements.txt

install-dev:
	pip install -r backend/requirements-dev.txt

test:
	cd backend && pytest tests/ -v

test-unit:
	cd backend && pytest tests/ -v -m unit

test-integration:
	cd backend && pytest tests/ -v -m integration

test-coverage:
	cd backend && pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in backend/htmlcov/index.html"

lint:
	-flake8 .
	-black --check .
	-isort --check-only .
	-mypy . --check-untyped-defs
	-cd frontend && npx eslint . --ext .js,.jsx,.ts,.tsx
	-cd frontend && npx stylelint "**/*.{css,scss}"
	-cd frontend && npx htmlhint "frontend/**/*.html"
	-yamllint . --config-file .yamllint

format:
	black .
	isort .

format-check:
	black --check backend/
	isort --check-only backend/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete

backend:
	cd backend && uvicorn app:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

run: backend frontend


run-prod:
	cd backend && uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4