.PHONY: help version test install lint precommit bump-patch bump-minor bump-major

VERSION := $(shell cat VERSION 2>/dev/null || echo "0.0.1")

COLOR_RESET  := \033[0m
COLOR_BOLD   := \033[1m
COLOR_GREEN  := \033[32m
COLOR_YELLOW := \033[33m

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "$(COLOR_BOLD)Available targets:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'

version: ## Show current version
	@echo "$(COLOR_YELLOW)$(VERSION)$(COLOR_RESET)"

install: ## Install all dependencies
	uv sync

test: ## Run tests
	uv run pytest tests/ -v

lint: ## Format code with black
	uv run black cogrion_cli tests

precommit: lint test ## Run lint then tests — use before committing

define update-version
	sed -i 's/^version = ".*"/version = "$(NEW_VER)"/' pyproject.toml
endef

bump-patch: ## Bump patch version (x.y.Z → x.y.Z+1)
	$(eval NEW_VER := $(shell echo "$(VERSION)" | awk -F. '{printf "%s.%s.%d\n", $$1, $$2, $$3+1}'))
	@echo "$(NEW_VER)" > VERSION
	$(update-version)
	@echo "$(COLOR_YELLOW)Version → $(NEW_VER)$(COLOR_RESET)"

bump-minor: ## Bump minor version (x.Y.z → x.Y+1.0)
	$(eval NEW_VER := $(shell echo "$(VERSION)" | awk -F. '{printf "%s.%d.0\n", $$1, $$2+1}'))
	@echo "$(NEW_VER)" > VERSION
	$(update-version)
	@echo "$(COLOR_YELLOW)Version → $(NEW_VER)$(COLOR_RESET)"

bump-major: ## Bump major version (X.y.z → X+1.0.0)
	$(eval NEW_VER := $(shell echo "$(VERSION)" | awk -F. '{printf "%d.0.0\n", $$1+1}'))
	@echo "$(NEW_VER)" > VERSION
	$(update-version)
	@echo "$(COLOR_YELLOW)Version → $(NEW_VER)$(COLOR_RESET)"
