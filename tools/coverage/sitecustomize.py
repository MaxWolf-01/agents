# The scripts under mx run in environments `uv run --script` builds, which hold no coverage, so `make coverage` puts this
# directory and one holding coverage alone on PYTHONPATH and every Python it starts measures itself here.
import coverage

coverage.process_startup()
