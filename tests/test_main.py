import os
from typing import Dict

import pytest

import main


def _offer(job_id: str) -> Dict[str, str]:
    return {
        "id": job_id,
        "title": "Dev",
        "company": "X",
        "location": "Remoto",
        "url": f"https://x.com/{job_id}",
        "source": "Test",
        "published_at": "2026-10-08 10:00",
    }


class FakeStore:
    def __init__(self, seen=()):
        self.seen, self.marked = set(seen), []

    def only_new(self, jobs):
        return [j for j in jobs if j["id"] not in self.seen]

    def mark_seen(self, jobs):
        self.marked.extend(j["id"] for j in jobs)


class FakeNotifier:
    def __init__(self, fail=False):
        self.fail, self.sent = fail, []

    def send(self, jobs):
        if self.fail:
            raise RuntimeError("Telegram caído")
        self.sent.extend(j["id"] for j in jobs)


def test_check_environment_missing_keys(caplog, monkeypatch):
    """Registra un aviso si faltan las variables de entorno."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    with caplog.at_level("WARNING"):
        main.check_environment()
    assert "No se detectaron variables de entorno" in caplog.text


def test_check_environment_with_token(caplog, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    with caplog.at_level("INFO"):
        main.check_environment()
    assert "cargadas correctamente" in caplog.text
    assert "dummy" not in caplog.text  # nunca exponer secretos
    assert os.getenv("TELEGRAM_BOT_TOKEN") == "dummy"


def test_fetch_all_survives_failing_feed(mocker):
    mocker.patch(
        "main.fetch_rss_feed",
        side_effect=[RuntimeError("timeout"), [_offer("a")]],
    )
    result = main.fetch_all([("u1", "Rota"), ("u2", "Buena")])
    assert [o["id"] for o in result] == ["a"]


def test_fetch_all_raises_when_every_feed_fails(mocker):
    mocker.patch("main.fetch_rss_feed", side_effect=RuntimeError("timeout"))
    with pytest.raises(main.AllFeedsFailedError):
        main.fetch_all([("u1", "A"), ("u2", "B")])


def test_deduplicate_keeps_first_and_order():
    result = main.deduplicate([_offer("a"), _offer("b"), _offer("a")])
    assert [o["id"] for o in result] == ["a", "b"]


def test_run_pipeline_returns_list(mocker):
    """El orquestador devuelve una lista, sin tocar la red."""
    mocker.patch("main.fetch_rss_feed", return_value=[])
    assert main.run_pipeline() == []


def test_pipeline_notifies_only_new_and_marks_seen(mocker):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a"), _offer("b")])
    store, notifier = FakeStore(seen={"a"}), FakeNotifier()
    main.run_pipeline(store=store, notifier=notifier)
    assert notifier.sent == ["b"]
    assert store.marked == ["b"]


def test_pipeline_does_not_mark_seen_if_notify_fails(mocker):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a")])
    store = FakeStore()
    with pytest.raises(RuntimeError):
        main.run_pipeline(store=store, notifier=FakeNotifier(fail=True))
    assert store.marked == []  # se reintentará en la próxima ejecución


def test_dry_run_neither_sends_nor_persists(mocker):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a")])
    store, notifier = FakeStore(), FakeNotifier()
    result = main.run_pipeline(store=store, notifier=notifier, dry_run=True)
    assert [o["id"] for o in result] == ["a"]
    assert notifier.sent == [] and store.marked == []


def test_main_returns_1_when_all_feeds_fail(mocker):
    mocker.patch("main.fetch_rss_feed", side_effect=RuntimeError("timeout"))
    assert main.main([]) == 1
