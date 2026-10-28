# НОУС — единый интерфейс команд. Реализация в scripts/ (одна задача = одна команда).
SHELL := /bin/bash
.DEFAULT_GOAL := verify

.PHONY: bootstrap verify state release help

bootstrap: ## подготовить среду (идемпотентно)
	bash scripts/bootstrap.sh

verify: ## сверить карту с территорией (все проверки)
	bash scripts/verify.sh

state: ## снять состояние организма в state/
	bash scripts/state.sh

release: ## подготовить релизный срез (локальная проверка)
	bash scripts/verify.sh && bash scripts/gen_llms.sh

help: ## показать список целей
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
