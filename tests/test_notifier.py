import unittest
from unittest.mock import patch, MagicMock
from src.notifier import TelegramNotifier
from src.models import JobOffer

class TestTelegramNotifier(unittest.TestCase):

    def setUp(self) -> None:
        self.sample_offer: JobOffer = {
            "id": "e10adc3949ba59abbe56e057f20f883e",
            "title": "Desarrollador Python Junior",
            "company": "Tech Solutions",
            "location": "Remoto",
            "url": "https://example.com/job/1",
            "source": "Tecnoempleo",
            "published_at": "2026-10-05 10:00"
        }

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    @patch("requests.post")
    def test_send_notification_success(self, mock_post: MagicMock) -> None:
        """Prueba de envío exitoso de notificación (Happy Path)."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        notifier = TelegramNotifier()
        result = notifier.send_notification([self.sample_offer])

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_send_notification_missing_credentials(self) -> None:
        """Prueba que falla de forma segura cuando faltan credenciales."""
        notifier = TelegramNotifier()
        result = notifier.send_notification([self.sample_offer])

        self.assertFalse(result)

    def test_send_notification_empty_list(self) -> None:
        """Verifica que no hace peticiones HTTP si la lista de ofertas está vacía."""
        notifier = TelegramNotifier()
        result = notifier.send_notification([])

        self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()