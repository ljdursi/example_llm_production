# Getting started: Phase 0 in an afternoon

By the end of this page you'll have a running multi-user LLM service — auth,
accounting, chat UI, tests — with zero GPUs, on any machine with Docker.

## 1. Get an upstream API key

Create an account at [build.nvidia.com](https://build.nvidia.com) and generate
an API key (free tier is fine for a pilot). This key is the *gateway's*
upstream credential; researchers never see it. Browse the catalog while you're
there — every model card shows a hosted OpenAI-compatible endpoint and the
exact model id string, which is what `gateway/litellm-config.yaml` references.

## 2. Configure and start

```bash
cp .env.example .env
# edit .env: paste NVIDIA_API_KEY, and generate the two secrets as the comments describe
make up
```

Three containers start (peek at `docker-compose.yaml` — it's short and every
service is commented):

- **gateway** (LiteLLM) on `:4000` — the service itself
- **db** (Postgres) — keys, users, spend logs
- **webui** (Open WebUI) on `:8080` — chat interface

## 3. Prove it works

```bash
make smoke
```

Six tests run (read `tests/smoke/test_gateway.py` — it's a tour of the
service's guarantees): the gateway is alive, both models are advertised, a bad
key is rejected, a real completion round-trips through each of the two models,
and the spend log recorded it.

Then try it as a user would:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "coder", "messages": [{"role": "user", "content": "Write a Python one-liner to sum a file of integers."}]}'
```

Note what you did *not* specify: anything about build.nvidia.com. You asked
the *service* for the *model name* `coder`. That indirection is the whole
architecture — see [00-architecture.md](00-architecture.md).

## 4. Put it on the network: TLS

(Evaluating alone on a laptop? Skip ahead and come back — but this step comes
*before* the first real user, not after, because API keys must never cross a
network unencrypted.)

The stack includes a TLS front door — Caddy, behind a compose profile — that
terminates HTTPS and forwards to the gateway and chat UI, fetching and
renewing certificates automatically:

```bash
# in .env: set GATEWAY_HOSTNAME and WEBUI_HOSTNAME (DNS must point at this box)
make tls
```

Users get `https://llm.your.edu/v1` and `https://chat.llm.your.edu`; the
plain-HTTP ports never leave the machine — once TLS works, rebind them to
loopback (`"127.0.0.1:4000:4000"` in `docker-compose.yaml`, same for `:8080`)
so the proxy is the only way in. If your institution already fronts services
with its own proxy or load balancer, use that instead and skip the profile —
anything that terminates TLS in front of `:4000` is equivalent. (Certificate
specifics and variations: comments in `tls/Caddyfile` and the `caddy` service.)

One more thing to say out loud before keys go anywhere: in Phase 0, prompts
are forwarded off-campus to the hosted endpoints. Tell users so, and steer
restricted data away until Phase 1 brings the model on-prem (see the data
note in [00-architecture.md](00-architecture.md)).

## 5. Onboard your first researcher

```bash
make create-key USER_ID=alice BUDGET=20     # $20/30 days; omit BUDGET for no cap
```

Copy the `key` field from the output and hand it over with the base URL
([researcher-handout.md](researcher-handout.md) is a template for exactly
this). Any OpenAI-compatible tool now works, e.g.:

```python
from openai import OpenAI
client = OpenAI(base_url="http://your-host:4000/v1", api_key="sk-...")
print(client.chat.completions.create(
    model="coder",
    messages=[{"role": "user", "content": "Vectorize this loop for me: ..."}],
).choices[0].message.content)
```

IDE coding assistants (Continue.dev, Cline, aider, ...) configure the same
way: OpenAI-compatible provider, your base URL, their key, model `coder`.

Check accounting is accruing:

```bash
curl -s http://localhost:4000/spend/logs \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | python3 -m json.tool | head -40
```

## 6. The chat UI

Open http://localhost:8080 and create the first account (it becomes admin).
The model dropdown shows `coder` and `general` — the UI is just another
gateway client and inherits routing and accounting like everyone else.

## 7. Baseline your performance and quality numbers

```bash
make perf    # TTFT / inter-token latency / tokens-per-sec, via AIPerf
make eval    # golden-answer quality probes
```

Commit the perf CSVs from `tests/perf/results/`. These hosted-endpoint numbers
are the baseline you'll compare against when you self-host in Phase 1 —
capturing them *before* you need them is the habit this repo is trying to
teach. (Reading the numbers: [tests/perf/README.md](../tests/perf/README.md).)

## Where you now stand

You're running a real multi-user service: per-user revocable keys, budgets,
full usage accounting, stable model names, TLS at the front door, tests, and
a UI. What you *haven't*
done is operate any GPUs — model quality problems, CUDA drivers, VRAM sizing
are all still someone else's problem while your team learns the service layer.

Next, in whichever order need dictates:

- more users / models → [02-the-gateway.md](02-the-gateway.md)
- your own GPUs → [03-swapping-in-self-hosted-nim.md](03-swapping-in-self-hosted-nim.md)
- wire into your Prometheus/Grafana → [05-monitoring.md](05-monitoring.md)
- upgrades and a troubleshooting runbook → [08-operating.md](08-operating.md)
- something to hand your users → [researcher-handout.md](researcher-handout.md)
