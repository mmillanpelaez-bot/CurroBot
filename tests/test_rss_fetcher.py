from fetcher.rss_fetcher import fetch_rss_feed, generate_job_id


def test_generate_job_id_consistency():
    """El generador de IDs es consistente y produce 32 caracteres."""
    url = "https://example.com/job/123"
    assert generate_job_id(url) == generate_job_id(url)
    assert len(generate_job_id(url)) == 32


def test_fetch_rss_feed_mock(mocker):
    """Transformación con datos simulados, sin internet."""
    mock_feed = mocker.Mock()
    mock_feed.bozo = False
    mock_feed.entries = [
        mocker.Mock(
            link="https://remoteok.com/l/1",
            title="Python Developer",
            company="Tech Corp",
            location="Remoto",
            published="2026-09-28 10:00",
        )
    ]
    mocker.patch("feedparser.parse", return_value=mock_feed)

    offers = fetch_rss_feed("https://remoteok.com/rss", "RemoteOK")
    assert len(offers) == 1
    assert offers[0]["id"] == generate_job_id("https://remoteok.com/l/1")
    assert offers[0]["title"] == "Python Developer"
    assert offers[0]["company"] == "Tech Corp"
    assert offers[0]["source"] == "RemoteOK"


def test_fetch_rss_feed_skips_entries_without_link(mocker):
    mock_feed = mocker.Mock()
    mock_feed.bozo = False
    mock_feed.entries = [mocker.Mock(link="", title="Sin enlace")]
    mocker.patch("feedparser.parse", return_value=mock_feed)

    assert fetch_rss_feed("https://x.com/rss", "X") == []
