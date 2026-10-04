PLUGIN := mx/.claude-plugin/plugin.json
MARKETPLACE := .claude-plugin/marketplace.json
HOOKS := mx/hooks/hooks.json

.PHONY: check test test-all test-full-path version release-patch release-minor release-major

check:
	@jq -e . $(PLUGIN) >/dev/null
	@jq -e . $(MARKETPLACE) >/dev/null
	@jq -e . $(HOOKS) >/dev/null
	@jq -r '.hooks[][].hooks[].command' $(HOOKS) | tr -d '"' | sed 's|$${CLAUDE_PLUGIN_ROOT}|mx|' | cut -d' ' -f1 | \
	  while read -r c; do [ -x "$$c" ] || { echo "$(HOOKS): $$c is not an executable file"; exit 1; }; done
	@for f in mx/bin/*; do $$f --help >/dev/null || { echo "$$f --help failed"; exit 1; }; done
	@PYTHONDONTWRITEBYTECODE=1 uv run --quiet --with pytest --with pyyaml pytest -q -p no:cacheprovider --tb=short mx/test_launches.py mx/test_skill_injections.py
	@echo "manifests parse, hooks point at executables, bin/ answers --help, every claude launch names what it inherits, every skill approves its own ! lines"

# One test process per core; JOBS=1 runs them one after another.
JOBS ?= auto
# What `make test` measures the change from: the merge-base of this tree with BASE.
BASE ?= master
PYTEST = PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-xdist --with hypothesis --with tyro --with pyyaml --with markdown --with markdown-it-py pytest -p no:cacheprovider -n $(JOBS)
# The full-path checks: each starts a browser or drives tmux, so they run from test-full-path alone.
FULL_PATH = mx/skills/tracker/test_board_layout.py mx/skills/show/test_render_lint.py mx/skills/show/test_browsers.py \
  mx/skills/session-page/test_page_in_a_browser.py mx/skills/dispatch/test_dispatch.py mx/skills/dispatch/test_dispatch_ps.py

# The test files this tree's changes since BASE reach (tools/affected_tests.py says how).
test:
	@reached=$$(BASE=$(BASE) uv run --quiet tools/affected_tests.py) || exit 1; \
	tests=$$(printf '%s\n' $$reached | grep -vxF $(addprefix -e ,$(FULL_PATH))); \
	full=$$(printf '%s\n' $$reached | grep -xF $(addprefix -e ,$(FULL_PATH))); \
	[ -z "$$full" ] || echo "+ full-path checks reached, left to make test-full-path:" $$full; \
	if [ -z "$$tests" ]; then echo "no test reaches what changed since $(BASE); make test-all runs every one"; \
	else echo "+ $$(echo $$tests | wc -w) test files reached from $(BASE)"; $(PYTEST) $$tests; fi

test-all:
	$(PYTEST) mx/ $(addprefix --ignore=,$(FULL_PATH))

test-full-path:
	$(PYTEST) $(FULL_PATH)

version:
	@jq -r .version $(PLUGIN)

release-patch: PART = patch
release-minor: PART = minor
release-major: PART = major

release-patch release-minor release-major: check test-all test-full-path
	@V=$$(jq -r .version $(PLUGIN)); \
	NEW=$$(echo $$V | awk -F. -v part=$(PART) '{ \
	  if (part == "major") { printf "%d.0.0", $$1+1 } \
	  else if (part == "minor") { printf "%d.%d.0", $$1, $$2+1 } \
	  else { printf "%d.%d.%d", $$1, $$2, $$3+1 } }'); \
	tmp=$$(mktemp); jq --arg v "$$NEW" '.version = $$v' $(PLUGIN) >$$tmp && mv $$tmp $(PLUGIN); \
	git commit -q -m "mx v$$NEW" -- $(PLUGIN); \
	echo "$$V -> $$NEW"
