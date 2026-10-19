"""Notificador por Webhook de Discord."""

import logging
import time
from typing import Any, Callable, Dict, List

from models import JobOffer
from notifier.formatter import (
    DISCORD_LIMIT,
    build_messages,
    count_label,
    format_job_markdown,
)
from notifier.http import post_json

logger = logging.getLogger("Notifier")

PostFn = Callable[[str, Dict[str, Any]], int]


class DiscordNotifier:
    def __init__(self, webhook_url: str, pause: float = 1.0, post: PostFn = post_json) -> None:
        if not webhook_url.startswith("https://"):
            raise ValueError("El webhook de Discord debe ser una URL https")
        self._url = webhook_url
        self._pause = pause
        self._post = post

    def send(self, jobs: List[JobOffer]) -> None:
        """Envía las ofertas (troceadas). Lanza NotificationError si falla."""
        if not jobs:
            return
        header = f"📢 **{count_label(len(jobs))}**"
        messages = build_messages(jobs, format_job_markdown, DISCORD_LIMIT, header)
        for index, text in enumerate(messages):
            if index:
                time.sleep(self._pause)  # límite de ritmo de los webhooks
            self._post(self._url, {"content": text})
        logger.info("Discord: %d ofertas en %d mensaje(s).", len(jobs), len(messages))
