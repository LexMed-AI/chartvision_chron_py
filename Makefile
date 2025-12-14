.PHONY: install run ui test clean help

# Default target
help:
	@echo "ChartVision Chronology Engine"
	@echo ""
	@echo "Usage:"
	@echo "  make install    Install dependencies"
	@echo "  make run        Start API server (port 8811)"
	@echo "  make ui         Start UI server (port 8812)"
	@echo "  make test       Run all tests"
	@echo "  make clean      Remove cache files"
	@echo ""
	@echo "Quick start:"
	@echo "  make install && make run"
	@echo "  (in another terminal: make ui)"

# Install dependencies
install:
	pip install -r requirements.txt

# Start API server
run:
	PYTHONPATH=. python -m uvicorn app.api.ere_api:create_app --factory --host 0.0.0.0 --port 8811

# Start UI server
ui:
	cd app/ui && python -m http.server 8812

# Run tests
test:
	PYTHONPATH=. pytest tests/ -v

# Run tests with coverage
test-cov:
	PYTHONPATH=. pytest tests/ -v --cov=app --cov-report=term-missing

# Clean cache files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
