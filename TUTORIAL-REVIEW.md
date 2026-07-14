# Tutorial review log

Review date: 2026-07-14

Perspective: a sysadmin comfortable with Docker and moderately familiar with
Kubernetes, but new to operating LLM inference. This is a static review: no
containers, models, or Kubernetes resources were started. The local machine did
not have a usable Docker Compose plugin or `kubectl`, so Compose rendering and
Kustomize rendering could not be repeated here. `INFRA-AUDIT.md` records an
earlier live exercise of Phases 0–2 on GPU hardware.

This is a review log, not a change list. It separates tutorial blockers from
smaller improvements so fixes can be discussed and applied deliberately.

## Overall assessment

The tutorial has a strong spine:

1. establish the gateway as the stable service boundary;
2. stand up a GPU-free service against hosted backends;
3. add access control, safety, testing, monitoring, and operating habits;
4. replace a hosted backend with a local NIM without changing the client API;
5. treat model replacement and LoRA evaluation as controlled lifecycle work;
6. translate the stack to Kubernetes; and
7. introduce scale-out only after monitoring demonstrates a need.

That progression is appropriate for an academic infrastructure team. The
gateway, accounting, backend-swap, and evaluation arguments are especially
clear. The documents generally respect a modest operational budget and avoid
presenting high availability or Kubernetes as automatic virtues.

The largest pedagogical gap is an LLM-serving concepts bridge. A reader new to
inference encounters tokens, context length, prefill, decode, KV cache, batching,
precision, quantization, model weights, inference engines, NIM, TTFT, and
inter-token latency across several chapters without first seeing how those
concepts fit together. A short primer near `00-01` would remove many small jumps
later. It should distinguish:

- model weights from an inference engine and from an API server;
- NIM from the model it packages, and LiteLLM from both;
- input/output tokens and the context window;
- prefill from decode, and TTFT from inter-token latency;
- batching/concurrency from model replicas;
- weight memory from KV-cache/activation memory; and
- precision/quantization as capacity/performance/quality choices.

## Learning-objective and activity coverage

| Document | Objective status | Learner activity | Review note |
|---|---|---|---|
| `00-01` Architecture | Met | None (conceptual) | Add a short “trace one request / map one constraint” check and the concepts primer above. |
| `00-02` Getting started | Partly met | Strong: configure, start, smoke, call, mint key, inspect spend, use UI, baseline | Setup omissions make several commands fail in a fresh shell; TLS is optional in the procedure but assumed complete in the conclusion. |
| `00-03` Gateway | Partly met | Strong intent: mint, exhaust, inspect, add/reload | The raw management API examples omit required headers, and adding a model is described rather than exercised with a concrete safe candidate. |
| `00-04` Guardrails | Not met as shipped | Strong: enable and send a blocking probe | The example guardrail is not default-on, so the documented request will not select it. |
| `00-05` Testing | Partly met | Run three suites | The objective promises baselines committed and CI wired; the chapter mostly points elsewhere, and ignored results cannot normally be committed. |
| `00-06` Monitoring | Partly met | Generate load and watch panels | Add a concrete local path (`make monitoring`, URLs, credentials, metric checks) and a central-monitoring checklist. The ledger intentionally is not fed into Prometheus, contrary to the objective wording. |
| `00-07` Operating | Partly met | No real exercise | The runbook is useful, but backup/restore and a small diagnosis drill are missing; some exposure and pinning claims conflict with the manifests. |
| `01-01` Self-hosted NIM | Mostly met | Strong before/start/direct-call/cutover/after sequence | One command loses the Compose overlay; GPU selection and host exposure do not fully match the prose. |
| `01-02` Model replacement | Partly met | Mostly conceptual | It lacks a concrete candidate, runnable comparison, weighting syntax, and a reliable way to distinguish canary backends in monitoring. |
| `01-03` LoRA | Mostly met | Strong worked example | A few stale references remain; “same cost” needs qualification, and the Kubernetes download path is not reproducibly pinned. |
| `02-01` Kubernetes | Not met | Only high-level apply commands | GPU Operator setup, required secrets, ingress, data migration, and acceptance-test URL changes are not walked through. The promise that keys survive is unsupported without a database migration. |
| `03-01` Scale-out | Objective is too strong | One scale command; otherwise conceptual | No Dynamo or autoscaling implementation is shipped. Recast as a decision/concepts chapter or add a runnable follow-on lab. |
| Researcher handout | Good template | Operator customization | Add an explicit guardrail statement when enabled and avoid an unconditional no-prompt-storage promise unless configuration enforces it. |

