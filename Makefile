# Alias tipis atas pipenv. Sumber kebenaran perintah = CLAUDE.md §Perintah.
# Di Windows tanpa `make`, jalankan `pipenv run …` langsung (lihat CLAUDE.md).

install:
	pipenv install --dev

test:
	pipenv run pytest

test-hpp:
	pipenv run pytest tests/test_hpp.py

migrate:
	pipenv run alembic upgrade head

seed:
	pipenv run python -m app.seeds.bu_sari

lint:
	pipenv run ruff check .
	pipenv run ruff format .

.PHONY: install test test-hpp migrate seed lint
