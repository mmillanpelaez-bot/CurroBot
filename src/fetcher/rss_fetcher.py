import hashlib
import logging
import sys
from pathlib import Path
from typing import List
import feedparser

# Añade la raíz del proyecto al sys.path para resolver las importaciones
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.models import JobOffer

logger = logging.getLogger("JobBotPipeline.Fetcher")


def generate_job_id(url: str) -> str:
    """Genera un hash MD5 único y determinista a partir de la URL canónica."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def fetch_tecnoempleo_rss(feed_url: str = "https://www.tecnoempleo.com/rss/") -> List[JobOffer]:
    """
    Extrae ofertas de empleo desde el feed RSS de Tecnoempleo
    y las transforma defensivamente al contrato JobOffer.
    """
    logger.info(f"Martín: Conectando al feed RSS en {feed_url}...")

    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            logger.warning("Martín: El XML recuperado tiene mal formato, aplicando parseo defensivo.")

        offers: List[JobOffer] = []

        for entry in feed.entries:
            raw_url = getattr(entry, "link", "")
            if not raw_url:
                continue

            job_id = generate_job_id(raw_url)
            title = getattr(entry, "title", "Sin título")
            company = getattr(entry, "author", "Desconocida")

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
                "source": "Tecnoempleo",
                "published_at": published_at
            }
            offers.append(offer)

        logger.info(f"Martín: Extraídas exitosamente {len(offers)} ofertas.")
        return offers

    except Exception as e:
        logger.error(f"Martín: Error al procesar el feed RSS: {e}")
        return []