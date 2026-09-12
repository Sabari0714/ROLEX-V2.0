# ROLEX AI — quick commands
.PHONY: run hud test selftest clean

run:
	python run.py

hud:
	python -m rolex.ui.bridge


test:
	python -m pytest tests/ -v || python tests/run_all.py

selftest:
	python run.py --self-test

clean:
	rm -rf data __pycache__ rolex/__pycache__ rolex/**/__pycache__
