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
                      extract Python from the reply and execute it in a
                      SUBPROCESS with a timeout, running `cases` against
                      `function`. Note this is containment (a hung or crashing
                      snippet can't take the test run down), NOT a sandbox —
                      the code runs with your privileges. Run evals from a
                      dev box or CI runner you'd be comfortable running a
                      stranger's script on, and keep probes simple enough
                      to review.

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
import subprocess
import sys
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


# Driver run in a child process: reads {code, function, cases} on stdin,
# executes the model's code, applies the cases, writes results as JSON.
# Isolation from the test process is containment, not security (see module
# docstring) — the win is that an infinite loop or sys.exit() in model output
# becomes a clean test failure instead of a wedged pytest.
_RUN_CASES_DRIVER = """
import json, sys
spec = json.load(sys.stdin)
ns = {}
exec(spec["code"], ns)
fn = ns[spec["function"]]
print(json.dumps([fn(*case["args"]) for case in spec["cases"]]))
"""


def run_cases_in_subprocess(code: str, function: str, cases: list) -> list:
    proc = subprocess.run(
        [sys.executable, "-c", _RUN_CASES_DRIVER],
        input=json.dumps({"code": code, "function": function, "cases": cases}),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"model code failed to define a working {function!r}:\n{proc.stderr}"
    )
    return json.loads(proc.stdout)


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
        results = run_cases_in_subprocess(extract_python(reply), g["function"], g["cases"])
        for case, got in zip(g["cases"], results):
            assert got == pytest.approx(case["expect"]), f"{g['function']}{tuple(case['args'])}"
