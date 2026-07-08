# Testing: wiring, performance, quality

Three test suites, three different questions, all present from Phase 0. The
shared discipline: **every one of them talks to the gateway, exactly like a
user** — so a passing suite validates the whole path (auth → routing →
backend), and the suites never need rewriting as backends change. That
invariance is what makes "swap the backend, rerun the suites" a safe,
routine operation instead of a leap of faith.

| Suite | Question | Tool | When to run |
|---|---|---|---|
| `tests/smoke/` | Is the service up and correctly wired? | pytest, stdlib only | after every change; ~30s |
| `tests/perf/` | How fast, and how many users can it carry? | AIPerf (NVIDIA OSS) | baseline now; before/after every backend change; when users report slowness |
| `tests/eval/` | Is the model behind each name good enough? | pytest goldens → NeMo Evaluator / lm-eval-harness | before/after every backend or model-version change |

Each suite's own README/docstring covers mechanics; this page is the *why and
when*.

## Smoke (`make smoke`)

Five checks in `tests/smoke/test_gateway.py`: liveness, models advertised,
bad keys rejected, real completions round-trip per model, spend logged. Note
the auth-rejection test — services drift toward accidentally-open; test the
*denial* path, not just the happy path. When you add a model to the gateway
config, add its name to `test_models_are_listed` in the same commit.

## Performance (`make perf`)

The metrics (TTFT, inter-token latency, request latency, tokens/s), the
baseline discipline, and concurrency sweeps are covered in
[tests/perf/README.md](../tests/perf/README.md). The headline: **numbers
without baselines are trivia**; capture them before you need them, commit the
CSVs, and always compare like-for-like parameters.

Perf tests and monitoring ([05-monitoring.md](05-monitoring.md)) are two views
of the same thing — run a concurrency sweep while watching the Grafana
dashboard and you'll see queue depth, KV-cache pressure, and GPU utilization
*explain* the latency curve. Do this once as a team; it's the fastest serving
education available.

## Quality (`make eval`)

Tiered: golden probes in-repo for regression detection, NeMo Evaluator or
lm-evaluation-harness for standardized benchmarks, task-specific eval sets as
use cases arrive — see [tests/eval/README.md](../tests/eval/README.md). The
one habit to establish now: **no backend/model change lands without an eval
run**, even while the eval is just five golden probes. The habit is the
infrastructure; the probes grow with your users' real prompts.

## Toward CI

Wiring these into whatever CI your institution runs is straightforward since
each suite is one make target — and rather than describe it, this repo ships
two ready-to-adapt examples in [`ci/`](../ci/): a GitLab CI pipeline
(`ci/gitlab-ci.yml`) and a GitHub Actions workflow
(`ci/github-actions-smoke.yml`), both implementing the same schedule: smoke on
every push that touches the gateway config, smoke+eval nightly against the
live service, perf weekly with results committed. A nightly smoke+eval run is
also your cheapest availability monitor: it fails loudly the morning after
something quietly broke — an entirely appropriate alerting story for a
three-nines academic service.

---

**◀ Prev** [03 · Self-hosted NIM](03-swapping-in-self-hosted-nim.md) · **[Up](../README.md)** · **Next ▶** [05 · Monitoring](05-monitoring.md)
