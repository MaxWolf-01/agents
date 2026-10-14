PLUGIN := mx/.claude-plugin/plugin.json
MARKETPLACE := .claude-plugin/marketplace.json
HOOKS := mx/hooks/hooks.json
# Each release puts its section on top: its version, then the subjects of the commits on master's first-parent line
# since the previous release that change something under mx/. A session moved to a newer mx reads the sections it
# skipped (mx/hooks/plugin_updates.py).
CHANGELOG := mx/CHANGELOG.md

.PHONY: check test test-all test-full-path version release-patch release-minor release-major

check:
	@jq -e . $(PLUGIN) >/dev/null
	@jq -e . $(MARKETPLACE) >/dev/null
	@jq -e . $(HOOKS) >/dev/null
	@jq -r '.hooks[][].hooks[].command' $(HOOKS) | tr -d '"' | sed 's|$${CLAUDE_PLUGIN_ROOT}|mx|' | cut -d' ' -f1 | \
	  while read -r c; do [ -x "$$c" ] || { echo "$(HOOKS): $$c is not an executable file"; exit 1; }; done
	@for f in mx/bin/*; do $$f --help >/dev/null || { echo "$$f --help failed"; exit 1; }; done
	@uvx --quiet ruff@0.17.0 check --quiet --select F811 mx/
	@[ ! -f $(CHANGELOG) ] || [ "$$(sed -n 's/^## //p' $(CHANGELOG) | head -1)" = "$$(jq -r .version $(PLUGIN))" ] || \
	  { echo "$(CHANGELOG): its top section is not $(PLUGIN)'s version, which the release that wrote both left equal"; exit 1; }
	@PYTHONDONTWRITEBYTECODE=1 uv run --quiet --with pytest --with pyyaml pytest -q -p no:cacheprovider --tb=short mx/test_launches.py mx/test_skill_injections.py mx/test_module_names.py
	@echo "manifests parse, hooks point at executables, bin/ answers --help, every claude launch names what it inherits, every skill approves its own ! lines, no two scripts under mx share a name and no check imports another, no file under mx defines one name twice"

# One test process per core; JOBS=1 runs them one after another.
JOBS ?= auto
# What `make test` measures the change from: the merge-base of this tree with BASE.
BASE ?= master
UV_PYTEST = PYTHONDONTWRITEBYTECODE=1 uv run --quiet --with pytest --with pytest-xdist --with hypothesis --with tyro --with pyyaml --with markdown --with 'markdown-it-py[linkify]' pytest -p no:cacheprovider
PYTEST = $(UV_PYTEST) -n $(JOBS)
# The full-path checks test-full-path runs: every one, or those in the test files TESTS names on
# the command line. Never read from the environment, so an exported TESTS cannot narrow a release.
TESTS = mx/ $(EXTENSION_FULL_PATH)

EXTENSION := hypervisor/extension
# The hypervisor extension's full-path checks, which drive real tmux and a real pi TUI.
EXTENSION_FULL_PATH := $(wildcard $(EXTENSION)/tests/full-path/*.full.ts)

# The test files this tree's changes since BASE reach (tools/affected_tests.py says how), less
# their full-path checks. The recipe then prints the test-full-path command that runs those.
# pytest exits 5 when it ran nothing: every test it collected was a full-path check.
test:
	@tests=$$(BASE=$(BASE) uv run --quiet tools/affected_tests.py) || exit 1; \
	if [ -z "$$tests" ]; then echo "no test reaches what changed since $(BASE); make test-all runs every one"; exit 0; fi; \
	echo "+ $$(echo $$tests | wc -w) test files reached from $(BASE)"; \
	py=$$(echo "$$tests" | grep '\.py$$'); ts=$$(echo "$$tests" | grep '\.ts$$'); full=; \
	if [ -n "$$py" ]; then \
	  $(PYTEST) -m 'not full_path' $$py || [ $$? -eq 5 ] || exit 1; \
	  full=$$($(UV_PYTEST) -q --co -m full_path $$py 2>/dev/null | sed -n 's/::.*//p' | sort -u); fi; \
	if [ -n "$$ts" ]; then \
	  $(MAKE) -s $(EXTENSION)/node_modules && node --test $$ts || exit 1; \
	  full="$$full $(EXTENSION_FULL_PATH)"; fi; \
	[ -z "$$(echo $$full)" ] || echo "+ full-path checks reached: make test-full-path TESTS=\"$$(echo $$full)\""

test-all: $(EXTENSION)/node_modules
	$(PYTEST) -m 'not full_path' mx/
	cd $(EXTENSION) && npm run -s typecheck
	node --test "$(EXTENSION)/tests/**/*.test.ts"

# A .ts file in TESTS is one of the extension's full-path checks, which node runs; the rest go to pytest.
test-full-path: $(EXTENSION)/node_modules
	@py=$$(printf '%s\n' $(TESTS) | grep -v '\.ts$$'); ts=$$(printf '%s\n' $(TESTS) | grep '\.ts$$'); \
	{ [ -z "$$py" ] || $(PYTEST) -m full_path $$py; } && { [ -z "$$ts" ] || node --test $$ts; }

$(EXTENSION)/node_modules: $(EXTENSION)/package-lock.json
	cd $(EXTENSION) && npm ci --no-audit --no-fund
	@touch $@

version:
	@jq -r .version $(PLUGIN)

release-patch: PART = patch
release-minor: PART = minor
release-major: PART = major

release-patch release-minor release-major: check test-all test-full-path
	@set -e; V=$$(jq -r .version $(PLUGIN)); \
	NEW=$$(echo $$V | awk -F. -v part=$(PART) '{ \
	  if (part == "major") { printf "%d.0.0", $$1+1 } \
	  else if (part == "minor") { printf "%d.%d.0", $$1, $$2+1 } \
	  else { printf "%d.%d.%d", $$1, $$2, $$3+1 } }'); \
	tmp=$$(mktemp); jq --arg v "$$NEW" '.version = $$v' $(PLUGIN) >$$tmp && mv $$tmp $(PLUGIN); \
	last=$$(git log --first-parent --grep='^mx v[0-9]' --format=%H -1); \
	{ printf '## %s\n\n' "$$NEW"; git log --first-parent --format='- %s' $$last..HEAD -- mx/ | { grep -v '^- mx v[0-9]' || true; }; echo; \
	  [ ! -f $(CHANGELOG) ] || cat $(CHANGELOG); } >$$tmp; mv $$tmp $(CHANGELOG); \
	git add $(CHANGELOG); \
	git commit -q -m "mx v$$NEW" -- $(PLUGIN) $(CHANGELOG); \
	git tag -a "mx-v$$NEW" -m "mx v$$NEW"; \
	echo "$$V -> $$NEW"
