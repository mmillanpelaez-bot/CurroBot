import unittest
from unittest.mock import MagicMock, patch
import requests

# Corrección de la ruta de importación cuando ejecutas dentro de CurroBot
from fetcher.rss_fetcher import (
    fetch_all_sources,
    fetch_rss_feed,
    generate_job_id,
)


class TestRssFetcher(unittest.TestCase):

    def test_generate_job_id_deterministic(self):
        url = "https://remoteok.com/remote-jobs/12345"
        self.assertEqual(generate_job_id(url), generate_job_id(url))
        self.assertEqual(len(generate_job_id(url)), 32)

    @patch("requests.get")
    @patch("feedparser.parse")
    def test_fetch_rss_feed_success(self, mock_feedparser, mock_requests_get):
        mock_response = MagicMock()
        mock_response.content = b"<xml></xml>"
        mock_requests_get.return_value = mock_response

        mock_entry = MagicMock()
        mock_entry.link = "https://tecnoempleo.com/oferta/100"
        mock_entry.title = " Desarrollador Python "
        mock_entry.author = " TechCorp "
        mock_entry.location = " Remoto "
        mock_entry.published = "2026-10-05 10:00"

        mock_feed = MagicMock()
        mock_feed.bozo = 0
        mock_feed.entries = [mock_entry]
        mock_feedparser.return_value = mock_feed

        results = fetch_rss_feed("https://fake-url.com/rss", "TestProvider")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Desarrollador Python")
        self.assertEqual(results[0]["company"], "TechCorp")

    @patch("requests.get")
    def test_fetch_rss_feed_timeout_resilience(self, mock_requests_get):
        mock_requests_get.side_effect = requests.Timeout("Timeout de red")
        results = fetch_rss_feed("https://fake-url.com/rss", "TestProvider")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()