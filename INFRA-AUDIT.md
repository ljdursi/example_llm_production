# Infrastructure audit — docs ↔ definitions

For each walkthrough doc, the concrete infrastructure it depends on, whether that
definition is present and complete in the repo, and open items to revisit one by
one. Generated alongside the per-doc **Infrastructure** header blocks (which now
carry the links); this file tracks *completeness*, not just linkage.

**Legend:** ✅ present & complete · ⚠️ present but incomplete / relies on reader
instructions · ❌ referenced but not shipped (by design or a real gap).

The `researcher-handout.md` is intentionally excluded — it's a template to hand
to end users, not a build/learning doc, so it carries no objective/infra block.

---

## Per-doc coverage

### 00-01 architecture
- ✅ Conceptual only; defines no infrastructure. Links forward to where each piece is stood up.

### 00-02 getting-started
- ✅ `.env.example` — documents all three secrets incl. the two `openssl rand` generators.
- ✅ `docker-compose.yaml` — gateway/db/webui, pinned tags; `caddy` under `--profile tls`.
- ✅ `gateway/litellm-config.yaml`, `Makefile` targets, `tests/`.

### 00-03 the-gateway
- ✅ `gateway/litellm-config.yaml` (fake illustrative prices present so budgets bind), `Makefile` `create-key`, gateway/db services.

### 00-04 guardrails
- ✅ `docker-compose.guardrails.yaml` (presidio-analyzer/anonymizer sidecars).
- ✅ Pre-written, commented `guardrails:` block in `gateway/litellm-config.yaml`; `Makefile` `guardrails`.

### 00-05 testing
- ✅ `tests/smoke|perf|eval`, `Makefile` `smoke`/`perf`/`eval`, `ci/gitlab-ci.yml`, `ci/github-actions-smoke.yml`.

### 00-06 monitoring
- ✅ `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/` (dashboard + provisioning), `make monitoring`, `k8s/monitoring/servicemonitor.yaml`.
- ⚠️ **DCGM / GPU signal (layer 3) ships no definition.** The doc describes GPU metrics via dcgm-exporter but there is no dcgm-exporter service in any compose file, and the `monitoring` profile is prometheus+grafana only. On the single-box compose GPU host the GPU panels stay empty until the reader runs dcgm-exporter by hand. → see **Open item 1**.
- ⚠️ Verify `monitoring/prometheus/prometheus.yml` actually contains scrape jobs for the gateway, the NIM backend(s), and (if added) dcgm — not audited line-by-line here. → **Open item 4**.

### 00-07 operating
- ✅ Pinned tags in `docker-compose.yaml` and `k8s/base/`; `Makefile` `up`/`smoke`/`eval`/`perf`; `tls/Caddyfile`.

### 01-01 swapping-in-self-hosted-nim
- ✅ `docker-compose.selfhost.yaml` (`nim-coder`, pinned-tag guidance), Phase-1 template in `gateway/litellm-config.yaml`, `make selfhost`, `NGC_API_KEY` in `.env.example`.

### 01-02 evaluating-and-replacing-a-model
- ✅ Candidate/load-balancing stanza templates in `gateway/litellm-config.yaml`, `tests/eval/`, `make eval`/`perf` (`MODEL=` arg supported), `requested_model` Grafana label.

### 01-03 comparing-fine-tunes-with-lora
- ⚠️ **`nim-general` service is commented-out** in `docker-compose.selfhost.yaml`, and there is **no `make` target** to launch it — the reader runs a raw `docker compose … up -d nim-general`. → **Open item 2**.
- ⚠️ `loras/` adapter tree is reader-created (gitignored); the doc gives exact `huggingface-cli` steps. Expected, but there is no `loras/.gitkeep` or example layout committed. → **Open item 2**.

### 02-01 kubernetes
- ✅ `k8s/base/` (litellm, postgres, namespace), `k8s/nim/`, `k8s/monitoring/servicemonitor.yaml`, `k8s/README.md` (secret + deploy commands, translation table).
- ⚠️ **`webui` has no k8s manifest** — `k8s/README.md` leaves it "as the first exercise." Deliberate, but means the k8s track has no chat UI out of the box. → **Open item 3**.

### 03-01 scaling-out
- ❌ **No Dynamo manifests/compose shipped.** Dynamo is deployed via its own operator/Helm chart, out of this repo's scope; the doc is conceptual + external. `kubectl scale` (replicas) works today; the Dynamo/autoscaling machinery does not exist as runnable infra here. → **Open item 5**.

---

## Open items to revisit

1. **DCGM exporter for GPU metrics.** Monitoring (00-06) and architecture (00-01) promise a GPU signal, but nothing ships it for the compose track. Options: add a `dcgm-exporter` service to `docker-compose.selfhost.yaml` (or a `monitoring`-profile overlay) with a matching Prometheus scrape job, or make the "run it yourself" instruction explicit and prominent in 00-06. Decide runnable-vs-documented.

2. **LoRA NIM ergonomics (01-03).** The `nim-general` multi-LoRA service is commented out with no launcher. Consider: a `make lora` / `make selfhost-lora` target, committing a `loras/.gitkeep` (or `loras/README.md`) documenting the expected adapter layout, and deciding whether `nim-general` should be uncommented-but-profiled rather than commented.

3. **Chat UI on Kubernetes (02-01).** `webui` is intentionally left out of `k8s/base/`. Either ship the manifest (removing an undifferentiated exercise) or keep it as an exercise but add a short "here's the shape" pointer so a k8s deployment isn't silently UI-less.

4. **Prometheus scrape completeness (00-06).** Confirm `monitoring/prometheus/prometheus.yml` covers gateway (`/metrics/`, note the 307), each NIM backend (`:8000/metrics`), and dcgm — with hostnames/placeholders that match the compose and self-host service names.

5. **Phase 3 runnability (03-01).** Everything here is conceptual/external. If we ever want a runnable Phase 3, that's a `k8s/dynamo/` example (frontend + KV-router + a prefill/decode split) plus a KEDA/HPA scaled-object example. Large; likely stays documented-only for a pilot repo — flag intentionally.
