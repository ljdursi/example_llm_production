# Guardrails: keeping PII and secrets out of prompts

Guardrails are the checks that run *around* an LLM call — inspecting the request
before it reaches a model and, optionally, the response before it reaches the
user. This page comes early on purpose: the moment real people send real prompts
(the end of [00-02-getting-started.md](00-02-getting-started.md)), some of them will
paste a spreadsheet of names, a patient record, or an API key into the chat box.
You want a policy for that before it happens, not after.

A deliberate scoping note first. Guardrails are a spectrum, and heavier is not
better for a research pilot:

- **Data-leak guardrails** — detect and mask/redact PII, PHI, secrets in the
  text. Cheap, deterministic, no model inference. **This is the one to turn on
  first**, and what the rest of this page sets up.
- **Safety / topical / jailbreak guardrails** — "don't answer that," "stay on
  topic," "refuse this class of request." Valuable for a *public* chatbot; for
  an internal research tool with named, budgeted users it's usually lower
  priority, and the good implementations cost extra LLM calls (below).

## Where a guardrail lives (and why not in the gateway page)

Unlike auth or accounting — which are intrinsically the gateway's job — a
guardrail can sit in several places, and the heavier ones are *separate services
in the request path*, only loosely coupled to LiteLLM:

```
request → [gateway: authn/budget] → [guardrail check] → [route → backend] → response
                                          │
              in-process hook  ──────────┤ (Presidio, LLM Guard)
              separate service ──────────┘ (NeMo Guardrails, SaaS APIs)
```

That's why guardrails get their own page rather than living in
[00-03-the-gateway.md](00-03-the-gateway.md): the gateway is one *place* you can
enforce them, but the choice of engine is independent, and some engines aren't
gateway-native at all.

## The three choices

| Engine | Runs as | LiteLLM support | Extra LLM calls? | External account |
|--------|---------|-----------------|------------------|------------------|
| **Presidio** (this repo's default) | two sidecar containers | **first-class** (`guardrail: presidio`) | **no** — NER + patterns | none (OSS) |
| **LLM Guard** | in-process Python library | via a custom callback | no (for most scanners) | none (OSS) |
| **NeMo Guardrails** | separate service / Colang app | custom (not native) | **yes** — self-check flows | none (OSS) |

- **Presidio** ([Microsoft/OSS, now `data-privacy-stack`](https://microsoft.github.io/presidio/))
  is the pragmatic default and a genuine first-class LiteLLM guardrail — you turn
  it on declaratively in `gateway/litellm-config.yaml`, same mechanism as any
  other provider. It finds 100+ entity types with spaCy NER, regex, and checksum
  validators, so it adds **no token cost and no second model to host** — exactly
  the objection to running something heavier in a tutorial. The price you pay is
  two small sidecar services.
- **LLM Guard** ([Protect AI/OSS](https://llm-guard.com)) runs *in-process* — no
  extra containers — and bundles more scanner types (prompt-injection, toxicity,
  secrets, ban-topics) than Presidio's PII focus. It isn't a native LiteLLM
  provider, so you wire it as a custom callback. Reach for it if "no extra
  services" matters more than "declarative config," or you want its scanners.
- **NeMo Guardrails** ([NVIDIA/OSS](https://github.com/NVIDIA/NeMo-Guardrails))
  is the graduation path when you need *topical rails*, dialog policy, and
  jailbreak defense expressed in Colang. It's the most capable and the
  heaviest: its self-check and topical flows **make their own LLM calls**, so
  every guarded request can cost 2–3× the inference. Right for a production,
  outward-facing assistant; over-built for a first research pilot.

## Turning on Presidio (the concrete path)

Two steps, deliberately separate — *running* the checker and *enforcing* it —
the same split as the Phase 1 self-host overlay.

**1. Start the sidecars** (opt-in; they're not in the default `make up` stack):

```bash
make guardrails
# = docker compose -f docker-compose.yaml -f docker-compose.guardrails.yaml up -d --wait
```

This starts `presidio-analyzer` and `presidio-anonymizer` and points the gateway
at them (`PRESIDIO_ANALYZER_API_BASE` / `PRESIDIO_ANONYMIZER_API_BASE`). Nothing
is enforced yet — the gateway doesn't call them until you tell it to.

**2. Enable it in the config.** Uncomment the `guardrails:` block at the bottom
of `gateway/litellm-config.yaml` (it's pre-written), then reload:

```bash
docker compose restart gateway
```

The shipped block masks credit cards and emails and *blocks* on US SSNs:

```yaml
guardrails:
  - guardrail_name: "presidio-pii"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"            # scan input; "post_call" also scrubs output
      pii_entities_config:
        CREDIT_CARD:   "MASK"     # → "<CREDIT_CARD>" in the forwarded prompt
        EMAIL_ADDRESS: "MASK"
        US_SSN:        "BLOCK"    # reject the request outright
```

`MASK` replaces the entity with a placeholder before the prompt reaches the
model; `BLOCK` rejects the whole request. `mode` decides *when*: `pre_call`
(input only), `post_call` (also scrub the response), or `logging_only` (mask
only what's written to your logs/Langfuse, pass the real request through).

**Verify enforcement works** — the same discipline as the budget check in
[00-03-the-gateway.md](00-03-the-gateway.md). Masking is invisible in a normal reply,
so test the observable `BLOCK` path: send an SSN and confirm a rejection.

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -d '{"model":"coder","messages":[{"role":"user","content":"my ssn is 078-05-1120"}]}'
# → HTTP 400, a "violated guardrail policy" message — the request never hit a model.
```

By default a guardrail applies to every request. To scope it per key instead
(e.g. only a shared teaching account), omit `default_on` and attach it via the
key's `metadata` — see [LiteLLM's guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/quick_start).

One caveat worth pinning: output **un-masking** has a known bug on the
Anthropic-native `/v1/messages` path. This stack routes over the
OpenAI-compatible path, so it doesn't bite — but if you add that path later,
keep output masking on chat-completions.

## If you'd rather use one of the others

- **LLM Guard** — no native LiteLLM provider, so add a
  [custom-guardrail callback](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail):
  a small Python class whose `async_pre_call_hook` runs your chosen LLM Guard
  scanners over the messages and raises to block. Nothing new in the compose
  file — it's in-process — but you own the class and its dependency.
- **NeMo Guardrails** — run it as its own service (its
  [server](https://github.com/NVIDIA/NeMo-Guardrails) speaks an OpenAI-ish API)
  and either put it *in front of* the gateway, or call it from a custom LiteLLM
  callback. Author your rails in Colang; budget for the extra inference its
  self-check flows add, and give it its own key so that spend shows up in
  accounting. This is a project, not a config edit — which is the point: turn to
  it when the pilot has graduated to a service that needs real dialog policy.

## What to tell your users

Whatever you enable, say so plainly in the researcher handout: what's inspected,
what's masked vs. blocked, and that (per the privacy note in
[00-03-the-gateway.md](00-03-the-gateway.md)) prompt *content* isn't logged by
default. Masking is a safety net, not a license to paste regulated data —
guardrails reduce blast radius, they don't grant compliance.

---

**◀ Prev** [00-03 · The gateway](00-03-the-gateway.md) · **[Up](../README.md)** · **Next ▶** [00-05 · Testing](00-05-testing-performance-and-quality.md)
