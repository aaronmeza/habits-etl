.PHONY: venv install db-setup etl test
VENV?=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
export PYTHONPATH:=.

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

db-setup:
	psql "$$PG_DSN" -f sql/001_schema.sql

etl:
	$(PY) etl/etl_habits.py

test:
	$(VENV)/bin/pytest -q
