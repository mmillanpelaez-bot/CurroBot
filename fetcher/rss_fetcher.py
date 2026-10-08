"""Ingesta de feeds RSS y transformación al contrato JobOffer."""

import hashlib
import logging
from typing import List

import feedparser

from models import JobOffer

logger = logging.getLogger("DataFetcher")


def generate_job_id(url: str) -> str:
    """Genera un hash MD5 de 32 caracteres a partir de la URL."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def fetch_rss_feed(feed_url: str, source_name: str) -> List[JobOffer]:
    """Obtiene un feed RSS y devuelve las ofertas siguiendo el contrato JobOffer."""
    logger.info("Iniciando descarga de RSS desde: %s", feed_url)
    parsed_feed = feedparser.parse(feed_url)

    if parsed_feed.bozo:
        logger.warning("Posible problema de formato en el RSS de %s.", source_name)

    job_offers: List[JobOffer] = []

    for entry in parsed_feed.entries:
        link = getattr(entry, "link", "")
        if not link:
            continue  # Sin URL no hay ID posible

        title = getattr(entry, "title", "Sin título")
        company = getattr(entry, "company", "Desconocida")
        location = getattr(entry, "location", "No especificada")
        published = getattr(entry, "published", "1970-01-01 00:00")

        offer: JobOffer = {
            "id": generate_job_id(link),
            "title": title.strip(),
            "company": company.strip() if company else "Desconocida",
            "location": location.strip() if location else "No especificada",
            "url": link.strip(),
            "source": source_name,
            "published_at": published,
        }
        job_offers.append(offer)

    logger.info("Se procesaron %d ofertas de %s.", len(job_offers), source_name)
    return job_offers
