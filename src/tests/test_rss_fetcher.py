import unittest
from unittest.mock import MagicMock, patch

from src.fetcher.rss_fetcher import fetch_rss_jobs, generate_job_id

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <item>
        <title>Python Developer</title>
        <link>https://ejemplo.com/job/100</link>
    </item>
</channel>
</rss>
"""


class TestRssFetcher(unittest.TestCase):

    def test_id_generation(self) -> None:
        """Verifica la generación idempotente de IDs MD5."""
        url = "https://ejemplo.com/job/100"
        self.assertEqual(len(generate_job_id(url)), 32)
        self.assertEqual(generate_job_id(url), generate_job_id(url))

    @patch("urllib.request.urlopen")
    def test_fetch_rss_success(self, mock_urlopen: MagicMock) -> None:
        """Verifica la extracción exitosa desde un RSS simulado."""
        mock_response = MagicMock()
        mock_response.read.return_value = SAMPLE_XML.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        offers = fetch_rss_jobs("https://fake.com/rss", "TestSource")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title"], "Python Developer")
        self.assertEqual(offers[0]["source"], "TestSource")


if __name__ == "__main__":
    unittest.main()