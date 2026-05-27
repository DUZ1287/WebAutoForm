# Contributing

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/web-auto-form.git`
3. Install development dependencies: `make dev`
4. Create a branch: `git checkout -b feature/my-feature`

## Development Workflow

```bash
make test      # run all tests
make lint      # flake8 + mypy
make format    # black + isort
```

## Code Style

- **PEP 8** with 100-character line length (enforced by Black)
- **Type hints** on all public functions (checked by mypy)
- **Docstrings** on all public modules, classes, and functions
- **Tests** required for all new features and bug fixes

## Pull Request Process

1. Ensure all tests pass: `make test`
2. Ensure linting passes: `make lint`
3. Update documentation if needed
4. Submit your PR with a clear description

## Reporting Issues

Use GitHub Issues. Include:
- Python version
- Playwright version
- Minimal reproduction steps
- Expected vs actual behavior
