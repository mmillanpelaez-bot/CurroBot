# fetcher/rss_fetcher.py

import hashlib
import logging
from typing import List, TypedDict
import feedparser

# 1. Configuración de Logging: Para registrar la actividad en la consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("DataFetcher")


# 2. Contrato de Datos: La estructura exacta que exige el equipo
class JobOffer(TypedDict):
    id: str           # Hash MD5 único derivado de la URL
    title: str        # Título de la oferta
    company: str      # Nombre de la empresa ('Desconocida' si no existe)
    location: str     # Ubicación o modalidad
    url: str          # Enlace directo
    source: str       # Fuente de donde se obtiene (ej: 'RemoteOK')
    published_at: str # Fecha formateada


# 3. Generador de ID Único: Evita procesar ofertas duplicadas
def generate_job_id(url: str) -> str:
    """Genera un hash MD5 de 32 caracteres a partir de la URL."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


# 4. Función de Descarga y Transformación: Descarga el RSS y mapea al contrato
def fetch_rss_feed(feed_url: str, source_name: str) -> List[JobOffer]:
    """Obtiene un feed RSS y devuelve las ofertas siguiendo el contrato JobOffer."""
    logger.info(f"Iniciando descarga de RSS desde: {feed_url}")
    parsed_feed = feedparser.parse(feed_url)

    if parsed_feed.bozo:
        logger.warning(f"Posible problema de formato en el RSS de {source_name}.")

    job_offers: List[JobOffer] = []

    for entry in parsed_feed.entries:
        link = getattr(entry, "link", "")
        if not link:
            continue  # Si no hay URL, ignoramos la entrada por falta de ID

        # Parseo defensivo con valores por defecto
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

    logger.info(f"Se procesaron exitosamente {len(job_offers)} ofertas de {source_name}.")
    return job_offers