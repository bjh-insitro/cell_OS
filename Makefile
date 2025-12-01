.PHONY: lint bootstrap-data

lint:
	python3 -m pytest tests/static/test_code_analysis.py

bootstrap-data:
	python3 scripts/bootstrap_data.py
