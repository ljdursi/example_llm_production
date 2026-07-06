# Operating the service: network exposure, upgrades, and a small runbook

Phases 0–3 are about *building*; this page is about the day-2 habits that make
the service trustworthy. None of it is LLM-specific — which is the point: the
pilot is practice for every service after it.

## Network exposure (recap)

TLS is part of getting started, not an afterthought — `make tls` and the
loopback rebind are [01-getting-started.md](01-getting-started.md) step 4,
and on Kubernetes it's the Ingress + cert-manager path in
[06-kubernetes.md](06-kubernetes.md). The two rules worth restating as
*operating* rules:

- The **NIM/backends** are never exposed, on any track: only the gateway
  (and Prometheus) may reach them. Anything new you add — an eval runner, a
  batch pipeline — goes through the gateway with its own key, like any user.
- The **master key** only ever transits the network over TLS; before the
  front door is up, admin work happens on the host itself.

## Upgrades: why every image is pinned

Every container tag in this repo is pinned to a specific version, and that's
load-bearing, not fussiness. The gateway is an internet-facing service holding
every user credential — in early 2026 alone, LiteLLM had a supply-chain
incident (malicious published releases) and a critical, actively-exploited
auth-path SQL injection (fixed in v1.83.7). A floating tag like `:latest` or
`:main-stable` means you deploy whatever existed at your last pull, silently.
Pinned tags mean an upgrade is a *decision*, with a procedure:

1. Read the release notes (for LiteLLM, watch the security advisories
   particularly); bump the tag in `docker-compose.yaml` **and** the k8s
   manifests in the same commit.
2. `make up` (compose recreates the changed container), or
   `kubectl apply -k k8s/base/`.
3. `make smoke && make eval` — same acceptance tests as a backend migration,
   because an upgrade *is* one.
4. Commit. The git history of tags is your service changelog.

Same procedure for NIM upgrades, plus `make perf` — a new engine build can
shift performance, and you want to know by how much, not vibes. Cadence:
gateway monthly-ish (or immediately on a security advisory — subscribe to
LiteLLM's GitHub security advisories so those find you); NIMs when a model or
engine improvement is worth taking, not reflexively.

## A small runbook

The failure modes you'll actually see, in the order you'll see them:

| Symptom | First check | Usual cause |
|---|---|---|
| Completions return 401/403 | which key? `curl /v1/models` with it | expired/revoked key, or budget exhausted (check `/key/info`) |
| Completions return 429 | `/key/info` for the key | `rpm_limit`/`tpm_limit` doing its job — a runaway client loop |
| Phase 0 completions 5xx, gateway healthy | `make logs` for the upstream error | upstream `NVIDIA_API_KEY` invalid/rate-limited at build.nvidia.com |
| Phase 1 completions 5xx or hang | `curl nim-host:8000/v1/health/ready`; `docker compose logs nim-coder` | NIM restarted and is reloading weights (minutes), or OOM — check `dcgm` / dmesg |
| Gateway up but no models listed | `make logs` right after start | YAML error in `litellm-config.yaml` — it fails at config parse |
| Keys work but no spend rows | gateway logs for DB errors | `DATABASE_URL`/Postgres down; spend writes are async, so this fails quietly |
| Everything slow, nothing down | Grafana: queue depth & KV-cache panels | saturation, not breakage — this is the [07-scaling-out.md](07-scaling-out.md) trigger |
| Chat UI errors but API fine | webui container logs | UI's gateway key revoked, or UI version bump changed config |

The habit that makes the runbook work: **look at the layer below the symptom.**
Users see the gateway; the gateway sees the backend; the backend sees the GPU.
One layer per step, and the monitoring from [05-monitoring.md](05-monitoring.md)
is exactly the set of eyes this walk needs.

When you fix something that isn't in this table, add a row. A runbook nobody
grows is a runbook nobody trusts.
