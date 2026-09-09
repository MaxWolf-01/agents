.PHONY: test harden fuzz check format lint typecheck install dev clean build publish release-patch release-minor release-major

test:
	uv run pytest

# What the tests fail to hold, for everything this branch changed. The highest installed version of
# the plugin wins; `HARDEN=path make harden` points at another checkout, and `make harden ARGS=--help`
# explains the range, the report and the exit codes.
HARDEN ?= $(shell ls -d $(HOME)/.claude/plugins/cache/*/mx/*/skills/testing/harden.py 2>/dev/null | sort -V | tail -1)
ARGS ?=

harden:
	@test -n "$(HARDEN)" || { echo "no harden.py found; install the mx plugin or set HARDEN=<path>"; exit 1; }
	@echo "harden: $(HARDEN)"
	uv run $(HARDEN) $(ARGS)

# The property tests again, at the fuzz profile's budget, until you stop it. HypoFuzz takes over
# when it is installed and adds coverage guidance; its licence is the project's call.
fuzz:
	@if uv run python -c "import hypofuzz" >/dev/null 2>&1; then \
	  uv run hypothesis fuzz -- tests/properties; \
	else \
	  echo "no hypofuzz: looping the fuzz profile instead, ctrl-c to stop"; \
	  while HYPOTHESIS_PROFILE=fuzz uv run pytest tests/properties -q; do :; done; \
	fi

check: lint typecheck
	@echo "All checks passed!"

lint:
	uv run ruff check

format:
	uv run ruff format

format-check:
	uv run ruff format --check

typecheck:
	uv run ty check

fix:
	uv run ruff check --fix
	uv run ruff format

install:
	uv sync

dev:
	uv sync --group dev

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build: clean
	uv build

publish: build
	uv publish && git push && git push --tags
	@VERSION=$$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2) && \
		PREV_TAG=$$(git describe --tags --abbrev=0 "v$$VERSION^" 2>/dev/null || echo "") && \
		if [ -n "$$PREV_TAG" ]; then \
			NOTES=$$(git log "$$PREV_TAG..v$$VERSION" --pretty=format:"- %s" | grep -v "^- Release v"); \
		else \
			NOTES=$$(git log "v$$VERSION" --pretty=format:"- %s" | grep -v "^- Release v"); \
		fi && \
		gh release create "v$$VERSION" --title "v$$VERSION" --notes "$$NOTES"

define bump_version
	@uv run python -c 'import tomllib; s=open("pyproject.toml","r",encoding="utf-8").read(); v=tomllib.loads(s)["project"]["version"]; a,mi,pa=map(int,v.split(".")); nv=$(1); open("pyproject.toml","w",encoding="utf-8").write(s.replace(f"version = \"{v}\"", f"version = \"{nv}\"", 1)); print(f"Bumped {v} -> {nv}")'
	@VERSION=$$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2) && \
		git add pyproject.toml && \
		git commit -m "Release v$$VERSION" && \
		git tag -m "v$$VERSION" "v$$VERSION"
endef

release-patch: check test
	$(call bump_version,f"{a}.{mi}.{pa+1}")

release-minor: check test
	$(call bump_version,f"{a}.{mi+1}.0")

release-major: check test
	$(call bump_version,f"{a+1}.0.0")
