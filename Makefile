.PHONY: lint test install format clean all

install:
	uv pip install --system ruff mypy pytest pytest-asyncio pytest-cov homeassistant aiohttp pytest-homeassistant-custom-component

lint:
	ruff check --fix .
	ruff format .
	mypy custom_components/trading212

format:
	ruff format .

test:
	pytest --cov=custom_components.trading212 --cov-report=xml

clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f coverage.xml
	rm -f .coverage

all: install lint test
