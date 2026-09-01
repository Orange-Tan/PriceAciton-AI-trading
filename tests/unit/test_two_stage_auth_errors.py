from __future__ import annotations

import sys
import types


def test_http_401_is_not_classified_as_network_error(monkeypatch):
    from pa_agent.orchestrator.two_stage import TwoStageOrchestrator

    class APIStatusError(Exception):
        status_code = 401

    fake_openai = types.SimpleNamespace(
        APITimeoutError=type("APITimeoutError", (Exception,), {}),
        APIConnectionError=type("APIConnectionError", (Exception,), {}),
        APIStatusError=APIStatusError,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    assert TwoStageOrchestrator._is_network_error(APIStatusError("invalid key")) is False
