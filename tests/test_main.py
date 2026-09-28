import os
import pytest
from main import check_environment, run_pipeline

def test_check_environment_missing_keys(caplog):
    """Verifica que el sistema registre un aviso si faltan las variables de entorno."""
    # Aseguramos ausencia de variables en el entorno de prueba
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("DISCORD_WEBHOOK_URL", None)

    with caplog.at_level("WARNING"):
        check_environment()
        assert "No se detectaron variables de entorno" in caplog.text


def test_run_pipeline_returns_list():
    """Garantiza que el orquestador devuelva una lista compatible con JobOffer."""
    results = run_pipeline()
    assert isinstance(results, list)