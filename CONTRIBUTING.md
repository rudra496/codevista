# Contributing to CodeVista

Thank you for your interest in contributing! This guide covers how to get started.

## Quick Start

```bash
# Clone and install
git clone <repo-url> codevista
cd codevista
pip install -e .

# Run analysis
codevista analyze /path/to/project -o report.html
```

## Development Setup

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
make test

# Run with verbose output
make test-v
```

## Project Structure

```
codevista/
├── codevista/
│   ├── __init__.py      # Package metadata
│   ├── cli.py           # Command-line interface
│   ├── config.py        # Configuration & ignore patterns
│   ├── languages.py     # 90+ language definitions
│   ├── analyzer.py      # Core analysis engine
│   ├── security.py      # Security scanner (40+ patterns)
│   ├── report.py        # HTML report generator
│   ├── git_analysis.py  # Git history analysis
│   ├── dependencies.py  # Dependency parsing (10+ formats)
│   ├── metrics.py       # Code metrics & health scoring
│   ├── tech_detector.py # Framework/library detection
│   └── utils.py         # Shared utilities
├── tests/
│   ├── test_analyzer.py
│   ├── test_security.py
│   ├── test_metrics.py
│   ├── test_report.py
│   └── test_utils.py
├── Makefile
├── pyproject.toml
└── CONTRIBUTING.md
```

## Coding Standards

- **Zero external dependencies** — CodeVista must work with only the Python standard library
- **Type hints** — All public functions should have type annotations
- **Docstrings** — All modules and public functions need docstrings
- **Line length** — Max 88 characters (Black default)
- **Testing** — All new features need tests

## Adding a New Language

1. Add extension mapping in `languages.py` → `LANG_MAP`
2. Add GitHub color in `LANG_COLORS`
3. Add comment syntax in `COMMENT_SYNTAX`
4. Add import patterns in `utils.py` → `extract_imports()`
5. Add function pattern in `utils.py` → `detect_functions()`
6. Add tests in `tests/test_analyzer.py`

## Adding Security Patterns

1. Add regex pattern tuple to `SECRET_PATTERNS` or `DANGEROUS_PATTERNS` in `security.py`
2. Add remediation text in `_get_remediation()`
3. Add test in `tests/test_security.py`

## Reporting Issues

Please include:
- CodeVista version (`codevista --version`)
- Python version
- Sample code that triggers the issue
- Expected vs actual behavior

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/name`)
3. Write tests for your changes
4. Run `make test` and `make lint` to verify
5. Open a pull request with a clear description

## License

MIT License — see [LICENSE](LICENSE) for details.
