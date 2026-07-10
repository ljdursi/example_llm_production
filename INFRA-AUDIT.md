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
- ✅ **DCGM / GPU signal (layer 3) now ships.** `dcgm-exporter` is a service in `docker-compose.selfhost.yaml` (starts with `make selfhost`), mounting a committed non-profiling counter set (`monitoring/dcgm/counters.csv`) so the dashboard's GPU panels populate even on virtualized/cloud GPU hosts. Verified live on an L40S box: `DCGM_FI_DEV_GPU_UTIL` / `DCGM_FI_DEV_FB_USED` scrape cleanly. (Resolved Open item 1.)
- ✅ Scrape completeness confirmed: `prometheus.yml` has jobs for `gateway` (`/metrics`, 307→`/metrics/` followed automatically), `nim-coder` (`:8000/metrics`), and `dcgm` (`dcgm-exporter:9400`, now backed by the shipped service). (Resolved Open item 4.)

### 00-07 operating
- ✅ Pinned tags in `docker-compose.yaml` and `k8s/base/`; `Makefile` `up`/`smoke`/`eval`/`perf`; `tls/Caddyfile`.

### 01-01 swapping-in-self-hosted-nim
- ✅ `docker-compose.selfhost.yaml` (`nim-coder`, pinned-tag guidance), Phase-1 template in `gateway/litellm-config.yaml`, `make selfhost`, `NGC_API_KEY` in `.env.example`.

### 01-02 evaluating-and-replacing-a-model
- ✅ Candidate/load-balancing stanza templates in `gateway/litellm-config.yaml`, `tests/eval/`, `make eval`/`perf` (`MODEL=` arg supported), `requested_model` Grafana label.

