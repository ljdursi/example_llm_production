# The gateway: auth, accounting, budgets, and routing

The gateway ([LiteLLM Proxy](https://docs.litellm.ai/docs/simple_proxy)) is the
component your users experience as "the service." This page covers operating
it. Its configuration is `gateway/litellm-config.yaml` — heavily commented,
kept in git, and deliberately the single source of truth (`STORE_MODEL_IN_DB`
is off so nobody can drift the config from a web UI; changes are commits).

## The mental model

```
request → [authn: valid key?] → [authz/budget: allowed? under budget?]
        → [route: model name → backend] → [forward + stream back]
        → [account: log user, model, tokens, cost to Postgres]
```

Two kinds of credentials, never to be confused:

- **Master key** (`LITELLM_MASTER_KEY`): admin. Mints keys, reads spend,
  changes everything. Held by operators only.
- **Virtual keys**: minted per user (or per *application* — the chat UI, an
  eval runner, a course's shared account), each with optional budgets,
  expiry, and model restrictions. This is what you hand out.

## User and key management

`make create-key USER_ID=alice BUDGET=20` wraps the API; the underlying calls
(all with `Authorization: Bearer $LITELLM_MASTER_KEY`):

```bash
# key with a monthly budget, rate limits, restricted to one model, auto-expiring
curl http://localhost:4000/key/generate -d '{
  "user_id": "alice", "max_budget": 20, "budget_duration": "30d",
  "rpm_limit": 60, "tpm_limit": 100000,
  "models": ["coder"], "duration": "180d",
  "metadata": {"group": "smith-lab"}
}'

curl http://localhost:4000/key/delete -d '{"keys": ["sk-..."]}'   # revoke: immediate

# teams: shared budgets for a lab or a course
curl http://localhost:4000/team/new -d '{"team_alias": "smith-lab", "max_budget": 200}'
# then mint keys with "team_id" and members draw from the shared budget
```

There's also an admin web UI at `http://localhost:4000/ui` (log in with the
master key) for doing all of this by clicking — handy, but learn the API
first: your onboarding automation will use it.

Budgets and rate limits solve different problems, so set both: a budget is a
*monthly* backstop, but the runaway-script-at-2am problem is handled by
`rpm_limit`/`tpm_limit` (requests and tokens per minute, enforced per key) —
those are what stop one user from monopolizing the service *right now*.

Budgets are denominated in dollars against LiteLLM's per-model price table —
and LiteLLM has **no price for these model names** (it doesn't recognize custom
aliases, nor arbitrary hosted/self-hosted endpoints). With no price, every
request costs $0.00, `/spend` logs $0.00, and a dollar `max_budget` never binds
— budgets silently do nothing. So you must set per-token prices in the model
stanza (`input_cost_per_token`/`output_cost_per_token`) to make budgets
meaningful as fair-use accounting, which for an academic service is usually the
real goal. **This repo ships deliberately-fake illustrative prices** on both
models (see the pricing note in `gateway/litellm-config.yaml`) so the budget
machinery is live out of the box; replace them with your own notional credits
or, once self-hosting, real amortized cost.

Verify enforcement actually works (do this after any pricing change) — mint a
tiny budget and spend it:

```bash
make create-key USER_ID=budget-test BUDGET=0.02      # a few requests' worth
# fire a handful of completions with the returned key; watch key spend climb:
curl -s "http://localhost:4000/key/info?key=sk-..." \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | python3 -m json.tool | grep spend
# once spend ≥ budget, further requests return HTTP 400 with a budget message.
```

## Usage accounting

Everything is queryable with the master key:

```bash
curl http://localhost:4000/spend/logs                        # per-request log
curl "http://localhost:4000/spend/logs?user_id=alice"        # one user
curl http://localhost:4000/global/spend/report?group_by=model_name
```

For reporting (the quarterly "who used what" slide), hit these from a cron
job and land the results wherever you keep such things; the data is also just
rows in the `db` Postgres if you'd rather point a BI tool at it. This is the
service's *billing-grade* usage record; the Prometheus side of observability
is [00-06-monitoring.md](00-06-monitoring.md).

Worth knowing before your privacy office asks: by default the spend log stores
**metadata** — user, key, model, token counts, cost, timestamps — not prompt or
response content. (LiteLLM *can* log message content to external stores if you
turn such callbacks on; don't, unless you've decided to and told your users.)
State this in whatever you hand researchers — it's usually the first question.

## Routing: adding models and backends

Covered inline in `gateway/litellm-config.yaml` (read it now if you haven't),
but the three moves worth naming:

1. **New model** = new `model_name` stanza. Restart the gateway
   (`docker compose restart gateway`); clients see it in `/v1/models`
   immediately. This is how "summarizer" and multi-modal models arrive later —
   routine, not a project.
2. **New backend for an existing model** = change `api_base`. This is the
   Phase 1 migration ([01-01-swapping-in-self-hosted-nim.md](01-01-swapping-in-self-hosted-nim.md)).
3. **Two stanzas, same `model_name`** = load balancing across both, which
   also gives you zero-downtime migrations and simple fallback
   (`litellm_settings.fallbacks` can chain models — e.g. retry `coder`
   requests on `general` if the coder backend is down; decide deliberately
   whether silent substitution is acceptable for research use).

## When you outgrow it, or want CNCF alignment

LiteLLM's sweet spot is exactly this: single-team-operated, config-file-driven,
batteries included. Signals you've outgrown it: you need institutional SSO on
every request path with real policy (start with LiteLLM's OIDC support first),
gateway throughput itself becomes a bottleneck, or platform/networking teams
want the LLM path on their standard proxy stack. The alternatives:

- **[Envoy AI Gateway](https://aigateway.envoyproxy.io/)** — CNCF ecosystem
  (built on Envoy Gateway), and production-mature: v1.0 GA since mid-2026 with
  stable CRDs. Kubernetes-native, policy-as-CRDs, token-aware rate limiting
  and quota as core features. The natural landing spot if your institution
  standardizes on Envoy. No built-in spend ledger, so you'd own accounting.
- **Kong AI Gateway / Apache APISIX** — established API gateways with LLM
  plugins; right if one is already deployed institutionally. (Caveat: several
  of Kong's advanced AI features are enterprise-tier; APISIX's ai-proxy
  including token-based rate limiting is OSS.)

Because clients only ever saw "OpenAI API + a base URL + a key," a gateway
swap is invisible to users — the same trick the gateway plays for backends
applies to the gateway itself. Keep your model-name conventions and key
inventory portable (they're in git and Postgres respectively) and the exit
cost stays low.

---

**◀ Prev** [00-02 · Getting started](00-02-getting-started.md) · **[Up](../README.md)** · **Next ▶** [00-04 · Guardrails](00-04-guardrails.md)
