"""Formato de las alertas (HTML para Telegram, Markdown para Discord) y troceado."""

import html
import logging
import re
from typing import Callable, List

from models import JobOffer

logger = logging.getLogger("Notifier")

TELEGRAM_LIMIT = 4096
DISCORD_LIMIT = 2000
MAX_TITLE = 200
MAX_FIELD = 100


def _cut(value: object, limit: int) -> str:
    """Normaliza espacios y recorta a `limit` caracteres."""
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _md_escape(text: str) -> str:
    return re.sub(r"([\\*_`~|>])", r"\\\1", text)


def count_label(n: int) -> str:
    return "1 oferta nueva" if n == 1 else f"{n} ofertas nuevas"


def format_job_html(job: JobOffer) -> str:
    """Bloque HTML (Telegram). Todo el contenido externo se escapa."""
    title = html.escape(_cut(job.get("title"), MAX_TITLE))
    company = html.escape(_cut(job.get("company"), MAX_FIELD))
    location = html.escape(_cut(job.get("location"), MAX_FIELD))
    source = html.escape(_cut(job.get("source"), MAX_FIELD))
    published = html.escape(_cut(job.get("published_at"), MAX_FIELD))
    url = html.escape(str(job.get("url") or ""), quote=True)
    return (
        f"🔹 <b>{title}</b>\n"
        f"🏢 {company} · 📍 {location}\n"
        f"🕒 {published} · {source}\n"
        f'<a href="{url}">Ver oferta</a>'
    )


def format_job_markdown(job: JobOffer) -> str:
    """Bloque Markdown (Discord). La URL entre <> evita la previsualización."""
    title = _md_escape(_cut(job.get("title"), MAX_TITLE))
    company = _md_escape(_cut(job.get("company"), MAX_FIELD))
    location = _md_escape(_cut(job.get("location"), MAX_FIELD))
    source = _md_escape(_cut(job.get("source"), MAX_FIELD))
    published = _cut(job.get("published_at"), MAX_FIELD)
    url = str(job.get("url") or "")
    return (
        f"🔹 **{title}**\n"
        f"🏢 {company} · 📍 {location}\n"
        f"🕒 {published} · {source}\n"
        f"<{url}>"
    )


def build_messages(
    jobs: List[JobOffer],
    formatter: Callable[[JobOffer], str],
    limit: int,
    header: str = "",
) -> List[str]:
    """Agrupa las ofertas en mensajes que nunca superan `limit` caracteres."""
    messages: List[str] = []
    current = header
    added = 0
    for job in jobs:
        block = formatter(job)
        if len(block) > limit:
            logger.warning("Oferta %s omitida: supera el límite del canal.", job.get("id"))
            continue
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and added:
            messages.append(current)
            current = block
        else:
            current = candidate
        added += 1
    if added:
        messages.append(current)
    return messages
