from __future__ import annotations


def test_probe_worker_does_not_emit_after_interruption(monkeypatch):
    from pa_agent.gui.watchlist_worker import AshareSourceProbeWorker

    worker = AshareSourceProbeWorker()
    emitted = []
    worker.result_ready.connect(lambda *args: emitted.append(args))
    import pa_agent.data.factory as factory

    monkeypatch.setattr(factory, "first_connected_a_share_source", lambda **kwargs: "tencent")
    monkeypatch.setattr(worker, "isInterruptionRequested", lambda: True)

    worker.run()

    assert emitted == []
