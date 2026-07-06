# Monitoring: feeding your existing Prometheus/Grafana

You already operate Prometheus and Grafana — good, that's the design
assumption. This stack ships metric *sources* and a starter dashboard; the
bundled Prometheus/Grafana (`make monitoring`) exist only so the repo is
self-contained for evaluation. For real use, add the scrape jobs to your
central Prometheus and import the dashboard into your central Grafana.

## The three layers of signal

**1. Serving layer — is the model service healthy and keeping up?**
Every NIM exposes Prometheus metrics natively at `:8000/metrics` (so do vLLM
and Dynamo — NIM follows vLLM's metric naming). No exporter needed; scrape
each backend directly (`monitoring/prometheus/prometheus.yml` shows the jobs;
on k8s, `k8s/monitoring/servicemonitor.yaml`). The ones that matter:

| Metric (vLLM/NIM naming) | Meaning | Watch for |
|---|---|---|
| `num_requests_running` / `num_requests_waiting` | in-flight vs queued | sustained waiting > 0 = you need capacity (or Phase 3) |
| `time_to_first_token_seconds` (histogram) | user-perceived responsiveness | p95 growth under load |
| `time_per_output_token_seconds` | stream speed | creeping up as batch sizes grow |
| `gpu_cache_usage_perc` | KV-cache pressure | pinned near 100% = context lengths outrunning VRAM |

**2. Hardware — are the GPUs healthy and earning their keep?**
Run NVIDIA's [dcgm-exporter](https://github.com/NVIDIA/dcgm-exporter) on every
GPU node (one `docker run`, or the GPU Operator deploys it on k8s):
utilization, VRAM, temperature, power. Utilization data is also your honest
answer to "do we need more GPUs?" — and, just as valuable in academia, to "are
the ones we have justified?"

**3. Usage — who is using what?**
This lives in the **gateway's Postgres**, queried via `/spend` APIs
([02-the-gateway.md](02-the-gateway.md)) — billing-grade per-user/per-model
records. A caveat discovered so you don't have to: LiteLLM's native Prometheus
`/metrics` endpoint is an enterprise-licensed feature. Rather than pay for or
work around it, this design treats usage accounting as the gateway's job
(Postgres, exact) and operational telemetry as the serving layer's job
(Prometheus) — a cleaner split anyway. If you want per-user request rates on
Grafana dashboards, options: a tiny cron that publishes `/spend` deltas to
Prometheus's pushgateway, Grafana's Postgres datasource pointed at the spend
tables (read-only user, easy win), or an Envoy-based gateway which emits
request metrics natively.

## Wiring it in

```bash
# 1. copy the scrape jobs into your central prometheus.yml (adjust hostnames)
# 2. import monitoring/grafana/dashboards/llm-overview.json into Grafana
# 3. sanity-check end-to-end: generate load and watch it move
make perf MODEL=coder
```

The starter dashboard is deliberately minimal (four panels). Once it's boring,
import the community vLLM and DCGM dashboards from grafana.com for depth —
but a small dashboard the team fully understands beats a wall of panels
nobody reads.

## Alerting, sized for three nines

Don't build a paging rotation for a service whose users will tolerate a
morning outage. Sensible tiers:

1. **Nightly smoke+eval in CI** ([04-testing](04-testing-performance-and-quality.md)) —
   catches "quietly broken" within a day, costs nothing.
2. **A few Alertmanager rules into your existing channels** (email/Slack):
   gateway `/health/liveliness` failing (blackbox exporter or your uptime
   checker), any backend target `up == 0` for 10m, `num_requests_waiting`
   sustained high for 30m, DCGM thermal alerts.
3. That's it, until this pilot graduates into something people's deadlines
   depend on — at which point revisit deliberately.
