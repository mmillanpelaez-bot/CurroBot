import hashlib
import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List

from src.models import JobOffer

logger = logging.getLogger(__name__)


def generate_job_id(canonical_url: str) -> str:
    """Genera un hash MD5 único a partir de la URL canónica de la oferta."""
    return hashlib.md5(canonical_url.strip().encode("utf-8")).hexdigest()


def fetch_rss_jobs(
    feed_url: str, source_name: str = "RSS Feed"
) -> List[JobOffer]:
    """
    Obtiene y parsea un feed RSS público convirtiendo las entradas al contrato JobOffer.
    Maneja timeouts, errores HTTP y XMLs corruptos.
    """
    offers: List[JobOffer] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BotEmpleo/1.0"
    }
    req = urllib.request.Request(feed_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        logger.error(f"Error de red/timeout en {source_name} ({feed_url}): {e}")
        return []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        logger.error(f"Error parseando el XML de {source_name}: {e}")
        return []

    for item in root.findall(".//item"):
        link = item.findtext("link", default="").strip()
        if not link:
            continue

        title = item.findtext("title", default="Sin Título").strip()
        company = (
            item.findtext("author")
            or item.findtext("dc:creator")
            or "Desconocida"
        )
        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        offer: JobOffer = {
            "id": generate_job_id(link),
            "title": title,
            "company": company.strip(),
            "location": "No especificada",
            "url": link,
            "source": source_name,
            "published_at": formatted_date,
        }
        offers.append(offer)

    logger.info(
        f"Se extrajeron {len(offers)} ofertas de la fuente: {source_name}"
    )
    return offers