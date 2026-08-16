PLUGIN := mx/.claude-plugin/plugin.json
MARKETPLACE := .claude-plugin/marketplace.json

.PHONY: check version release-patch release-minor release-major publish

check:
	@jq -e . $(PLUGIN) >/dev/null
	@jq -e . $(MARKETPLACE) >/dev/null
	@echo "manifests parse"

version:
	@jq -r .version $(PLUGIN)

release-patch: PART = patch
release-minor: PART = minor
release-major: PART = major

release-patch release-minor release-major: check
	@V=$$(jq -r .version $(PLUGIN)); \
	NEW=$$(echo $$V | awk -F. -v part=$(PART) '{ \
	  if (part == "major") { printf "%d.0.0", $$1+1 } \
	  else if (part == "minor") { printf "%d.%d.0", $$1, $$2+1 } \
	  else { printf "%d.%d.%d", $$1, $$2, $$3+1 } }'); \
	tmp=$$(mktemp); jq --arg v "$$NEW" '.version = $$v' $(PLUGIN) >$$tmp && mv $$tmp $(PLUGIN); \
	git commit -q -m "mx v$$NEW" -- $(PLUGIN); \
	git tag -m "v$$NEW" "v$$NEW"; \
	echo "$$V -> $$NEW — run 'make publish' to ship it"

publish:
	git push
	git push --tags
