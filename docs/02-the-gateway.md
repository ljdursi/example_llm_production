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
# key with a monthly budget, restricted to one model, auto-expiring
curl http://localhost:4000/key/generate -d '{
  "user_id": "alice", "max_budget": 20, "budget_duration": "30d",
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

Budgets are denominated in dollars against LiteLLM's per-model price table.
For self-hosted models "cost" is notional — set your own per-token prices in
the model stanza (`input_cost_per_token`/`output_cost_per_token`) to keep
budgets meaningful as fair-use accounting, which for an academic service is
usually the real goal.

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
is [05-monitoring.md](05-monitoring.md).

## Routing: adding models and backends

Covered inline in `gateway/litellm-config.yaml` (read it now if you haven't),
but the three moves worth naming:

1. **New model** = new `model_name` stanza. Restart the gateway
   (`docker compose restart gateway`); clients see it in `/v1/models`
   immediately. This is how "summarizer" and multi-modal models arrive later —
   routine, not a project.
2. **New backend for an existing model** = change `api_base`. This is the
   Phase 1 migration ([03-swapping-in-self-hosted-nim.md](03-swapping-in-self-hosted-nim.md)).
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
  (built on Envoy Gateway); Kubernetes-native, policy-as-CRDs, token-aware
  rate limiting. The natural landing spot if your institution standardizes on
  Envoy. No built-in spend ledger, so you'd own accounting.
- **Kong AI Gateway / Apache APISIX** — established API gateways with LLM
  plugins; right if one is already deployed institutionally.

Because clients only ever saw "OpenAI API + a base URL + a key," a gateway
swap is invisible to users — the same trick the gateway plays for backends
applies to the gateway itself. Keep your model-name conventions and key
inventory portable (they're in git and Postgres respectively) and the exit
cost stays low.