## Issues to review

Severity meanings:

- **High** — blocks a documented exercise, makes a material claim untrue, or
  creates an unsafe operational expectation.
- **Medium** — an objective or important concept is incomplete, but the reader
  can continue with prior knowledge or investigation.
- **Low** — stale wording, tone, or a useful refinement.

### TR-01 — Direct shell examples do not load `.env` (**High**)

Locations: `00-02` lines 62–67 and 123–128, `00-03`, `01-01` prerequisite
login, and later `$KEY` examples.

`Makefile` includes and exports `.env` for commands run by `make`, but copying
`.env.example` to `.env` does not populate variables in the reader's interactive
shell. A command containing `$LITELLM_MASTER_KEY` or `$NGC_API_KEY` can therefore
send an empty credential even though `make up` worked.

Suggested remedy: establish one convention early, such as `set -a; source .env;
set +a` for the current shell, or show how to extract/use the returned virtual
key without relying on ambient variables. Define `$KEY` at its first use. Note
that sourcing `.env` executes shell syntax, so this assumes the file is trusted
and shell-compatible.

### TR-02 — Fresh-host Python/tool setup is incomplete (**High**)

Locations: `00-02` lines 19–24 and 136–146.

The text says smoke/eval run “in a virtualenv,” but neither the Makefile nor the
tutorial creates one. `make smoke` needs `pytest`; the Python client example
needs `openai`; and `make perf` needs AIPerf or `uvx`. Installing `python3-pip`
alone does not make these commands work.

Suggested remedy: add a small, explicit tool bootstrap (preferably a venv and a
requirements/dev lock file), or state that dependency management is left to the
operator and give exact minimal commands before the first invocation.

### TR-03 — Key/team management `curl` commands omit required headers (**High**)

Location: `00-03` lines 36–53.

The paragraph says all calls use the master-key header, but the copyable commands
do not contain it. They also omit `Content-Type: application/json`. A newcomer
will paste them and receive an auth or request-parsing error.

Suggested remedy: make every command independently runnable, even at the cost of
repetition, or define a small shell helper immediately above the block.

### TR-04 — The shipped guardrail is defined but not selected (**High**)

Locations: `00-04` lines 92–131 and the commented block in
`gateway/litellm-config.yaml`.

LiteLLM guardrails default to `default_on: false`. The example leaves
`default_on: true` commented out, while the chapter says the guardrail applies to
every request and expects an ordinary chat request to be blocked. Starting the
sidecars and uncommenting the block therefore does not complete the exercise.

Suggested remedy: enable `default_on: true` in the tutorial block. Teach
per-request or per-key selection as the explicit alternative. Also use `curl -i`
and include `Content-Type` so the student can actually observe HTTP 400.

Reference: LiteLLM's guardrail quick-start documents `default_on` as false unless
enabled: <https://docs.litellm.ai/docs/proxy/guardrails/quick_start>.

### TR-05 — “Secrets” guardrail scope is broader than the implementation (**Medium**)

Location: `00-04` title and lines 23–25.

The concrete Presidio policy masks credit cards/email and blocks US SSNs. It does
not demonstrate detection of generic API keys, private keys, or institutional
secrets. Presidio can be extended with recognizers, but that work is not shown.

Suggested remedy: call the concrete lab “PII/PHI masking” and identify secret
scanning as a separate recognizer/scanner task, or add a safe example recognizer.

### TR-06 — Perf baselines are described as committed but are ignored by Git (**High**)

Locations: `00-02` lines 143–146, `00-05` lines 42–44,
`tests/perf/README.md` lines 17–21, and `.gitignore` line 6.

`tests/perf/results/` is ignored, so the normal workflow cannot commit the
artifacts the tutorial repeatedly asks the reader to commit. The GitLab example
retains artifacts rather than committing them; the GitHub example omits the
weekly perf job.

