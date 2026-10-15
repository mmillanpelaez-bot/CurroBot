"""Orquestador del Bot de Alertas de Empleo (CurroBot)."""

import argparse
import logging
import os
import sys
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from dotenv import load_dotenv

from fetcher.rss_fetcher import fetch_rss_feed
from models import JobOffer

logger = logging.getLogger("JobAlertBot")

# Provisional: en la Sesión 7 Martín lo parametrizará vía variables de entorno.
FEEDS: List[Tuple[str, str]] = [
    ("https://remoteok.com/remote-jobs.rss", "RemoteOK"),
]


class AllFeedsFailedError(RuntimeError):
    """Todos los feeds configurados fallaron: no hay datos con los que trabajar."""


class JobFilter(Protocol):
    def apply(self, jobs: List[JobOffer]) -> List[JobOffer]: ...


class JobStore(Protocol):
    def only_new(self, jobs: List[JobOffer]) -> List[JobOffer]: ...

    def mark_seen(self, jobs: List[JobOffer]) -> None: ...


class JobNotifier(Protocol):
    def send(self, jobs: List[JobOffer]) -> None: ...


def configure_logging(level: str = "INFO") -> None:
    """Única configuración de logging del proyecto; los módulos solo usan getLogger."""
    logging.basicConfig(
        level=getattr(logging, level),
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
    failures = 0
    for url, source in feeds:
        try:
            offers.extend(fetch_rss_feed(url, source))
        except Exception:
            failures += 1
            logger.exception("Fallo al obtener el feed de %s; se continúa.", source)
    if feeds and failures == len(feeds):
        raise AllFeedsFailedError(f"Fallaron los {failures} feeds configurados.")
    return offers


def deduplicate(offers: List[JobOffer]) -> List[JobOffer]:
    """Elimina duplicados dentro de la misma ejecución conservando el orden."""
    unique: Dict[str, JobOffer] = {}
    for offer in offers:
        unique.setdefault(offer["id"], offer)
    return list(unique.values())


def run_pipeline(
    feeds: Optional[List[Tuple[str, str]]] = None,
    job_filter: Optional[JobFilter] = None,
    store: Optional[JobStore] = None,
    notifier: Optional[JobNotifier] = None,
    dry_run: bool = False,
) -> List[JobOffer]:
    """fetch -> filtro -> solo nuevas -> notificar -> marcar como vistas."""
    logger.info("Iniciando pipeline del Bot de Alertas de Empleo...")
    check_environment()

    jobs = deduplicate(fetch_all(feeds if feeds is not None else FEEDS))
    if job_filter:
        jobs = job_filter.apply(jobs)
    if store:
        jobs = store.only_new(jobs)

    if dry_run:
        logger.info("Dry-run: %d ofertas nuevas; no se envía ni se persiste.", len(jobs))
        return jobs

    if jobs and notifier:
        notifier.send(jobs)  # si lanza, NO se marca nada y se reintenta en la próxima ejecución
    if jobs and store:
        store.mark_seen(jobs)

    logger.info("Pipeline finalizado. Ofertas procesadas: %d", len(jobs))
    return jobs


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CurroBot: alertas de empleo")
    parser.add_argument(
        "--dry-run", action="store_true", help="No envía notificaciones ni guarda estado."
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    load_dotenv()  # no-op si no existe .env (caso de GitHub Actions)
    try:
        run_pipeline(dry_run=args.dry_run)
    except AllFeedsFailedError:
        logger.error("Pipeline abortado: ninguna fuente respondió.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