### 01-03 comparing-fine-tunes-with-lora
- ✅ **`nim-general` is a real service** in `docker-compose.selfhost.yaml`, behind the `lora` compose profile (so `make selfhost` doesn't start it), launched by **`make lora`**. (Resolved Open item 2.)
- ✅ `loras/README.md` is committed documenting the expected adapter layout; `.gitignore` keeps adapter contents out but tracks the README (`loras/*` + `!loras/README.md`). (Resolved Open item 2.)
- ✅ **Walkthrough ran end to end on the L40S box** (see Live verification): base `general` vs `general-lora` showed the documented Pontic-dialect delta; regression probe held. Two doc fixes applied — `huggingface-cli download` → `hf download` + a `pip install huggingface_hub` prereq (the CLI wasn't installed and wasn't listed), and the backend caveat updated (the NIM auto-selected the vLLM backend on the L40S and LoRA worked; the TRT-LLM gap is the real caveat). → **Open item 7**.
- ⚠️ **No k8s LoRA manifest yet** — the walkthrough is compose-only; `k8s/nim/` has just `nim-coder`, no `nim-general`/PEFT equivalent. **Decided to build it out on the k8s track** (multi-LoRA NIM + `loras/` via PVC/hostPath + doc pointer). → **Open item 7** (planned).

### 02-01 kubernetes
- ✅ `k8s/base/` (litellm, postgres, namespace, **webui**), `k8s/nim/`, `k8s/monitoring/servicemonitor.yaml`, `k8s/README.md` (secret + deploy commands, translation table).
- ✅ **`webui` now has a k8s manifest** — `k8s/base/webui/` (Deployment + PVC + Service), wired into `base/kustomization.yaml` and pointing at the in-cluster `litellm` Service; `kubectl kustomize k8s/base` renders it. (Resolved Open item 3.)

### 03-01 scaling-out
- ❌ **No Dynamo manifests/compose shipped.** Dynamo is deployed via its own operator/Helm chart, out of this repo's scope; the doc is conceptual + external. `kubectl scale` (replicas) works today; the Dynamo/autoscaling machinery does not exist as runnable infra here. → **Open item 5**.

---

## Open items to revisit

1. ✅ **RESOLVED — DCGM exporter for GPU metrics.** Shipped as the `dcgm-exporter`
   service in `docker-compose.selfhost.yaml` (starts with `make selfhost`),
   scraped by the existing `dcgm` job in `prometheus.yml`. Mounts a committed
   non-profiling counter set (`monitoring/dcgm/counters.csv`) so the GPU panels
   populate on virtualized/cloud hosts as well as bare metal; 00-06 documents the
   bare-metal fuller-set fallback. Verified live on an L40S.

2. ✅ **RESOLVED — LoRA NIM ergonomics (01-03).** `nim-general` is now a real
   service behind the `lora` compose profile, launched by `make lora`; a
   committed `loras/README.md` documents the adapter layout and `.gitignore`
   tracks it while ignoring adapter contents. 01-03 uses `make lora`.

3. ✅ **RESOLVED — Chat UI on Kubernetes (02-01).** `k8s/base/webui/`
   (Deployment + PVC + Service) added and wired into `base/kustomization.yaml`;
   `k8s/README.md` translation table updated. `kubectl kustomize k8s/base`
   renders it pointing at the in-cluster `litellm` Service.

4. ✅ **RESOLVED — Prometheus scrape completeness (00-06).** Confirmed jobs for
   `gateway`, `nim-coder`, and `dcgm` (now backed by the shipped service);
   comments note the gateway 307→`/metrics/` and that `dcgm` is a Phase-1+ target.

5. **Phase 3 runnability (03-01).** Everything here is conceptual/external. If we ever want a runnable Phase 3, that's a `k8s/dynamo/` example (frontend + KV-router + a prefill/decode split) plus a KEDA/HPA scaled-object example. Large; likely stays documented-only for a pilot repo — flag intentionally. **(Left open by design — out of scope for a Phase 0–2 pilot.)**

6. ✅ **RESOLVED (not previously listed) — `coder` model id drift across the
   Phase 0→1 cutover, and the model choice itself.** The Phase-1 artifacts
   (`docker-compose.selfhost.yaml`, `k8s/nim/nim-coder.yaml`, docs 01-01/01-03,
   perf tokenizer examples) named `qwen/qwen2.5-coder-32b-instruct` while the
   config served a different model — so the "same model across the cutover, so
   the Phase-0 eval baseline is the Phase-1 acceptance test" promise was broken.
   Converged `coder` to **`meta/llama-3.2-3b-instruct`** everywhere: it exists as
   both a hosted endpoint (Phase 0) and an NGC NIM (Phase 1), **and** is a small
   3B that self-hosts on one modest GPU — so Phase 1 is genuinely testable end to
   end without a multi-GPU box. (A bigger/stronger coder is then a `docs/01-02`
   evaluate-and-replace exercise, not a prerequisite.)

7. **LoRA walkthrough (01-03) — flagged during live run.** Two doc fixes were
   applied inline (`hf download` + `pip install huggingface_hub` prereq; backend
   caveat corrected — the NIM defaults to vLLM on L40S and LoRA works, so the
   TRT-LLM warning was overstated). **Decided: build out LoRA on the k8s track
   too** (not compose-only). Planned work:
   - Add `k8s/nim/nim-general.yaml` — a multi-LoRA NIM (Llama-3.1-8B base) mirroring
     the compose `nim-general`: `NIM_PEFT_SOURCE=/opt/nim/loras`,
     `NIM_PEFT_REFRESH_INTERVAL`, `imagePullSecrets: ngc-registry`, GPU limit, and
     the `loras/` adapter tree mounted via a PVC or hostPath (decide how adapters
     land on the cluster — PVC + a copy job, or a hostPath on the GPU node).
   - Wire it in (its own `k8s/nim/kustomization.yaml` entry or a separate overlay so
     it isn't pulled by the default `coder` NIM apply), and add the base +
     `-lora` gateway stanzas pointing at the in-cluster `nim-general` Service.
   - Update `k8s/README.md`'s translation table and add a short "LoRA on k8s"
     pointer from 01-03 (and/or 02-01) so the Phase-2 reader isn't left without it.
   - Verify on the MicroK8s box the same way the compose path was verified here.

---

## Live verification (2026-07-10, on a 2× L40S box)

Beyond parsing/kustomize checks, the phases were exercised end to end:

- **Phase 0** — `docker compose up` (gateway + Postgres + Open WebUI): `/v1/models`
  lists `coder`+`general`, bad keys → 401, `make create-key` mints a budgeted
  per-user key, spend/DB wiring returns 200. A hosted `coder` completion
  round-tripped through the gateway (later hosted calls were throttled — expected
  on a shared free-tier key after many requests).
- **Phase 1** — `make selfhost` pulled and ran the real
  `nvcr.io/nim/meta/llama-3.2-3b-instruct` NIM on one L40S (nvcr.io login used the
  NVIDIA API key). The NIM served `meta/llama-3.2-3b-instruct` and replied `pong`
  directly; after the doc 01-01 cutover (only `api_base`→`http://nim-coder:8000/v1`),
  `coder` was served by the local NIM and the smoke suite passed **5/5** (wiring +
  coder round-trip + spend). `dcgm-exporter` scraped GPU metrics from the L40S.
- **Phase 2** — a real Kubernetes cluster (MicroK8s, single node, GPU addon
  enabled → `nvidia.com/gpu=2` allocatable). `kubectl apply -k k8s/base/` brought
  up `litellm`, `postgres`, and `webui` (all pods `Running`); the in-cluster
  gateway (from a ConfigMap of `litellm-config.yaml`) served `/v1/models` and
  enforced auth. Then `kubectl apply -k k8s/nim/` scheduled the **llama-3.2-3b
  NIM onto the node GPU** (`ngc-registry` pull secret + `NGC_API_KEY` in
  `llm-secrets`); after repointing `coder`'s `api_base` to
  `http://nim-coder.llm-service:8000/v1` in the ConfigMap and rolling the gateway,
  `coder` was served by the **in-cluster GPU NIM** and the smoke suite passed
  **5/5** through the in-cluster gateway. Same manifests as `k8s/` ship — the only
  reader-supplied inputs are the four secrets in `k8s/README.md`.

- **LoRA (doc 01-03)** — `make lora` ran the `nvcr.io/nim/meta/llama-3.1-8b-instruct`
  multi-LoRA NIM on the L40S; it auto-selected the **vLLM** backend (FP8). The
  example adapter (`Stergios/llama3.1-8b-instruct-lora`, public — no HF token)
  downloaded and validated against the doc's table (base `Llama-3.1-8B-Instruct`,
  `r=16`, 7 target modules, `modules_to_save=null`); after the doc's tokenizer-file
  removal it registered at `/v1/models` alongside the base. Base `general` vs
  `general-lora` showed the documented Pontic-dialect delta, and the boiling-point
  regression probe held on both. Doc fixes applied (see 01-03 coverage).

The NIM/GPU parts need NGC access + a GPU-scheduling cluster; both were exercised
here (the base stack needs neither).