Suggested remedy: choose one policy and use it consistently: version selected
baseline summaries in a non-ignored `baselines/` directory, or retain CI
artifacts and stop saying “commit.” Avoid CI jobs that push generated commits
unless that operational choice is explained.

### TR-07 — The testing objective and CI description overstate what is shipped (**Medium**)

Location: `00-05` objective and lines 61–72.

The objective says the reader will wire all suites into CI. The chapter does not
walk through adapting either template. It also says both examples implement
weekly perf with results committed; GitHub explicitly omits weekly perf, while
GitLab stores artifacts.

Suggested remedy: either narrow the objective to “inspect and adapt a CI
template,” or add a short exercise that copies one template into its active
location, configures a dedicated credential and URL, and explains runner network
reachability.

### TR-08 — A normal dedicated CI key cannot run the smoke suite as written (**High**)

Locations: both `ci/` examples and `tests/smoke/test_gateway.py`.

The CI comments recommend a dedicated virtual key, but the smoke suite uses its
credential to call the admin `/spend/logs` endpoint. A normal virtual key should
not have that authority. Supplying the master key makes the test pass but expands
CI's blast radius.

Suggested remedy: split operator/admin accounting checks from user-path smoke
tests, or create a narrowly privileged CI key if LiteLLM supports the required
scope and document it. The spend test should also prove that the current run
created a row; today any old spend row satisfies it.

### TR-09 — Monitoring objective conflates the ledger with Prometheus (**Medium**)

Location: `00-06` objective versus lines 66–74.

The objective says all four layers, including the ledger, are fed into
Prometheus/Grafana. The chapter correctly argues that accounting remains in
Postgres and must not be reconstructed from Prometheus. These are different
outcomes.

Suggested remedy: say “connect three metric layers to Prometheus/Grafana and
verify the fourth, authoritative ledger separately.” If a Grafana Postgres view
is an optional exercise, show creation of a read-only database user rather than
pointing Grafana at operator credentials.

### TR-10 — Kubernetes monitoring omits the gateway (**High**)

Locations: `00-06`, `k8s/monitoring/servicemonitor.yaml`, and
`monitoring/prometheus/prometheus.yml`.

The static Compose scrape file targets `gateway:4000`. The Kubernetes
ServiceMonitor selects only `nim-coder` and `nim-general`; it does not discover
the `litellm` Service. Thus the Kubernetes path does not ship the documented
gateway scrape.

Suggested remedy: add a gateway ServiceMonitor endpoint (or expand the existing
object carefully) and explain any Prometheus Operator label selector required by
the institution's installation.

### TR-11 — The monitoring chapter needs a concrete first lab (**Medium**)

Location: `00-06` lines 76–88.

The only command is a perf run beneath two comment-only instructions. A reader
does not get the satisfying Phase-0 exercise of starting the bundled stack,
opening Grafana, checking targets, curling `/metrics/`, and mapping one PromQL
query to one panel.

Suggested remedy: add a local path using `make monitoring`, the pilot Grafana
credential warning, Prometheus target checks, `curl -L` against gateway metrics,
and one “generate load, observe counter/latency movement” task. Follow it with a
separate central-Prometheus checklist.

### TR-12 — Operational exposure and pinning rules conflict with manifests (**High**)

Locations: `00-07` lines 24–37, `docker-compose.selfhost.yaml`, and both NIM
Kubernetes manifests.

The operating chapter says backends are never exposed and every image is pinned.
The Compose NIM publishes `8000:8000` on all host interfaces for the lab, and the
NIM images use `:latest`. `01-01` does tell the reader to firewall/remove the
port, and manifest comments tell them to pin, but the unconditional operating
claims remain false.

Suggested remedy: distinguish “safe end state” from “temporary lab exposure,”
bind direct-test ports to `127.0.0.1`, and say core service images are pinned
while NIM tags are placeholders that must be replaced before use.

### TR-13 — `make down` does not reliably mean “stop everything” (**High**)

Location: `Makefile` `down` target.

The target invokes only the base Compose file with the monitoring/TLS profiles.
Services introduced only by the guardrail and self-host overlays are not in that
Compose model and may remain as project orphans. This is especially surprising
after `make selfhost` or `make guardrails`.

