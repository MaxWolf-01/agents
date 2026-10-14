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
	@PYTHONDONTWRITEBYTECODE=1 uv run --quiet --with pytest pytest -q -p no:cacheprovider --tb=short mx/test_launches.py
	@echo "manifests parse, hooks point at executables, bin/ answers --help, every claude launch names what it inherits"

# One test process per core; JOBS=1 runs them one after another.
JOBS ?= auto
# What `make test` measures the change from: the merge-base of this tree with BASE.
BASE ?= master
PYTEST = PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-xdist --with hypothesis --with libcst --with tyro --with mutmut~=3.8.0 --with coverage --with pyyaml --with markdown --with markdown-it-py pytest -p no:cacheprovider -n $(JOBS)

EXTENSION := hypervisor/extension

# The test files this tree's changes since BASE reach (tools/affected_tests.py says how).
test:
	@tests=$$(BASE=$(BASE) uv run --quiet tools/affected_tests.py) || exit 1; \
	py=$$(echo "$$tests" | grep '\.py$$'); ts=$$(echo "$$tests" | grep '\.ts$$'); \
	if [ -z "$$tests" ]; then echo "no test reaches what changed since $(BASE); make test-all runs every one"; \
	else echo "+ $$(echo $$tests | wc -w) test files reached from $(BASE)"; \
	{ [ -z "$$py" ] || $(PYTEST) $$py; } && { [ -z "$$ts" ] || { $(MAKE) -s $(EXTENSION)/node_modules && node --test $$ts; }; }; fi

test-all: $(EXTENSION)/node_modules
	$(PYTEST) mx/
	node --test "$(EXTENSION)/tests/**/*.test.ts"

# Checks that drive real tmux; they run on a host that has it, not in the fast suite.
test-full-path: $(EXTENSION)/node_modules
	node --test "$(EXTENSION)/tests/full-path/*.full.ts"

$(EXTENSION)/node_modules: $(EXTENSION)/package-lock.json
	cd $(EXTENSION) && npm ci --no-audit --no-fund
	@touch $@

version:
	@jq -r .version $(PLUGIN)

release-patch: PART = patch
release-minor: PART = minor
release-major: PART = major

release-patch release-minor release-major: check test-all
	@V=$$(jq -r .version $(PLUGIN)); \
	NEW=$$(echo $$V | awk -F. -v part=$(PART) '{ \
	  if (part == "major") { printf "%d.0.0", $$1+1 } \
	  else if (part == "minor") { printf "%d.%d.0", $$1, $$2+1 } \
	  else { printf "%d.%d.%d", $$1, $$2, $$3+1 } }'); \
	tmp=$$(mktemp); jq --arg v "$$NEW" '.version = $$v' $(PLUGIN) >$$tmp && mv $$tmp $(PLUGIN); \
	git commit -q -m "mx v$$NEW" -- $(PLUGIN); \
	echo "$$V -> $$NEW"
