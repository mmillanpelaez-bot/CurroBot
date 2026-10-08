import hashlib
import logging
from typing import Dict, List, TypedDict
import feedparser
import requests

# 1. Logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("DataFetcher")

# Fuentes RSS predeterminadas para la Sesión 3
DEFAULT_SOURCES: List[Dict[str, str]] = [
    {"name": "RemoteOK", "url": "https://remoteok.com/rss"},
    {"name": "Tecnoempleo", "url": "https://www.tecnoempleo.com/feeder/rss.te"},
]


# 2. Contrato de Datos JobOffer
class JobOffer(TypedDict):
    id: str           # Hash MD5 único derivado de la URL canónica
    title: str        # Título de la oferta
    company: str      # Nombre de la empresa ('Desconocida' si no existe)
    location: str     # Ubicación o modalidad ('Remoto', etc.)
    url: str          # Enlace directo canónico
    source: str       # Nombre de la fuente ('Tecnoempleo', 'RemoteOK')
    published_at: str # Fecha formateada (ISO 8601 o texto RSS)


# 3. Generación de Hash MD5 Único
def generate_job_id(canonical_url: str) -> str:
    """Genera un hash MD5 único de 32 caracteres a partir de la URL."""
    return hashlib.md5(canonical_url.encode("utf-8")).hexdigest()


# 4. Parseo Defensivo de RSS Individual
def fetch_rss_feed(feed_url: str, source_name: str, timeout: int = 10) -> List[JobOffer]:
    """Descarga y parsea un feed RSS/Atom convirtiéndolo al contrato JobOffer."""
    logger.info(f"Iniciando descarga de RSS desde {source_name}: {feed_url}")

    try:
        response = requests.get(
            feed_url, 
            timeout=timeout, 
            headers={"User-Agent": "CurroBot/1.0 (Python/3.11)"}
        )
        response.raise_for_status()
        parsed_feed = feedparser.parse(response.content)
    except requests.RequestException as req_err:
        logger.error(f"Error de red/HTTP al conectar con {source_name} ({feed_url}): {req_err}")
        return []
    except Exception as e:
        logger.error(f"Error imprevisto procesando {source_name}: {e}")
        return []

    if parsed_feed.bozo:
        logger.warning(f"Posible problema de formato XML en {source_name}.")

    job_offers: List[JobOffer] = []

    for entry in parsed_feed.entries:
        raw_link = getattr(entry, "link", "")
        if not raw_link or not raw_link.strip():
            continue

        # Extraer con fallbacks defensivos
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


# 5. Orquestador de Fuentes (Sesión 3 Deliverable)
def fetch_all_sources(sources: List[Dict[str, str]] = None) -> List[JobOffer]:
    """Obtiene y agrupa ofertas de todas las fuentes configuradas."""
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

    logger.info(f"Total global descargado: {len(all_offers)} ofertas de {len(sources)} fuentes.")
    return all_offers


if __name__ == "__main__":
    # Prueba de ejecución manual local
    offers = fetch_all_sources()
    print(f"\n--- Descargadas {len(offers)} ofertas en total ---")
    if offers:
        print(f"Ejemplo de oferta parseada: {offers[0]}")