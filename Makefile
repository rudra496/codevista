.PHONY: install test test-v lint clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install package in development mode
	pip install -e .

test: ## Run tests
	python -m pytest tests/ -q

test-v: ## Run tests with verbose output
	python -m pytest tests/ -v

test-cov: ## Run tests with coverage
	python -m pytest tests/ -v --tb=short

lint: ## Lint with flake8 (if available)
	python -m flake8 codevista/ tests/ --max-line-length=88 || true

clean: ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .eggs/ codevista-report.html

demo: ## Run demo analysis on this project
	codevista analyze . -o /tmp/codevista-demo.html

quick: ## Quick analysis demo
	codevista quick . -o /tmp/codevista-quick.html

compare: ## Compare two directories (usage: make compare DIR1=../project1 DIR2=../project2)
	codevista compare $(DIR1) $(DIR2) -o /tmp/codevista-compare.html
