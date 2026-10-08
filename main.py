"""Orquestador del Bot de Alertas de Empleo (CurroBot)."""

import logging
import os
import sys
from typing import Dict, List, Tuple

from fetcher.rss_fetcher import fetch_rss_feed
from models import JobOffer

logger = logging.getLogger("JobAlertBot")

# Provisional: en la Sesión 7 Martín lo parametrizará vía variables de entorno.
FEEDS: List[Tuple[str, str]] = [
    ("https://remoteok.com/remote-jobs.rss", "RemoteOK"),
]


def configure_logging() -> None:
    """Única configuración de logging del proyecto; los módulos solo usan getLogger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def check_environment() -> None:
    """Valida la presencia de secretos sin exponer sus valores."""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")

    if not telegram_token and not discord_webhook:
        logger.warning(
            "No se detectaron variables de entorno para notificaciones "
            "(TELEGRAM_BOT_TOKEN o DISCORD_WEBHOOK_URL). "
            "El orquestador se ejecutará en modo simulación (Dry-Run)."
        )
    else:
        logger.info("Variables de entorno cargadas correctamente.")


def fetch_all(feeds: List[Tuple[str, str]]) -> List[JobOffer]:
    """Descarga todos los feeds; el fallo de uno no interrumpe a los demás."""
    offers: List[JobOffer] = []
    for url, source in feeds:
        try:
            offers.extend(fetch_rss_feed(url, source))
        except Exception:
            logger.exception("Fallo al obtener el feed de %s; se continúa.", source)
    return offers


def deduplicate(offers: List[JobOffer]) -> List[JobOffer]:
    """Elimina duplicados dentro de la misma ejecución conservando el orden."""
    unique: Dict[str, JobOffer] = {}
    for offer in offers:
        unique.setdefault(offer["id"], offer)
    return list(unique.values())


def run_pipeline() -> List[JobOffer]:
    """Coordina las etapas: fetch -> filtro -> persistencia -> notificación."""
    logger.info("Iniciando pipeline del Bot de Alertas de Empleo...")
    check_environment()

    jobs = deduplicate(fetch_all(FEEDS))
    # TODO S4: jobs = FilterEngine(...).apply(jobs)          (Sergio)
    # TODO S4: jobs = PersistenceEngine(...).only_new(jobs)  (Breixo)
    # TODO S5: Notifier(...).send(jobs)                      (René)

    logger.info("Pipeline finalizado. Ofertas procesadas: %d", len(jobs))
    return jobs


if __name__ == "__main__":
    configure_logging()
    run_pipeline()
