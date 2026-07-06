# Day-to-day driver for the stack. Everything here is a thin wrapper — read
# the underlying command it prints; there is no magic.

COMPOSE      := docker compose
GATEWAY_URL  ?= http://localhost:4000
-include .env
export

.PHONY: help up down logs monitoring selfhost create-key smoke perf eval

help:  ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

up:  ## start Phase 0: gateway + db + chat UI
	$(COMPOSE) up -d --wait
	@echo "gateway: $(GATEWAY_URL)/v1   chat UI: http://localhost:8080"

down:  ## stop everything (data volumes are kept)
	$(COMPOSE) --profile monitoring down

logs:  ## follow gateway logs
	$(COMPOSE) logs -f gateway

monitoring:  ## also start local Prometheus (:9090) + Grafana (:3000)
	$(COMPOSE) --profile monitoring up -d

selfhost:  ## Phase 1: also start the self-hosted NIM (see docs/03)
	$(COMPOSE) -f docker-compose.yaml -f docker-compose.selfhost.yaml up -d

create-key:  ## mint a user API key: make create-key USER=alice BUDGET=20
	@curl -s $(GATEWAY_URL)/key/generate \
	  -H "Authorization: Bearer $(LITELLM_MASTER_KEY)" \
	  -H "Content-Type: application/json" \
	  -d '{"user_id": "$(or $(USER_ID),$(USER))", "max_budget": $(or $(BUDGET),null), "budget_duration": "30d"}' \
	  | python3 -m json.tool

smoke:  ## run smoke tests against the running stack
	cd tests/smoke && python3 -m pytest -v

perf:  ## measure TTFT / inter-token latency / throughput with genai-perf
	tests/perf/run-genai-perf.sh $(or $(MODEL),coder)

eval:  ## run golden-answer quality checks
	cd tests/eval && python3 -m pytest -v
