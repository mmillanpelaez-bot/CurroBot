import json

from fetcher.feeds import DEFAULT_FEEDS, Feed, load_feeds


def test_missing_file_uses_defaults(tmp_path):
    assert load_feeds(tmp_path / "no_existe.json") == DEFAULT_FEEDS
    assert load_feeds(None) == DEFAULT_FEEDS


def test_invalid_json_uses_defaults(tmp_path):
    bad = tmp_path / "feeds.json"
    bad.write_text("{no es json")
    assert load_feeds(bad) == DEFAULT_FEEDS


def test_valid_file_and_invalid_entries_skipped(tmp_path):
    path = tmp_path / "feeds.json"
    path.write_text(
        json.dumps(
            {
                "feeds": [
                    {"url": "https://a.com/rss", "source": "A", "default_location": "Remoto"},
                    {"url": "https://b.com/rss", "source": "B"},
                    {"source": "sin url"},
                    "basura",
                ]
            }
        )
    )
    assert load_feeds(path) == [
        Feed("https://a.com/rss", "A", "Remoto"),
        Feed("https://b.com/rss", "B", "No especificada"),
    ]


def test_all_entries_invalid_uses_defaults(tmp_path):
    path = tmp_path / "feeds.json"
    path.write_text(json.dumps({"feeds": [{"x": 1}]}))
    assert load_feeds(path) == DEFAULT_FEEDS


def test_shipped_config_is_valid():
    feeds = load_feeds("config/feeds.json")
    assert len(feeds) >= 1 and all(f.url.startswith("https://") for f in feeds)
