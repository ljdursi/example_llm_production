"""Golden-answer quality evaluation.

Where smoke tests ask "does the service respond?", these ask "is the model
behind a given name still *good enough*?" — which matters exactly when you
change what's behind a name: swapping hosted → self-hosted, upgrading a NIM
version, trying a smaller/quantized model to save GPU memory.

    make eval

Each line of golden.jsonl is one probe:
    model             which gateway model name to test
    prompt            what to send
    must_contain      all of these substrings must appear in the reply
    must_contain_any  at least one of these must appear
    check: "python_defines_working_function"
                      extract Python from the reply, exec it in a sandboxed
                      namespace, and run `cases` against `function`

Grow golden.jsonl with prompts from YOUR researchers' real use — five probes
per model that reflect actual work beat five hundred generic ones. When you
outgrow substring checks, see README.md here for NeMo Evaluator and
lm-evaluation-harness, which run standardized benchmarks against the same
OpenAI-compatible endpoint.
"""

import json
import os
import pathlib
import re
import urllib.request

import pytest

_env = pathlib.Path(__file__).parents[2] / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:4000")
KEY = os.environ["LITELLM_MASTER_KEY"]
GOLDENS = [
    json.loads(line)
    for line in (pathlib.Path(__file__).parent / "golden.jsonl").read_text().splitlines()
    if line.strip()
]


def ask(model: str, prompt: str) -> str:
    req = urllib.request.Request(
        f"{GATEWAY}/v1/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,  # evals should be as deterministic as the backend allows
                "max_tokens": 500,
            }
        ).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def extract_python(reply: str) -> str:
    blocks = re.findall(r"```(?:python)?\n(.*?)```", reply, re.DOTALL)
    return blocks[0] if blocks else reply


@pytest.mark.parametrize(
    "g", GOLDENS, ids=[f"{g['model']}:{g['prompt'][:40]}" for g in GOLDENS]
)
def test_golden(g):
    reply = ask(g["model"], g["prompt"])

    for needle in g.get("must_contain", []):
        assert needle in reply, f"expected {needle!r} in reply:\n{reply}"

    if any_of := g.get("must_contain_any"):
        assert any(n in reply for n in any_of), f"expected one of {any_of} in reply:\n{reply}"

    if g.get("check") == "python_defines_working_function":
        namespace: dict = {}
        exec(extract_python(reply), namespace)  # noqa: S102 — model output, run only in CI/dev
        fn = namespace[g["function"]]
        for case in g["cases"]:
            assert fn(*case["args"]) == pytest.approx(case["expect"])
