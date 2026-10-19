"""Ingesta de feeds RSS y transformación al contrato JobOffer."""

import hashlib
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Any, List, Mapping

import feedparser

from models import JobOffer

logger = logging.getLogger("DataFetcher")

REQUEST_TIMEOUT = 15
USER_AGENT = "CurroBot/1.0 (job alerts; educational project)"
DATE_FORMAT = "%Y-%m-%d %H:%M"


def generate_job_id(url: str) -> str:
    """Genera un hash MD5 de 32 caracteres a partir de la URL."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _download(feed_url: str, timeout: int = REQUEST_TIMEOUT) -> bytes:
    """Descarga el feed con timeout y User-Agent. Solo permite http(s)."""
    if not feed_url.startswith(("http://", "https://")):
        raise ValueError(f"Esquema de URL no permitido: {feed_url}")
    request = urllib.request.Request(feed_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _clean(value: Any, default: str) -> str:
    """Convierte a str, recorta espacios y aplica el valor por defecto si queda vacío."""
    if not value:
        return default
    return str(value).strip() or default


def _published_at(entry: Mapping[str, Any]) -> str:
    """Fecha ISO 8601 (YYYY-MM-DD HH:MM); si falta o es inválida, usa 'ahora' en UTC."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6]).strftime(DATE_FORMAT)
        except (TypeError, ValueError):
            logger.debug("Fecha no interpretable: %r", parsed)
    return datetime.now(timezone.utc).strftime(DATE_FORMAT)


def fetch_rss_feed(
    feed_url: str, source_name: str, default_location: str = "No especificada"
) -> List[JobOffer]:
    """Obtiene un feed RSS y devuelve las ofertas siguiendo el contrato JobOffer.

    Lanza excepción si la red falla o el feed es ilegible (para que el
    orquestador pueda contar el fallo).
    """
    logger.info("Iniciando descarga de RSS desde: %s", feed_url)
    parsed_feed = feedparser.parse(_download(feed_url))

    if parsed_feed.bozo:
        if not parsed_feed.entries:
            raise ValueError(f"Feed ilegible o vacío en {source_name}")
        logger.warning("Posible problema de formato en el RSS de %s.", source_name)

    job_offers: List[JobOffer] = []
    for entry in parsed_feed.entries:
        link = _clean(entry.get("link"), "")
        if not link:
            continue  # Sin URL no hay ID posible

        job_offers.append(
            {
                "id": generate_job_id(link),
                "title": _clean(entry.get("title"), "Sin título"),
                "company": _clean(entry.get("company"), "Desconocida"),
                "location": _clean(entry.get("location"), default_location),
                "url": link,
                "source": source_name,
                "published_at": _published_at(entry),
            }
        )

    logger.info("Se procesaron %d ofertas de %s.", len(job_offers), source_name)
    return job_offers
