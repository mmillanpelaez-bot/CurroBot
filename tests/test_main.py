import os
from typing import Dict

import pytest

import main
from fetcher.feeds import Feed
from notifier.http import NotificationError


def _offer(job_id: str) -> Dict[str, str]:
    return {
        "id": job_id,
        "title": "Python Dev",
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
            raise NotificationError("Telegram caído")
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
    result = main.fetch_all([Feed("u1", "Rota"), Feed("u2", "Buena")])
    assert [o["id"] for o in result] == ["a"]


def test_fetch_all_raises_when_every_feed_fails(mocker):
    mocker.patch("main.fetch_rss_feed", side_effect=RuntimeError("timeout"))
    with pytest.raises(main.AllFeedsFailedError):
        main.fetch_all([Feed("u1", "A"), Feed("u2", "B")])


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


def test_pipeline_without_notifier_does_not_mark_seen(mocker):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a")])
    store = FakeStore()
    result = main.run_pipeline(store=store, notifier=None)
    assert [o["id"] for o in result] == ["a"]
    assert store.marked == []  # sin notificar no hay nada que marcar


def test_dry_run_neither_sends_nor_persists(mocker):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a")])
    store, notifier = FakeStore(), FakeNotifier()
    result = main.run_pipeline(store=store, notifier=notifier, dry_run=True)
    assert [o["id"] for o in result] == ["a"]
    assert notifier.sent == [] and store.marked == []


def test_main_returns_1_when_all_feeds_fail(mocker, tmp_path):
    mocker.patch("main.fetch_rss_feed", side_effect=RuntimeError("timeout"))
    assert main.main(["--state-file", str(tmp_path / "seen.json")]) == 1


def test_fetch_all_passes_default_location(mocker):
    fetch = mocker.patch("main.fetch_rss_feed", return_value=[])
    main.fetch_all([Feed("u", "RemoteOK", "Remoto")])
    fetch.assert_called_once_with("u", "RemoteOK", "Remoto")


def test_max_alerts_limits_and_only_marks_sent(mocker):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a"), _offer("b")])
    store, notifier = FakeStore(), FakeNotifier()
    main.run_pipeline(store=store, notifier=notifier, max_alerts=1)
    assert notifier.sent == ["a"] and store.marked == ["a"]  # "b" saldrá en la próxima


def test_main_returns_2_when_notification_fails(mocker, tmp_path):
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a")])
    mocker.patch("main.build_notifier_from_env", return_value=FakeNotifier(fail=True))
    state = tmp_path / "seen.json"
    assert main.main(["--state-file", str(state)]) == 2
    assert not state.exists()  # nada marcado: se reintenta


def test_main_end_to_end_is_idempotent(mocker, tmp_path):
    """Primera ejecución notifica y guarda; la segunda no repite nada."""
    mocker.patch("main.fetch_rss_feed", return_value=[_offer("a")])
    notifier = FakeNotifier()
    mocker.patch("main.build_notifier_from_env", return_value=notifier)
    state = tmp_path / "seen.json"

    assert main.main(["--state-file", str(state)]) == 0
    assert notifier.sent == ["a"] and state.exists()
    assert main.main(["--state-file", str(state)]) == 0
    assert notifier.sent == ["a"]


def test_main_filters_out_non_matching_offers(mocker, tmp_path):
    offer = _offer("a")
    offer["title"] = "Senior Python Developer"
    mocker.patch("main.fetch_rss_feed", return_value=[offer])
    notifier = FakeNotifier()
    mocker.patch("main.build_notifier_from_env", return_value=notifier)
    assert main.main(["--state-file", str(tmp_path / "s.json")]) == 0
    assert notifier.sent == []


def test_test_notify_sends_sample(mocker):
    notifier = FakeNotifier()
    mocker.patch("main.build_notifier_from_env", return_value=notifier)
    assert main.main(["--test-notify"]) == 0
    assert notifier.sent == ["test"]


def test_test_notify_without_channels_returns_1(mocker):
    mocker.patch("main.build_notifier_from_env", return_value=None)
    assert main.main(["--test-notify"]) == 1
