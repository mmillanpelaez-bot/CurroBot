import os
from typing import Dict

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


def test_deduplicate_keeps_first_and_order():
    result = main.deduplicate([_offer("a"), _offer("b"), _offer("a")])
    assert [o["id"] for o in result] == ["a", "b"]


def test_run_pipeline_returns_list(mocker):
    """El orquestador devuelve una lista, sin tocar la red."""
    mocker.patch("main.fetch_rss_feed", return_value=[])
    assert main.run_pipeline() == []
