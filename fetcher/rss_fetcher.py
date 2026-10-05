import hashlib
import logging
from typing import Dict, List, TypedDict
import feedparser
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("DataFetcher")

DEFAULT_SOURCES: List[Dict[str, str]] = [
    {"name": "RemoteOK", "url": "https://remoteok.com/rss"},
    {"name": "Tecnoempleo", "url": "https://www.tecnoempleo.com/feeder/rss.te"},
]


class JobOffer(TypedDict):
    id: str           # Unique MD5 Hash (derived from canonical URL or RSS GUID)
    title: str        # Job offer title
    company: str      # Offering company name ('Desconocida' if missing)
    location: str     # Work location or mode ('Remoto', 'Madrid', etc.)
    url: str          # Direct canonical link to the job posting
    source: str       # Origin platform ('Tecnoempleo', 'RemoteOK', etc.)
    published_at: str # Formatted date string (ISO 8601: YYYY-MM-DD HH:MM)


def generate_job_id(canonical_url: str) -> str:
    """Genera un hash MD5 único de 32 caracteres a partir de la URL canónica de la oferta."""
    return hashlib.md5(canonical_url.encode("utf-8")).hexdigest()


def fetch_rss_feed(feed_url: str, source_name: str, timeout: int = 10) -> List[JobOffer]:
    """Obtiene y parsea un feed RSS/Atom convirtiéndolo al contrato JobOffer."""
    logger.info(f"Iniciando descarga desde {source_name}: {feed_url}")

    try:
        response = requests.get(
            feed_url,
            timeout=timeout,
            headers={"User-Agent": "CurroBot/1.0 (Python/3.11)"}
        )
        response.raise_for_status()
        parsed_feed = feedparser.parse(response.content)
    except requests.RequestException as req_err:
        logger.error(f"Error HTTP/Red al conectar con {source_name} ({feed_url}): {req_err}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado al procesar {source_name}: {e}")
        return []

    if parsed_feed.bozo:
        logger.warning(f"Advertencia de formato XML en la fuente {source_name}.")

    job_offers: List[JobOffer] = []

    for entry in parsed_feed.entries:
        raw_link = getattr(entry, "link", "")
        if not raw_link or not raw_link.strip():
            continue

        title = getattr(entry, "title", "Sin título")
        company = getattr(entry, "author", getattr(entry, "company", "Desconocida"))
        location = getattr(entry, "location", "No especificada")
        published = getattr(entry, "published", "1970-01-01 00:00")

        clean_link = raw_link.strip()

        offer: JobOffer = {
            "id": generate_job_id(clean_link),
            "title": title.strip() if title else "Sin título",
            "company": company.strip() if company else "Desconocida",
            "location": location.strip() if location else "No especificada",
            "url": clean_link,
            "source": source_name,
            "published_at": published.strip() if published else "1970-01-01 00:00",
        }
        job_offers.append(offer)

    logger.info(f"Se procesaron {len(job_offers)} ofertas de {source_name}.")
    return job_offers


def fetch_all_sources(sources: List[Dict[str, str]] = None) -> List[JobOffer]:
    """Orquestador multifuente defensivo."""
    if sources is None:
        sources = DEFAULT_SOURCES

    all_offers: List[JobOffer] = []

    for source in sources:
        name = source.get("name", "Desconocida")
        url = source.get("url", "")

        if not url:
            continue

        offers = fetch_rss_feed(url, name)
        all_offers.extend(offers)

    logger.info(f"Total global: {len(all_offers)} ofertas obtenidas de {len(sources)} fuentes.")
    return all_offers