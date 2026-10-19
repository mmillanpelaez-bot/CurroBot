"""Notificador por Telegram Bot API (sendMessage)."""

import logging
import time
from typing import Any, Callable, Dict, List

from models import JobOffer
from notifier.formatter import (
    TELEGRAM_LIMIT,
    build_messages,
    count_label,
    format_job_html,
)
from notifier.http import post_json

logger = logging.getLogger("Notifier")

PostFn = Callable[[str, Dict[str, Any]], int]


class TelegramNotifier:
    def __init__(
        self, token: str, chat_id: str, pause: float = 0.5, post: PostFn = post_json
    ) -> None:
        if not token or not chat_id:
            raise ValueError("Telegram requiere token y chat_id")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"  # contiene el secreto
        self._chat_id = chat_id
        self._pause = pause
        self._post = post

    def send(self, jobs: List[JobOffer]) -> None:
        """Envía las ofertas (troceadas). Lanza NotificationError si falla."""
        if not jobs:
            return
        header = f"📢 <b>{count_label(len(jobs))}</b>"
        messages = build_messages(jobs, format_job_html, TELEGRAM_LIMIT, header)
        for index, text in enumerate(messages):
            if index:
                time.sleep(self._pause)
            self._post(
                self._url,
                {
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        logger.info("Telegram: %d ofertas en %d mensaje(s).", len(jobs), len(messages))
