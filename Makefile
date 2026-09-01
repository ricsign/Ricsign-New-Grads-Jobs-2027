.PHONY: help install lint test refresh render validate clean

help:
	@echo "install   Install runtime + dev dependencies"
	@echo "lint      Run ruff"
	@echo "test      Run the test suite"
	@echo "refresh   Full pipeline: fetch -> classify -> render (hits the network)"
	@echo "render    Re-render boards from cached data (no network)"
	@echo "validate  Validate data/v1/jobs.json against the published schema"

install:
	python -m pip install -r requirements-dev.txt

lint:
	ruff check src tests
	ruff format --check src tests

test:
	pytest

refresh:
	python -m eliteboard.cli refresh

render:
	python -m eliteboard.cli render

validate:
	python -m eliteboard.cli validate

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__
