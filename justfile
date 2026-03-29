default:
    @just --list

test:
    pytest src/tests -v -s --cov=nixsearch --cov-report=term-missing

run:
    PYTHONPATH=src python -c "from nixsearch.app import main; main()"

lint:
    ruff check --fix src
    ruff format src

ci-lint:
    ruff check src
    ruff format --check src

