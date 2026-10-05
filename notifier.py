import os
import logging
from typing import List
import requests
from src.models import JobOffer

# Configuración del logger
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Clase encargada de formatear y enviar notificaciones a Telegram."""

    def __init__(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else ""

    def format_offer_html(self, offer: JobOffer) -> str:
        """Formatea una única oferta en sintaxis HTML compatible con Telegram."""
        return (
            f"🚀 <b>{offer['title']}</b>\n"
            f"🏢 <b>Empresa:</b> {offer['company']}\n"
            f"📍 <b>Ubicación:</b> {offer['location']}\n"
            f"🏷️ <b>Fuente:</b> {offer['source']} | 🕒 {offer['published_at']}\n"
            f"🔗 <a href='{offer['url']}'>Ver oferta de empleo</a>\n"
        )

    def send_notification(self, offers: List[JobOffer]) -> bool:
        if not offers:
            logger.info("No hay nuevas ofertas para notificar.")
            return True

        if not self.bot_token or not self.chat_id:
            logger.error("Faltan variables de entorno: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configuradas.")
            return False

        # Construcción del mensaje agrupado
        header = f"🔔 <b>¡Se han encontrado {len(offers)} nuevas ofertas de empleo!</b>\n\n"
        body = "\n───────────────\n".join([self.format_offer_html(offer) for offer in offers])
        full_message = header + body

        payload = {
            "chat_id": self.chat_id,
            "text": full_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Notificación enviada con éxito ({len(offers)} ofertas).")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar la notificación a Telegram: {e}")
            return False