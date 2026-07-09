# Architecture: why these pieces

## The problem shape

You're standing up shared LLM inference for researchers, as a pilot for a
family of such services. The constraints that actually drive the design:

- **Multi-user from day one.** Individual accountability (whose usage is
  whose), revocable access, and per-user/group budgets — this is what
  separates "a service" from "a GPU box with vLLM someone SSHes into."
- **The backends will churn; the interface must not.** Today a hosted API,
  next quarter a NIM on one box, next year disaggregated serving on a
  cluster. Researchers configure their IDE once.
- **Academic availability.** Three nines or fewer. That rules *in* simple
  designs (one gateway, restart-on-failure) and rules *out* premature
  complexity (multi-region, five-nines HA databases).
- **Pedagogy is a requirement.** The team is learning; every component
  should be inspectable and explainable, and each capability added when its
  need is felt, not before.
- **Research data has rules.** In Phase 0 every prompt — source code,
  unpublished manuscripts — leaves campus for a hosted endpoint. That's fine
  for much work and a non-starter for some (health data, some funder and
  industry agreements). Name this constraint on day one, tell users what the
  service does and doesn't send off-site, and note that Phase 1 — the same
  model name moving on-prem with no client change — is the architecture's
  built-in answer to it.

## The load-bearing decision: gateway-first

Everything else in this repo follows from one decision: **users talk to a
gateway, never to a model server.**

```
users ──▶ GATEWAY ──▶ model backends (swappable, invisible to users)
          - authn: per-user API keys, revocable
          - accounting: every request logged with user, model, tokens, cost
          - budgets: per-user/team limits, so one runaway script can't eat a month of quota
          - routing: stable model names → whatever serves them today
          - one OpenAI-compatible API, because that's what every tool speaks
```

The gateway is the *service contract*. It's why Phase 0 can be zero-GPU
(backends are `build.nvidia.com` API calls), why Phase 1 is a two-line config
change, and why the testing and monitoring you build now stays valid through
every phase. It's also the pattern to reuse for your *next* service — the
gateway concept generalizes far beyond this pilot.

We use **LiteLLM Proxy**: open source, runs anywhere, and does keys, budgets,
spend tracking, and multi-backend routing out of the box. NVIDIA has no
open-source gateway, so this is the one non-NVIDIA choice at the core of the
stack. The interface it presents (OpenAI API + virtual keys) is a de facto
standard, so replacing it later with **Envoy AI Gateway** (CNCF, Envoy-based,
Kubernetes-native) or **Kong AI Gateway** / **Apache APISIX** is realistic;
see [00-03-the-gateway.md](00-03-the-gateway.md).

## The component map

| Concern | Component | Phase it appears | Why this one |
|---|---|---|---|
| Auth, accounting, routing | LiteLLM Proxy + Postgres | 0 | see above |
| Model serving | build.nvidia.com hosted APIs → NVIDIA NIM containers | 0 → 1 | *the same models*: the hosted API is NIM run by NVIDIA, so swapping changes operations, not behavior. Any OpenAI-compatible server (vLLM, SGLang) slots in identically. |
| Chat UI | Open WebUI | 0 | mature, zero-config against an OpenAI endpoint; it's just another gateway client |
| Wiring tests | pytest smoke tests | 0 | "did my change break auth/routing/serving?" in 30 seconds |
| Perf tests | AIPerf (NVIDIA OSS) | 0 | LLM-aware load: TTFT, inter-token latency, tokens/s |
| Quality tests | golden probes → NeMo Evaluator / lm-eval-harness | 0 | catches "the model behind this name got worse" |
| Monitoring | Prometheus metrics from backends + DCGM for GPUs → your existing Grafana | 0 (real signal from 1) | CNCF standard; you already run it |
| Orchestration | docker compose → Kubernetes (+ GPU Operator, NIM Operator) | 0 → 2 | compose while it's one box; k8s when it's more |
| Scale-out serving | NVIDIA Dynamo (OSS): KV-aware routing, disaggregated prefill/decode | 3 | when one replica per model stops being enough |
| Autoscaling | k8s HPA/KEDA on serving metrics, or Dynamo's planner | 3 | needs k8s; needs real utilization data first |

## What we deliberately did NOT include (yet)

Naming what's absent is as instructive as what's present:

- **SSO/OIDC integration** — pilot uses gateway-minted keys. LiteLLM supports
  OIDC when you're ready to wire into institutional identity; that's the
  first "productionization" step after the pilot proves out. (Often the first
  actual SSO ask is the chat UI, not the API — Open WebUI supports OIDC
  directly, config-only, without touching the key story.)
- **HA anything** — one gateway, one Postgres, restart-on-failure. At three
  nines with patient users, redundancy costs more in complexity than it buys.
  The k8s track makes gateway replicas a one-line change when wanted.
- **RAG / retrieval / agents** — application-layer concerns. This repo is the
  *serving substrate* those get built on; they arrive as gateway clients.
- **Multi-modal serving** — arrives as "another model_list entry" (vision
  NIMs speak the same OpenAI API with image content parts), not as new
  architecture. That's the test of a good substrate: the ambitious use case
  is boring to add.

---

**[Up: README](../README.md)** · **Next ▶** [00-02 · Getting started](00-02-getting-started.md)
