# Using the Research LLM Service

*(Template: replace the bracketed values, delete this line, and hand it out —
as a wiki page, an email, or a PDF. Everything researchers need is on this
page; everything else is your problem, which is the service's whole point.)*

## What you get

- **Chat in the browser:** [https://chat.llm.YOUR.EDU] — sign in and pick a
  model from the dropdown.
- **An API key** for use from code, notebooks, and IDE assistants, sent to
  you when you're onboarded. Treat it like a password: it's yours alone, it's
  revocable, and usage on it is attributed to you.

## The models

| Name to use | Good for |
|---|---|
| `coder` | code generation, review, debugging, research software questions |
| `general` | general Q&A, writing help, summarization |

(The list at any moment: `GET /v1/models`, or the chat UI's dropdown. Names
are stable — the models behind them may be upgraded, and we announce that.)

## From Python

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://llm.YOUR.EDU/v1",   # instead of OpenAI's
    api_key="sk-...your key...",
)
reply = client.chat.completions.create(
    model="coder",
    messages=[{"role": "user", "content": "Vectorize this loop: ..."}],
)
print(reply.choices[0].message.content)
```

Any tool that speaks the OpenAI API works the same way — set base URL, key,
and model name. For IDE assistants (Continue.dev, Cline, aider, ...), choose
"OpenAI-compatible" as the provider and fill in the same three values.

## The rules, plainly

- **Budgets & rate limits.** Your key has a monthly budget and a
  requests-per-minute cap [state yours, e.g. "$20/month, 60 req/min"]. Hit
  them and requests return errors until the window resets; if your research
  legitimately needs more, ask — that's a conversation, not a workaround.
- **What we log.** Request *metadata*: who, which model, when, token counts,
  cost. **We do not store your prompts or the model's replies.**
- **Where your data goes.** [Pick one: "Prompts are processed on university
  hardware and do not leave campus." / "Prompts to these models are currently
  processed by a hosted provider off-campus (NVIDIA); do not send data with
  residency or confidentiality restrictions — ask us first."]
- **Don't share keys.** Lab-shared workflows get their own key with a shared
  budget — ask; it's one command on our side.
- **Best effort, business hours.** This is a pilot: no pager, no SLA. If it's
  down, we'll see it next morning at the latest. Deadlines-week concerns →
  talk to us early.

## Help

Contact: [service email / chat channel]. Useful in a report: the model name,
roughly when, and the error message. Never include your API key.

---

**◀ Prev** [03-01 · Scaling out](03-01-scaling-out.md) · **[Up](../README.md)**
