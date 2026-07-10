# Day-to-day driver for the stack. Everything here is a thin wrapper — read
# the underlying command it prints; there is no magic.

COMPOSE      := docker compose
GATEWAY_URL  ?= http://localhost:4000
-include .env
export

.PHONY: help up down logs tls monitoring guardrails selfhost lora create-key smoke perf eval

help:  ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

up:  ## start Phase 0: gateway + db + chat UI
	$(COMPOSE) up -d --wait
	@echo "gateway: $(GATEWAY_URL)/v1   chat UI: http://localhost:8080"

down:  ## stop everything (data volumes are kept)
	$(COMPOSE) --profile monitoring --profile tls down

tls:  ## start the HTTPS front door (set GATEWAY_HOSTNAME/WEBUI_HOSTNAME in .env first)
	$(COMPOSE) --profile tls up -d
	@echo "gateway: https://$(or $(GATEWAY_HOSTNAME),llm.example.edu)/v1   chat UI: https://$(or $(WEBUI_HOSTNAME),chat.llm.example.edu)"

logs:  ## follow gateway logs
	$(COMPOSE) logs -f gateway

monitoring:  ## also start local Prometheus (:9090) + Grafana (:3000)
	$(COMPOSE) --profile monitoring up -d

guardrails:  ## also start Presidio PII sidecars (then enable them in the config — see docs/00-04)
	$(COMPOSE) -f docker-compose.yaml -f docker-compose.guardrails.yaml up -d --wait
	@echo "Presidio running. Enable it: uncomment the guardrails block in"
	@echo "gateway/litellm-config.yaml, then: docker compose restart gateway"

selfhost:  ## Phase 1: also start the self-hosted NIM + GPU metrics (see docs/01-01)
	$(COMPOSE) -f docker-compose.yaml -f docker-compose.selfhost.yaml up -d

lora:  ## Phase 1 LoRA: start the Llama-3.1-8B multi-LoRA NIM (see docs/01-03)
	$(COMPOSE) -f docker-compose.yaml -f docker-compose.selfhost.yaml --profile lora up -d nim-general

create-key:  ## mint a user API key: make create-key USER_ID=alice BUDGET=20
	@test -n "$(USER_ID)" || { echo "usage: make create-key USER_ID=alice [BUDGET=20]"; exit 1; }
	@curl -s $(GATEWAY_URL)/key/generate \
	  -H "Authorization: Bearer $(LITELLM_MASTER_KEY)" \
	  -H "Content-Type: application/json" \
	  -d '{"user_id": "$(USER_ID)", "max_budget": $(or $(BUDGET),null), "budget_duration": "30d"}' \
	  | python3 -m json.tool

smoke:  ## run smoke tests against the running stack
	cd tests/smoke && python3 -m pytest -v

perf:  ## measure TTFT / inter-token latency / throughput with AIPerf
	tests/perf/run-perf.sh $(or $(MODEL),coder)

eval:  ## run golden-answer quality checks
	cd tests/eval && python3 -m pytest -v
