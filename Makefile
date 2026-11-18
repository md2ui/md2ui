# The one command. Agents and humans both run `make check`, and nothing else.
#
# What is in the gate is what is GREEN today. Steps are added as the debt they
# would report is brought under a ratchet -- never as a permanently-red step,
# because a gate that is always red teaches everyone to ignore it.
#
#   check_conventions.py  ratcheted counts: ruff lint, ruff format, pyright
#   run_tests.py          all tests/*_tests.py, judged against tests/BASELINE.txt
#   lint-imports          the architecture contracts in pyproject.toml
#   check_file_budgets    the per-file line ceilings in budgets.txt
#   check_skill_pointers  every pointer in skills/ names a topic `guide` serves
#   fetch_assets --check  every font in assets/fonts.lock is here, byte for byte
#
# No font lives in the repository: `make assets` fetches the locked ones first.

.PHONY: assets assets-check check check-fast test conventions conventions-fast imports pointers fix format lint types baseline ratchets ratchets-lower

check: assets-check test imports pointers conventions
	@echo "\nmake check: OK"

# The inner loop. Skips type checking, which dominates the 30s runtime here.
# NOT the gate: if `check` is slow enough that people reach for this instead,
# that is the problem to fix -- a gate nobody runs protects nothing.
check-fast: assets-check test imports pointers conventions-fast
	@echo "\nmake check-fast: OK (types skipped -- run `make check` before you claim done)"

# The fonts the themes name, from assets/fonts.lock into assets/fonts/ (ignored).
assets:
	uv run python scripts/fetch_assets.py

assets-check:
	uv run python scripts/fetch_assets.py --check

test:
	uv run python scripts/run_tests.py

conventions:
	uv run python scripts/check_conventions.py

conventions-fast:
	uv run python scripts/check_conventions.py --fast

imports:
	uv run lint-imports

pointers:
	uv run python scripts/check_skill_pointers.py

# Auto-fixable subset, for convenience. `check` is still the gate.
# Note: ruff_unformatted_files is locked at 0. If `make format` ever rewrites a
# file, that is a change to review, not a chore to commit alongside other work.
fix:
	uv run ruff check --fix src tests scripts

format:
	uv run ruff format src tests scripts

# Informational: the full detail behind the ratcheted counts.
lint:
	uv run ruff check src tests scripts

types:
	uv run pyright

# Regenerating a ceiling or a baseline ACCEPTS the current state. Human call.
baseline:
	uv run python scripts/run_tests.py --write-baseline

# Records an improvement. Safe at any time: it can only move a ceiling DOWN.
# This is the answer when `check` says "Improved -- lower the ceiling".
ratchets-lower:
	uv run python scripts/check_conventions.py --lower-ratchets

# ACCEPTS the current state wholesale, including regressions. Human call.
ratchets:
	uv run python scripts/check_conventions.py --write-ratchets
