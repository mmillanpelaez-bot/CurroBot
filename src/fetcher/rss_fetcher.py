import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional
import feedparser

# Garantizar el path del proyecto
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.models import JobOffer

logger = logging.getLogger("JobBotPipeline.Fetcher")

DEFAULT_FEEDS = [
    "https://www.tecnoempleo.com/rss/",
    "https://remoteok.com/rss"
]


def get_configured_feeds() -> List[str]:
    """Obtiene la lista de feeds desde variable de entorno o usa los por defecto."""
    env_feeds = os.getenv("JOB_FEEDS_URLS")
    if env_feeds:
        return [url.strip() for url in env_feeds.split(",") if url.strip()]
    return DEFAULT_FEEDS


def generate_job_id(url: str) -> str:
    """Genera un hash MD5 único a partir de la URL canónica."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def fetch_single_feed(feed_url: str) -> List[JobOffer]:
    """Extrae ofertas de un feed RSS de forma defensiva."""
    logger.info(f"Martín: Conectando a {feed_url}...")

    try:
        feed = feedparser.parse(feed_url)

        if getattr(feed, "bozo", False):
            logger.warning(f"Martín: Formato XML irregular en {feed_url}. Parseo parcial.")

        offers: List[JobOffer] = []

        for entry in getattr(feed, "entries", []):
            raw_url = getattr(entry, "link", "")
            if not raw_url:
                continue

            job_id = generate_job_id(raw_url)
            title = getattr(entry, "title", "Sin título")
            company = getattr(entry, "author", getattr(entry, "company", "Desconocida"))

            location = "No especificada"
            if hasattr(entry, "tags") and entry.tags:
                location = entry.tags[0].get("term", "No especificada")

            published_at = getattr(entry, "published", "Fecha no disponible")

            offer: JobOffer = {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": raw_url,
                "source": "RSS_Feed",
                "published_at": published_at
            }
            offers.append(offer)

        return offers

    except Exception as e:
        logger.error(f"Martín: Error al procesar {feed_url}: {e}")
        return []


def fetch_all_jobs(feed_urls: Optional[List[str]] = None) -> List[JobOffer]:
    """Orquestador de extracción multi-fuente."""
    urls = feed_urls or get_configured_feeds()
    all_offers: List[JobOffer] = []

    for url in urls:
        offers = fetch_single_feed(url)
        all_offers.extend(offers)

    return all_offers