Suggested remedy: add explicit `down`, `down-selfhost`, and `down-guardrails`
targets, or have the all-down target include every overlay and profile. Explain
that volumes are retained.

### TR-14 — One self-host logging command drops the overlay (**High**)

Location: `01-01` lines 55–58.

`docker compose logs -f nim-coder` reads only `docker-compose.yaml`, which does
not define `nim-coder`. Compose does not remember the `-f` files used by a prior
command.

Suggested remedy: repeat both `-f` arguments, add a `make logs-nim` target, or set
`COMPOSE_FILE` once for the lab.

### TR-15 — Compose grants NIM all GPUs while the lesson says one (**Medium**)

Locations: `docker-compose.selfhost.yaml` for `nim-coder` and `nim-general`.

Both services reserve `count: all`. The prose presents each lab as a one-GPU
deployment, and the Kubernetes equivalents request exactly one GPU. On a
multi-GPU host the Compose example can expose or consume more devices than the
student expects and makes simultaneous labs contend.

Suggested remedy: use `count: 1` for the worked examples and document explicit
device IDs/tensor-parallel sizing as the multi-GPU variation.

### TR-16 — Model-replacement exercise is not concrete enough to complete (**High**)

Location: `01-02` Act 1 and Act 2.

The chapter never supplies a known candidate model stanza, does not show how to
run the existing golden harness against both aliases, and says “weight the
split” without showing LiteLLM's `weight` configuration. `$KEY` is undefined.
For a reader new to inference, this turns the central lifecycle lab into design
advice rather than an exercise.

Suggested remedy: provide one replaceable, date-stamped example candidate (with
a prominent instruction to verify catalog availability), duplicate a small
golden probe for both names, show two matching perf commands, and include the
exact weighted-canary syntax and rollback edit.

### TR-17 — `requested_model` cannot distinguish two canary backends (**High**)

Location: `01-02` lines 94–105 and `01-03` lines 193–202.

During a canary, both deployments receive the same user-facing alias, so the
gateway's `requested_model` label remains `coder` (or `general`). Grouping by it
cannot reveal incumbent versus candidate traffic. The docs need a deployment or
served-model identifier (`model_id` or another verified label), plus backend/NIM
metrics, to observe the split.

Suggested remedy: verify the pinned LiteLLM metric labels and add a canary panel
that distinguishes deployments. Keep `requested_model` for user-facing demand,
not backend attribution.

### TR-18 — The recommended source for task-specific eval prompts is unclear (**Medium**)

Location: `01-02` lines 45–53.

Earlier chapters emphasize that prompts are not stored by default, but this
chapter tells the operator to build an eval set from exported real usage. It
does not say where those prompts come from or address researcher consent,
purpose limitation, or review before committing research material to Git.

Suggested remedy: ask researchers to contribute representative prompts or use a
consented, curated collection workflow. Treat Presidio as one review step, not
as authorization to reuse or commit prompt data.

### TR-19 — LoRA chapter contains stale references and an overbroad cost claim (**Medium**)

Locations: `01-03` infrastructure header, line 31, and lines 189–191.

`nim-general` is a real profiled service, not a commented service; “doc 04” is a
stale reference to the self-hosting chapter; and an adapter is not literally
cost-identical if it reduces throughput or increases latency. It does avoid a
second copy of the base weights and usually has similar fixed GPU allocation.

Suggested remedy: update the references and describe cost as “same base-weight
deployment and broadly similar capacity cost, to be confirmed by the perf
comparison.” Include accounting prices in the example gateway stanzas.

### TR-20 — Kubernetes secret setup is incomplete (**High**)

Locations: `02-01` lines 43–50, `k8s/README.md` lines 18–32, and both NIM
manifests.

The chapter refers to four secret commands, but the README creates one generic
secret containing only `NVIDIA_API_KEY`, `LITELLM_MASTER_KEY`, and
`POSTGRES_PASSWORD`. The NIM pods require `NGC_API_KEY`, and both reference an
`ngc-registry` image-pull secret that the deploy block never creates. Applying
the NIM overlay as documented will not produce a running pod.

