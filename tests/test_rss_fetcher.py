import sys
from pathlib import Path

# Subir 2 niveles desde tests/ para llegar a la raíz CurroBot
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from src.fetcher.rss_fetcher import generate_job_id, get_configured_feeds, fetch_all_jobs


def test_generate_job_id():
    url = "https://www.tecnoempleo.com/oferta-12345"
    assert generate_job_id(url) == generate_job_id(url)
    assert len(generate_job_id(url)) == 32


def test_get_configured_feeds_from_env(monkeypatch):
    monkeypatch.setenv("JOB_FEEDS_URLS", "https://feed1.com/rss, https://feed2.com/rss")
    feeds = get_configured_feeds()
    assert len(feeds) == 2
    assert feeds[0] == "https://feed1.com/rss"


def test_fetch_all_jobs_integration(mocker):
    mock_entry = mocker.Mock()
    mock_entry.link = "https://ejemplo.com/job-1"
    mock_entry.title = "Python Dev"
    mock_entry.author = "Empresa Test"
    mock_entry.published = "2026-10-15"
    mock_entry.tags = [{"term": "Remoto"}]

    mock_feed = mocker.Mock()
    mock_feed.entries = [mock_entry]
    mock_feed.bozo = False

    mocker.patch("feedparser.parse", return_value=mock_feed)

    results = fetch_all_jobs(["https://fake-feed.com"])
    assert len(results) == 1
    assert results[0]["title"] == "Python Dev"