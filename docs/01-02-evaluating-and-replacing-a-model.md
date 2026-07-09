# Evaluating and replacing a model

Models don't stand still. A better one ships, a cheaper one appears, or the one
you're using hits end-of-life — hosted ids at build.nvidia.com reach EOL and
start returning **HTTP 410 Gone** (the note in `gateway/litellm-config.yaml` is
not hypothetical). Sooner or later you will point one of your user-facing names
at a different model, and the question is how to do it *without* guessing whether
the new model is actually better and *without* a disruptive flag-day cutover.

This is a lifecycle activity, not an infrastructure phase — which is why it sits
here and not in the Phase 0–3 table. **The procedure is phase-independent:** the
candidate can be another hosted endpoint, a NIM you run, or a vLLM backend, and
the steps are identical. This page uses a **second hosted model** as the
candidate, so the whole exercise runs with **no GPU** — the same reason Phase 0
does. For a worked, GPU-based instance of this same procedure where the candidate
is a **LoRA fine-tune of a model you already serve**, see
[01-03-comparing-fine-tunes-with-lora.md](01-03-comparing-fine-tunes-with-lora.md).

Two acts with a decision in between: **evaluate**, decide, **migrate**.

## Act 1 — Evaluate the candidate

**Add the candidate under a *new* name, not the one in use.** Give it its own
`model_list` stanza — say `coder-next` — pointing at the model you're
considering. Now you can hit it directly, run suites against it, and let it soak,
while every real user stays on `coder` untouched. (Adding a model is just a new
stanza — see [00-03-the-gateway.md](00-03-the-gateway.md); there's a commented
`coder-next` template in the config to copy.)

```bash
docker compose restart gateway
curl http://localhost:4000/v1/models -H "Authorization: Bearer $KEY"   # coder-next now listed
```

**Evaluate against *your* use case, with *your* data.** A leaderboard score on
MMLU tells you almost nothing about whether a model writes the kind of research
code your users need. The signal that matters comes from *your* prompts:

- Build a task-specific eval set from **real, anonymized usage**. You already
  have the tool to anonymize it — run the exported prompts through Presidio
  ([00-04-guardrails.md](00-04-guardrails.md)) before they land in a fixture. This is
  the single highest-leverage thing you can do, and it compounds: the set grows
  with your users and becomes the acceptance gate for every future swap.
- Run the comparison. This repo's `tests/eval/` goldens are the regression
  floor; for a head-to-head you want richer scoring:
  - **[NeMo Evaluator](https://github.com/NVIDIA-NeMo/Evaluator)** (NVIDIA OSS)
    — custom eval sets and **LLM-as-judge**, which is what you need for
    open-ended output (code quality, summary faithfulness) where there's no
    single golden string.
  - Alternatives, documented so nothing locks you in:
    **[promptfoo](https://www.promptfoo.dev/)** is purpose-built for exactly
    this — side-by-side "model A vs model B on my prompts," with a diff view and
    a CI mode; **lm-evaluation-harness** for standardized academic benchmarks
    when you *do* want them.
  - Point the eval at each name in turn (`coder` vs `coder-next`) — same suite,
    two backends, like-for-like.

**Score three axes, not one.** Quality alone doesn't make the decision:

| Axis | How | Source |
|---|---|---|
| Quality | eval set + LLM-as-judge, on *your* tasks | this page / `tests/eval/` |
| Performance | TTFT, inter-token latency, throughput at your concurrency | `make perf MODEL=coder-next` — [00-05](00-05-testing-performance-and-quality.md) |
| Cost | per-token price × your token mix | the pricing you set in [00-03](00-03-the-gateway.md) |

## The decision gate

**Write the acceptance criteria down *before* you look at the results.** "≥ the
incumbent's pass rate on the eval set, TTFT within 20%, and cheaper per request"
is a decision; eyeballing the numbers afterward and rationalizing is not — it's
how you talk yourself into a regression. Fix the bar first, then run.

And accept the honest outcome: **a model that's slightly worse on quality but
markedly cheaper or faster is often the right call** for an academic service
whose real constraint is a fixed budget across many users. That's a judgment,
but a judgment made against numbers you committed to in advance.

## Act 2 — Migrate

Once the candidate clears the bar, move traffic deliberately. This generalizes
the cutover you did in Phase 1 ([01-01-swapping-in-self-hosted-nim.md](01-01-swapping-in-self-hosted-nim.md));
the mechanics are the gateway's, so no user reconfigures anything.

1. **Canary.** Give the real `coder` name *two* stanzas — the incumbent and the
   candidate — so the gateway load-balances across them (weight the split if you
   want a smaller first dose). A fraction of live traffic now hits the new model.
2. **Watch.** With real traffic on it, watch the Grafana dashboards and the spend
   logs ([00-06-monitoring.md](00-06-monitoring.md)): error rate, latency, and
   per-model cost, split out by the `requested_model` label. This is the check
   your offline eval can't give you.
3. **Cut over.** When the canary looks good, remove the incumbent stanza (or
   repoint `api_base`) and `docker compose restart gateway`. The name is
   unchanged; users notice nothing.
4. **Keep a rollback ready.** The config is in git, so rollback is not a
   scramble — it's `git revert` (or restore the previous stanza) and restart.
   Decide your rollback trigger *before* the cutover, same as the acceptance
   bar.
5. **Retire and record.** Drop the `coder-next` name, update the eval baselines
   and perf CSVs to the new model, and add/adjust model names in the smoke
   suite's `test_models_are_listed` in the same commit — so the tests always
   match reality.

## What to tell your users

If the model behind a name changes materially, say so — a one-line changelog
entry in the researcher handout. Most swaps are invisible and need no notice;
but a capability or behavior shift (a different model family, a much smaller
model) can change results a researcher is depending on, and silent substitution
on research work is a trust cost, not just a technical one. The
`litellm_settings.fallbacks` caveat from [00-03](00-03-the-gateway.md) applies here
too: decide deliberately when quiet substitution is acceptable.

---

**◀ Prev** [01-01 · Self-hosted NIM](01-01-swapping-in-self-hosted-nim.md) · **[Up](../README.md)** · **Next ▶** [01-03 · Comparing fine-tunes (LoRA)](01-03-comparing-fine-tunes-with-lora.md)