Suggested remedy: include `NGC_API_KEY` in `llm-secrets`, show the
`docker-registry` secret command, use `--password-stdin` where possible in the
Compose path, and add verification commands that do not print secret values.

### TR-21 — Kubernetes migration promises key continuity without moving data (**High**)

Location: `02-01` lines 29–35 and 74–81.

The Kubernetes base creates a new PostgreSQL PVC and a new Open WebUI PVC. The
chapter does not migrate the Compose Postgres volume or WebUI data, nor point
both deployments at an existing managed database. Therefore existing gateway
keys, spend history, UI accounts, and chats do not automatically survive, even
though the chapter says users' keys remain untouched.

Suggested remedy: add a migration decision before deployment:

- preferred: move LiteLLM to managed PostgreSQL first, verify Compose against
  it, then point Kubernetes at the same database during cutover; or
- document `pg_dump`/restore, maintenance window, validation, and rollback.

Treat WebUI state separately. Add backup/restore to `00-07`; it is currently the
largest missing day-2 sysadmin responsibility.

### TR-22 — Kubernetes objective is not supported by a complete lab (**High**)

Location: `02-01` learning objective and lines 37–55.

The objective includes standing up the GPU Operator and migrating the service.
The chapter provides neither a pinned Helm command/values check nor an Ingress
example, full secret setup, namespace-aware status checks, ConfigMap rollout
steps, or a concrete `GATEWAY_URL=... make smoke` acceptance command. It also
calls the out-of-band ConfigMap creation a direct mount of the same source file.

Suggested remedy: make `02-01` an ordered lab with checkpoints: prerequisites,
GPU allocatable check, secrets, ConfigMap, base status, data migration, NIM
status, gateway routing update, temporary port-forward test, TLS Ingress, suites,
DNS cutover, and rollback. Include WebUI in the component list or explicitly
defer it.

### TR-23 — The first scale-out command is namespace- and storage-incomplete (**High**)

Locations: `03-01` lines 25–32 and `k8s/nim/nim-coder.yaml`.

`kubectl scale deployment nim-coder --replicas=2` omits `-n llm-service`. More
importantly, both replicas mount one `ReadWriteOnce` cache PVC. Across multiple
GPU nodes, the second pod may be unschedulable or unable to mount the volume;
the chapter presents multi-node scheduling as the reason to adopt Kubernetes.
An ordinary Service also balances connections, not a guaranteed new pod for
every HTTP request when clients reuse keep-alive connections.

Suggested remedy: teach the replica storage pattern first (per-replica cache,
RWX storage if appropriate, preloaded node cache, or NIM Operator cache
management), include the namespace, and describe Service balancing without
promising strict request round-robin.

### TR-24 — Phase 3 learning objective promises an implementation that is absent (**High**)

Location: `03-01` learning objective and infrastructure note.

The chapter says the learner will adopt Dynamo and queue-driven autoscaling, but
the repository intentionally ships neither. The text is a useful conceptual
roadmap, not a lab that can meet that objective.

Suggested remedy: change the objective to “identify the signals, explain the
options, and design the next experiment,” with a paper exercise based on a
sample latency/queue graph. If runnable Dynamo/KEDA manifests are added later,
make that a separate advanced lab with version-pinned upstream instructions.

### TR-25 — Kubernetes LoRA init is convenient but not reproducible (**Medium**)

Location: `k8s/nim-lora/nim-general.yaml` init container.

The pod installs the latest `huggingface_hub` from PyPI and downloads the moving
head of a Hugging Face repository at startup. That is approachable for a lab but
not reproducible, supply-chain stable, or compatible with many restricted
academic clusters. `kubectl cp` directly into a NIM pod is also a fragile way to
manage a PVC.

Suggested remedy: label the init container as lab-only, pin package and adapter
revision/checksum, and describe a production path using a reviewed artifact in
institutional object storage/registry plus a dedicated PVC-population Job.

### TR-26 — Backup, restore, and retention deserve an operating section (**High**)

Locations: `00-07`, Postgres/WebUI manifests, and monitoring/accounting chapters.

