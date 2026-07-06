"""Smoke tests: is the service up, authenticated, and actually serving tokens?

Run after every change to the stack (new model, backend swap, upgrade):

    make smoke

Needs only the Python stdlib + pytest, and two env vars (loaded from ../../.env
automatically): LITELLM_MASTER_KEY, and optionally GATEWAY_URL.

These are *wiring* tests, not quality tests (that's tests/eval/) and not
performance tests (that's tests/perf/). Keep them fast and unconditional:
if any of these fail, nothing else about the service can be trusted.
"""

import json
import os
import pathlib
import time
import urllib.error
import urllib.request

import pytest

# Minimal .env loader so the tests have no dependencies beyond pytest.
_env = pathlib.Path(__file__).parents[2] / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:4000")
ADMIN_KEY = os.environ["LITELLM_MASTER_KEY"]


def _request(path, payload=None, key=ADMIN_KEY):
    req = urllib.request.Request(
        GATEWAY + path,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def test_gateway_is_alive():
    with urllib.request.urlopen(GATEWAY + "/health/liveliness", timeout=10) as resp:
        assert resp.status == 200


def test_models_are_listed():
    """Every model name in gateway/litellm-config.yaml should be advertised."""
    listed = {m["id"] for m in _request("/v1/models")["data"]}
    for expected in ("coder", "general"):
        assert expected in listed, f"'{expected}' missing — gateway config drifted?"


def test_unauthenticated_requests_are_rejected():
    """Auth is the whole point of the gateway: prove it's enforced."""
    with pytest.raises(urllib.error.HTTPError) as err:
        _request("/v1/models", key="sk-not-a-real-key")
    assert err.value.code in (401, 403)


@pytest.mark.parametrize("model", ["coder", "general"])
def test_completion_round_trip(model):
    """A real completion through gateway → backend, whatever the backend is.

    This test is identical in every phase — that's the invariant the gateway
    buys you. When you swap build.nvidia.com for a self-hosted NIM, this
    passing is your definition of 'the migration worked'.
    """
    t0 = time.time()
    out = _request(
        "/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
            "max_tokens": 20,
        },
    )
    text = out["choices"][0]["message"]["content"]
    assert "pong" in text.lower()
    assert out["usage"]["completion_tokens"] > 0, "usage accounting data missing"
    print(f"\n  {model}: round trip {time.time() - t0:.1f}s, reply: {text!r}")


def test_spend_is_being_tracked():
    """Usage accounting: the completions above must show up in spend logs.

    Spend logs are written asynchronously (the gateway batches DB writes), so
    the rows may land a few seconds after the completion returns — hence the
    retry loop. Accounting being eventually consistent is normal; it's the
    ledger, not the request path.
    """
    deadline = time.time() + 30
    while True:
        logs = _request("/spend/logs")
        if isinstance(logs, list) and len(logs) > 0:
            return
        if time.time() > deadline:
            break
        time.sleep(3)
    pytest.fail("no spend logs after 30s — is DATABASE_URL wired to Postgres?")
