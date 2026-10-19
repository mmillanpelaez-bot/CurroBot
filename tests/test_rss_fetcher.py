import time

import feedparser
import pytest

from fetcher import rss_fetcher
from fetcher.rss_fetcher import fetch_rss_feed, generate_job_id

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title> Python Developer </title><link> https://remoteok.com/l/1 </link>
<pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>Sin enlace</title></item>
</channel></rss>"""


def test_generate_job_id_consistency():
    url = "https://example.com/job/123"
    assert generate_job_id(url) == generate_job_id(url)
    assert len(generate_job_id(url)) == 32


def test_fetch_real_rss_parsing_and_iso_date(mocker):
    mocker.patch("fetcher.rss_fetcher._download", return_value=RSS)
    offers = fetch_rss_feed("https://remoteok.com/rss", "RemoteOK")
    assert len(offers) == 1  # la entrada sin enlace se descarta
    offer = offers[0]
    assert offer["id"] == generate_job_id("https://remoteok.com/l/1")  # hash del link recortado
    assert offer["title"] == "Python Developer"
    assert offer["url"] == "https://remoteok.com/l/1"
    assert offer["company"] == "Desconocida"
    assert offer["location"] == "No especificada"
    assert offer["published_at"] == "2026-09-28 10:00"


def test_fetch_uses_company_and_location_when_present(mocker):
    entry = feedparser.FeedParserDict(
        link="https://x.com/1",
        title="Dev",
        company="Tech Corp",
        location="Remoto",
        published_parsed=time.struct_time((2026, 9, 28, 10, 0, 0, 0, 0, 0)),
    )
    feed = mocker.Mock(bozo=False, entries=[entry])
    mocker.patch("fetcher.rss_fetcher._download", return_value=b"")
    mocker.patch("feedparser.parse", return_value=feed)
    offer = fetch_rss_feed("https://x.com/rss", "X")[0]
    assert (offer["company"], offer["location"]) == ("Tech Corp", "Remoto")


def test_none_fields_use_defaults(mocker):
    entry = feedparser.FeedParserDict(link="https://x.com/1", title=None, company=None)
    feed = mocker.Mock(bozo=False, entries=[entry])
    mocker.patch("fetcher.rss_fetcher._download", return_value=b"")
    mocker.patch("feedparser.parse", return_value=feed)
    offer = fetch_rss_feed("https://x.com/rss", "X")[0]
    assert offer["title"] == "Sin título" and offer["company"] == "Desconocida"


def test_unreadable_feed_raises(mocker):
    """Bozo + sin entradas = fallo real: debe propagarse para que fetch_all lo cuente."""
    mocker.patch("fetcher.rss_fetcher._download", return_value=b"<html>no soy rss")
    with pytest.raises(ValueError):
        fetch_rss_feed("https://x.com/rss", "X")


def test_download_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        rss_fetcher._download("file:///etc/passwd")


def test_default_location_applies_when_feed_has_none(mocker):
    mocker.patch("fetcher.rss_fetcher._download", return_value=RSS)
    offer = fetch_rss_feed("https://remoteok.com/rss", "RemoteOK", default_location="Remoto")[0]
    assert offer["location"] == "Remoto"
