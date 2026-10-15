import sys
from pathlib import Path

# Ajuste del PYTHONPATH:
# Subimos 2 niveles desde 'tests/test_rss_fetcher.py' para llegar a la raíz 'CurroBot'
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from src.fetcher.rss_fetcher import generate_job_id, fetch_tecnoempleo_rss


def test_generate_job_id_consistency():
    """Valida que la generación de ID con MD5 sea consistente e idempotente."""
    url = "https://www.tecnoempleo.com/oferta-12345"
    id_1 = generate_job_id(url)
    id_2 = generate_job_id(url)

    assert id_1 == id_2
    assert len(id_1) == 32  # Un hash MD5 tiene exactamente 32 caracteres hexadecimales


def test_fetch_tecnoempleo_rss_contract(mocker):
    """
    Simula la respuesta del feed RSS y valida que el objeto resultante
    cumpla con la estructura y claves del contrato JobOffer.
    """
    # 1. Crear el objeto simulado (Mock) del feed
    mock_feed = mocker.Mock()
    mock_entry = mocker.Mock()

    mock_entry.link = "https://www.tecnoempleo.com/python-dev-madrid"
    mock_entry.title = "Desarrollador Python Junior"
    mock_entry.author = "Tech Company"
    mock_entry.published = "2026-10-15 10:00"
    mock_entry.tags = [{"term": "Remoto"}]

    mock_feed.entries = [mock_entry]
    mock_feed.bozo = False

    # 2. Interceptar la llamada a feedparser.parse
    mocker.patch("feedparser.parse", return_value=mock_feed)

    # 3. Ejecutar la función a probar
    result = fetch_tecnoempleo_rss("http://fake-feed-url.com")

    # 4. Validaciones
    assert len(result) == 1
    offer = result[0]

    # Verificación del Data Contract (JobOffer)
    assert offer["id"] == generate_job_id("https://www.tecnoempleo.com/python-dev-madrid")
    assert offer["title"] == "Desarrollador Python Junior"
    assert offer["company"] == "Tech Company"
    assert offer["location"] == "Remoto"
    assert offer["url"] == "https://www.tecnoempleo.com/python-dev-madrid"
    assert offer["source"] == "Tecnoempleo"
    assert offer["published_at"] == "2026-10-15 10:00"


def test_fetch_tecnoempleo_rss_empty_on_error(mocker):
    """Verifica el comportamiento defensivo: si la red o el feed falla, debe devolver lista vacía."""
    mocker.patch("feedparser.parse", side_effect=Exception("Error de conexión simualdo"))

    result = fetch_tecnoempleo_rss("http://fake-feed-url.com")

    assert result == []