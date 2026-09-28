# tests/test_rss_fetcher.py

from fetcher.rss_fetcher import generate_job_id, fetch_rss_feed


def test_generate_job_id_consistency():
    """Comprueba que el generador de IDs sea consistente y produzca un hash de 32 caracteres."""
    url = "https://example.com/job/123"
    hash1 = generate_job_id(url)
    hash2 = generate_job_id(url)
    assert hash1 == hash2
    assert len(hash1) == 32


def test_fetch_rss_feed_mock(mocker):
    """Prueba la lógica de transformación usando datos simulados sin depender de internet."""
    mock_feed = mocker.Mock()
    mock_feed.bozo = False
    mock_feed.entries = [
        mocker.Mock(
            link="https://remoteok.com/l/1",
            title="Python Developer",
            company="Tech Corp",
            location="Remoto",
            published="2026-09-28 10:00"
        )
    ]
    mocker.patch("feedparser.parse", return_value=mock_feed)

    offers = fetch_rss_feed("https://remoteok.com/rss", "RemoteOK")
    assert len(offers) == 1
    assert offers[0]["id"] == generate_job_id("https://remoteok.com/l/1")
    assert offers[0]["title"] == "Python Developer"
    assert offers[0]["company"] == "Tech Corp"
    assert offers[0]["source"] == "RemoteOK"