The service's durable state includes keys, budgets, spend records, UI accounts,
and possibly chats. The manifests mention `pg_dump` only in a comment. There is
no documented backup owner, frequency, restore test, retention period, or
privacy-aware deletion process.

Suggested remedy: add a minimal pilot policy and a restore drill. Distinguish
LiteLLM/Postgres state from Open WebUI state, and state whether chats are stored
by the UI even though LiteLLM does not store prompt bodies in spend logs.

### TR-27 — User-facing logging promise should be configuration-backed (**Medium**)

Locations: `00-03` lines 103–107 and `researcher-handout.md` lines 51–56.

LiteLLM does not store prompt/response content in spend logs by default, but its
UI can change that behavior. The handout makes an unconditional promise while
the repository does not explicitly set `store_prompts_in_spend_logs: false` or
describe a configuration audit. Open WebUI may separately retain chat history.

Suggested remedy: set the LiteLLM option explicitly, explain the UI's separate
storage, and give operators a pre-publication checklist for the handout. Current
LiteLLM logging documentation confirms content storage is off by default but
configurable: <https://docs.litellm.ai/docs/proxy/ui_logs>.

### TR-28 — Tone is engaging but occasionally too slogan-heavy for an ops guide (**Low**)

Locations throughout, especially phrases such as “load-bearing,” “the serving
layer grows a brain,” “quiet luxury,” “not vibes,” “cheapest availability
monitor,” and repeated “users noticed nothing.”

Most prose is natural, direct, and well matched to an academic sysadmin. The
occasional informal phrase adds personality, but repeated certainty can obscure
conditions and failure modes. “Users noticed nothing,” for example, is an
acceptance criterion, not a guaranteed outcome; model behavior can change even
when the API contract does not.

Suggested remedy: retain the conversational voice, but prefer observable claims
and explicit conditions in procedures. Reduce marketing-like superlatives and
use “the client configuration is unchanged” where that is the precise claim.

### TR-29 — A few repository references are stale (**Low**)

- `01-03` says “doc 04” for the self-hosted NIM chapter.
- Its infrastructure header calls `nim-general` commented rather than profiled.
- The Grafana dashboard comment points to `docs/06-monitoring.md`; the file is
  `docs/00-06-monitoring.md`.
- `02-01` omits the shipped WebUI from its `k8s/base/` component summary.
- `k8s/README.md` comments “gateway + postgres” although base also includes
  WebUI.

Suggested remedy: fix these mechanically and add a lightweight Markdown link
checker plus terminology/filename grep to CI.

## Suggested order of fixes

1. Fix copy/paste blockers: environment loading, Python dependencies, management
   API headers, guardrail `default_on`, self-host log command, and `$KEY`.
2. Repair false operational promises: result retention, CI credential scope,
   exposure/pinning, `make down`, and backup/logging language.
3. Rebuild `02-01` as a real migration lab, including complete secrets and
   database/UI state migration.
4. Correct canary observability and make `01-02` a worked no-GPU exercise.
5. Add the LLM-serving concepts primer and hands-on monitoring lab.
6. Recast Phase 3 as conceptual until runnable infrastructure is intentionally
   added.
7. Finish with stale references and tone edits.

## Static infrastructure observations that looked sound

The review found several areas where code and explanation align well:

- LiteLLM and PostgreSQL are separated cleanly, and the config file is kept as
  the routing source of truth.
- Compose health dependencies and the distinction between gateway liveness and
  Kubernetes readiness are explained thoughtfully.
- Hosted and self-hosted aliases use the same OpenAI-compatible gateway path.
- The self-host overlay separates “backend running” from “backend receiving
  traffic,” which is a valuable operational lesson.
- Presidio sidecars are opt-in and similarly separate running from enforcement.
- The smoke/eval/perf split is conceptually strong, and generated-code evals
  clearly warn that subprocess containment is not a security sandbox.
- Prometheus is correctly treated as operational telemetry rather than the
  billing ledger.
- Kubernetes Services keep model backends cluster-internal, and the NIM probes
  allow long initial model loading.
- The LoRA base/adapter compatibility checks and dynamic refresh explanation are
  unusually concrete for an introductory repository.
- The existing infrastructure audit records valuable live evidence and clearly
  identifies Phase 3 as intentionally unimplemented.

