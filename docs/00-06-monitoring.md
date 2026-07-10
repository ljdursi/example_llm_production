# Monitoring: feeding your existing Prometheus/Grafana

> **Learning objective.** Feed the four layers of signal (gateway, serving, GPU,
> ledger) into your Prometheus/Grafana: scrape the gateway and backend metrics,
> import the starter dashboard, and size alerting for a three-nines service.
>
> **Infrastructure** · *cross-cutting — from Phase 0 (real serving/GPU signal
> from Phase 1)*. [`monitoring/prometheus/prometheus.yml`](../monitoring/prometheus/prometheus.yml) ·
> [`monitoring/grafana/`](../monitoring/grafana) (dashboard + provisioning) ·
> [`Makefile`](../Makefile) (`monitoring`) ·
> [`k8s/monitoring/servicemonitor.yaml`](../k8s/monitoring/servicemonitor.yaml) ·
> `callbacks: ["prometheus"]` in [`gateway/litellm-config.yaml`](../gateway/litellm-config.yaml).

You already operate Prometheus and Grafana — good, that's the design
assumption. This stack ships metric *sources* and a starter dashboard; the
bundled Prometheus/Grafana (`make monitoring`) exist only so the repo is
self-contained for evaluation. For real use, add the scrape jobs to your
central Prometheus and import the dashboard into your central Grafana.

## The four layers of signal

**1. Gateway — is the service front door healthy, and who's knocking?**
LiteLLM's Prometheus integration (`callbacks: ["prometheus"]` in
`gateway/litellm-config.yaml`, exposed on `:4000/metrics`) gives you request
rates, failures, latency, and token counts labelled by model and key — it was
an enterprise-only feature until LiteLLM v1.80.0 (late 2025), and is now plain
open source. This is your dashboard/alerting view of usage; the *billing-grade*
record stays in Postgres (see layer 4).

Two version-specific gotchas, verified against the pinned v1.83.x image, worth
knowing when a gateway panel looks wrong: `:4000/metrics` **307-redirects to
`/metrics/`** — Prometheus follows it automatically, but a manual check needs
`curl -L`. And the per-model label on the proxy metrics is **`requested_model`**
(the served backend is `model_id`), *not* `model` — group by `requested_model`,
as the starter dashboard's gateway panels now do.

**2. Serving layer — is the model service healthy and keeping up?**
Every NIM exposes Prometheus metrics natively at `:8000/metrics` (so do vLLM
and Dynamo — NIM follows vLLM's metric naming, including its `vllm:` prefix).
No exporter needed; scrape each backend directly
(`monitoring/prometheus/prometheus.yml` shows the jobs; on k8s,
`k8s/monitoring/servicemonitor.yaml`). The ones that matter:

| Metric (vLLM/NIM naming) | Meaning | Watch for |
|---|---|---|
| `vllm:num_requests_running` / `vllm:num_requests_waiting` | in-flight vs queued | sustained waiting > 0 = you need capacity (or Phase 3) |
| `vllm:time_to_first_token_seconds` (histogram) | user-perceived responsiveness | p95 growth under load |
| `vllm:time_per_output_token_seconds` | stream speed | creeping up as batch sizes grow |
| `vllm:gpu_cache_usage_perc` | KV-cache pressure | pinned near 100% = context lengths outrunning VRAM |

Exact names drift a little between NIM/vLLM versions — `curl :8000/metrics`
against *your* backend once and adjust the dashboard; ten minutes well spent.

**3. Hardware — are the GPUs healthy and earning their keep?**
NVIDIA's [dcgm-exporter](https://github.com/NVIDIA/dcgm-exporter) gives you
utilization, VRAM, temperature, and power. It ships as the `dcgm-exporter`
service in `docker-compose.selfhost.yaml` (starts with `make selfhost`, since
GPU metrics only exist once you self-host); on Kubernetes the GPU Operator runs
it as a DaemonSet. The compose service mounts a small non-profiling counter set
(`monitoring/dcgm/counters.csv`) so the GPU panels populate even on virtualized
/ cloud GPU hosts — on bare metal, drop that mount for NVIDIA's fuller defaults
(the file explains both). Utilization data is also your honest answer to "do we
need more GPUs?" — and, just as valuable in academia, to "are the ones we have
justified?"

**4. Usage accounting — who used what, exactly?**
This lives in the **gateway's Postgres**, queried via `/spend` APIs
([00-03-the-gateway.md](00-03-the-gateway.md)) — billing-grade per-user/per-model
records. Don't be tempted to do accounting from the Prometheus side just
because layer 1 has token counters: metrics are sampled, relabelled, and
retention-limited by design. The split to keep in your head: **Postgres is
the ledger; Prometheus is the EKG.** (If you'd rather chart usage straight
from the ledger, Grafana's Postgres datasource pointed at the spend tables
with a read-only user is an easy win.)

## Wiring it in

```bash
# 1. copy the scrape jobs into your central prometheus.yml (adjust hostnames)
# 2. import monitoring/grafana/dashboards/llm-overview.json into Grafana
# 3. sanity-check end-to-end: generate load and watch it move
make perf MODEL=coder
```

The starter dashboard is deliberately minimal (six panels). Once it's boring,
import the community vLLM and DCGM dashboards from grafana.com for depth —
but a small dashboard the team fully understands beats a wall of panels
nobody reads.

## Alerting, sized for three nines

Don't build a paging rotation for a service whose users will tolerate a
morning outage. Sensible tiers:

1. **Nightly smoke+eval in CI** ([00-05 · testing](00-05-testing-performance-and-quality.md)) —
   catches "quietly broken" within a day, costs nothing.
2. **A few Alertmanager rules into your existing channels** (email/Slack):
   gateway `/health/liveliness` failing (blackbox exporter or your uptime
   checker), any backend target `up == 0` for 10m, `vllm:num_requests_waiting`
   sustained high for 30m, a rising gateway failure rate
   (`litellm_proxy_failed_requests_metric_total`), DCGM thermal alerts.
3. That's it, until this pilot graduates into something people's deadlines
   depend on — at which point revisit deliberately.

---

**◀ Prev** [00-05 · Testing](00-05-testing-performance-and-quality.md) · **[Up](../README.md)** · **Next ▶** [00-07 · Operating](00-07-operating.md)
