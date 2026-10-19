"""Construcción de notificadores a partir de variables de entorno."""

import logging
import os
from typing import List, Mapping, Optional

from models import JobOffer
from notifier.discord import DiscordNotifier
from notifier.http import NotificationError
from notifier.telegram import TelegramNotifier

logger = logging.getLogger("Notifier")


class CompositeNotifier:
    """Envía por todos los canales. Falla solo si TODOS fallan.

    Si un canal funciona y otro no, no se lanza excepción: reintentar
    duplicaría el aviso en el canal que sí funcionó.
    """

    def __init__(self, notifiers: List[object]) -> None:
        self.notifiers = notifiers

    def send(self, jobs: List[JobOffer]) -> None:
        delivered = 0
        for notifier in self.notifiers:
            try:
                notifier.send(jobs)  # type: ignore[attr-defined]
                delivered += 1
            except Exception as err:
                logger.error("Canal %s falló: %s", type(notifier).__name__, err)
        if self.notifiers and not delivered:
            raise NotificationError("Todos los canales de notificación fallaron.")


def build_notifier_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[CompositeNotifier]:
    """Devuelve el notificador configurado o None si no hay ningún canal."""
    env = os.environ if env is None else env
    channels: List[object] = []

    token, chat_id = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        channels.append(TelegramNotifier(token, chat_id))
    elif token or chat_id:
        logger.warning("Telegram incompleto: se necesitan TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.")

    webhook = env.get("DISCORD_WEBHOOK_URL")
    if webhook:
        try:
            channels.append(DiscordNotifier(webhook))
        except ValueError as err:
            logger.error("Discord desactivado: %s", err)

    return CompositeNotifier(channels) if channels else None
