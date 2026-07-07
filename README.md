# Academic LLM Serving — a pilot you can grow

A reference repository for standing up a **multi-user LLM inference service** for
researchers, starting simple and growing deliberately. It is designed for an
academic environment: no five-nines SLAs, modest ops staffing, but a real need
for **per-user auth, usage accounting, testing, and monitoring** from day one —
because this pilot is the template for every service you stand up after it.

## The core idea

> **Put a gateway in front of everything on day one. Treat the models behind it
> as swappable.**

On day one, the "model services" behind the gateway are just **hosted API
endpoints at [build.nvidia.com](https://build.nvidia.com)** — zero GPUs
required, working in minutes. Every later phase (self-hosted NIM, Kubernetes,
KV-aware routing, autoscaling) changes *what's behind the gateway* without
changing what your users see. Their API keys, their tooling, the URL in their
editor config: none of it changes as you get more ambitious.

```
                      ┌──────────────────────────────────────────────┐
   researchers ──────▶│  LiteLLM Gateway                             │
   (API keys,         │  auth · per-user keys · budgets · accounting │
    IDE plugins,      │  model routing · OpenAI-compatible API       │
    chat UI)          └───────┬──────────────┬───────────────────────┘
                              │              │
                    Phase 0   ▼              ▼   Phase 1+
                 build.nvidia.com      self-hosted NIM on your GPUs
                 (hosted NIM APIs)     → Kubernetes (Phase 2)
                                       → Dynamo, KV-aware routing,
                                         autoscaling (Phase 3)
```

## The phases

| Phase | What changes | GPUs needed | Doc |
|-------|-------------|-------------|-----|
| **0. Gateway + hosted models** | Everything in this repo works, models are API calls to build.nvidia.com | none | [docs/01-getting-started.md](docs/01-getting-started.md) |
| **1. First self-hosted model** | Swap one placeholder for a NIM container on a local GPU box | 1 box | [docs/03-swapping-in-self-hosted-nim.md](docs/03-swapping-in-self-hosted-nim.md) |
| **2. Kubernetes** | Same components, k8s manifests (already mirrored in `k8s/`) | cluster | [docs/06-kubernetes.md](docs/06-kubernetes.md) |
| **3. Scale-out serving** | NVIDIA Dynamo, KV-cache-aware routing, autoscaling | cluster | [docs/07-scaling-out.md](docs/07-scaling-out.md) |

Testing (performance **and** quality) and monitoring are not phases — they are
present from Phase 0 and grow with you. See
[docs/04-testing-performance-and-quality.md](docs/04-testing-performance-and-quality.md)
and [docs/05-monitoring.md](docs/05-monitoring.md).

## Quick start (Phase 0, ~15 minutes)

Prerequisites: Docker with the compose plugin; `make` and Python ≥3.9 with
`venv`/`pip` (for the `make` targets and the test suites — on a bare
Debian/Ubuntu box: `sudo apt-get install make python3-venv python3-pip`); and a
(free) API key from [build.nvidia.com](https://build.nvidia.com).

```bash
cp .env.example .env         # then edit: set NVIDIA_API_KEY and the two secrets
make up                      # gateway + database + chat UI
make create-key USER_ID=you  # mint an API key for your first user
make smoke                   # verify auth, routing, and a real completion
```

Then open http://localhost:8080 for the chat UI, or point any OpenAI-compatible
client at `http://localhost:4000/v1` with the key you just minted.

Serving users beyond this machine? First run `make tls` — the built-in HTTPS
front door (keys never cross a network in the clear; docs/01, step 4).

Full walkthrough: [docs/01-getting-started.md](docs/01-getting-started.md).

## What's in the box

```
docker-compose.yaml            Phase 0 stack: gateway, Postgres, chat UI
docker-compose.selfhost.yaml   Phase 1 overlay: adds a self-hosted NIM
gateway/litellm-config.yaml    THE file to understand: models, routing, auth
tls/                           Caddyfile for the HTTPS front door (make tls)
monitoring/                    Prometheus scrape config + Grafana dashboards
tests/smoke/                   pytest: is the service up and correctly wired?
tests/perf/                    AIPerf: TTFT, inter-token latency, tok/s
tests/eval/                    golden-answer quality checks + eval-harness pointers
ci/                            ready-to-adapt GitLab CI / GitHub Actions pipelines
k8s/                           the same stack as Kubernetes manifests (Phase 2)
docs/                          pedagogical walkthroughs for every phase,
                               plus an operating runbook and a researcher handout
```

## Tooling choices, and their CNCF/community alternatives

This repo prefers NVIDIA open-source tooling where it exists (that's the
support path available to us), and notes vendor-neutral alternatives everywhere
so no choice is a lock-in:

| Role | This repo uses | Alternatives (documented in each doc) |
|------|----------------|--------------------------------------|
| Gateway (auth, accounting, routing) | [LiteLLM Proxy](https://docs.litellm.ai) (open source; NVIDIA has no OSS gateway) | Envoy AI Gateway (CNCF ecosystem, v1.0 GA), Kong AI Gateway, Apache APISIX |
| Model serving | NVIDIA NIM containers | vLLM, SGLang, llama.cpp — anything OpenAI-compatible slots in identically |
| Scale-out serving | [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo) (open source) | llm-d (CNCF Sandbox), vLLM production stack |
| Perf testing | [AIPerf](https://github.com/ai-dynamo/aiperf) (NVIDIA OSS; successor to genai-perf) | k6, Locust, vLLM benchmark scripts |
| Quality eval | pytest goldens here; [NeMo Evaluator](https://github.com/NVIDIA-NeMo/Evaluator) for depth | EleutherAI lm-evaluation-harness, promptfoo |
| Monitoring | Prometheus + Grafana (CNCF; feeds your existing infra) | — already the standard |
| Chat UI | [Open WebUI](https://github.com/open-webui/open-webui) (note: license adds a branding clause for >50-user deployments) | LibreChat, HuggingFace chat-ui |

## Reading order for the team

1. [docs/00-architecture.md](docs/00-architecture.md) — why a gateway, why these pieces
2. [docs/01-getting-started.md](docs/01-getting-started.md) — get Phase 0 running
3. [docs/02-the-gateway.md](docs/02-the-gateway.md) — keys, budgets, accounting, adding models
4. [docs/08-operating.md](docs/08-operating.md) — upgrades and the runbook: read before real users arrive
5. Everything else as you need it.
