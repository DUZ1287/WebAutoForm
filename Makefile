.PHONY: install dev test lint format example clean demo playground

install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	playwright install chromium

test:
	python -m pytest -v

lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

example:
	web_auto_form run examples/job_application.json --debug

demo:
	python demo/demo_agent.py

playground:
	python playground/app.py

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	python -c "import shutil,pathlib;[shutil.rmtree(p,ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import pathlib;[p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
