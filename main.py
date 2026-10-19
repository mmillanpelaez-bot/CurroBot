"""Orquestador del Bot de Alertas de Empleo (CurroBot)."""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence

from dotenv import load_dotenv

from fetcher.feeds import DEFAULT_FEEDS, Feed, load_feeds
from fetcher.rss_fetcher import fetch_rss_feed
from filters.filter_engine import create_job_filter_from_config
from models import JobOffer
from notifier import NotificationError, build_notifier_from_env
from persistence.persistence_engine import PersistenceEngine

logger = logging.getLogger("JobAlertBot")

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FEEDS_FILE = BASE_DIR / "config" / "feeds.json"
DEFAULT_FILTERS_FILE = BASE_DIR / "config" / "filters.json"
DEFAULT_STATE_FILE = BASE_DIR / "data" / "seen_jobs.json"
DEFAULT_MAX_ALERTS = 20

TEST_JOB: JobOffer = {
    "id": "test",
    "title": "Oferta de prueba (CurroBot)",
    "company": "CurroBot",
    "location": "Remoto",
    "url": "https://github.com",
    "source": "Test",
    "published_at": "2026-01-01 00:00",
}


class AllFeedsFailedError(RuntimeError):
    """Todos los feeds configurados fallaron: no hay datos con los que trabajar."""


class JobFilter(Protocol):
    def filter_offers(self, offers: List[JobOffer]) -> List[JobOffer]: ...


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
        return

    if telegram_token and not os.getenv("TELEGRAM_CHAT_ID"):
        logger.warning("Falta TELEGRAM_CHAT_ID: el envío por Telegram no será posible.")
    logger.info("Variables de entorno cargadas correctamente.")


def fetch_all(feeds: List[Feed]) -> List[JobOffer]:
    """Descarga todos los feeds; el fallo de uno no interrumpe a los demás."""
    offers: List[JobOffer] = []
    failures = 0
    for feed in feeds:
        try:
            offers.extend(fetch_rss_feed(feed.url, feed.source, feed.default_location))
        except Exception:
            failures += 1
            logger.exception("Fallo al obtener el feed de %s; se continúa.", feed.source)
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
    feeds: Optional[List[Feed]] = None,
    job_filter: Optional[JobFilter] = None,
    store: Optional[JobStore] = None,
    notifier: Optional[JobNotifier] = None,
    dry_run: bool = False,
    max_alerts: Optional[int] = None,
) -> List[JobOffer]:
    """fetch -> filtro -> solo nuevas -> limitar -> notificar -> marcar como vistas."""
    logger.info("Iniciando pipeline del Bot de Alertas de Empleo...")
    check_environment()

    jobs = deduplicate(fetch_all(feeds if feeds is not None else DEFAULT_FEEDS))
    if job_filter:
        jobs = job_filter.filter_offers(jobs)
    if store:
        jobs = store.only_new(jobs)
    if max_alerts is not None and len(jobs) > max_alerts:
        # Las que no se envían no se marcan: salen en la próxima ejecución.
        logger.info("Se envían las %d mejores de %d nuevas.", max_alerts, len(jobs))
        jobs = jobs[:max_alerts]

    if dry_run:
        logger.info("Dry-run: %d ofertas nuevas; no se envía ni se persiste.", len(jobs))
        for job in jobs:
            logger.info("  • [%s] %s (%s)", job["source"], job["title"], job["location"])
        return jobs

    if notifier is None:
        # Marcar como vistas ofertas que nadie ha notificado = alertas perdidas.
        logger.warning("Sin notificador configurado: no se persiste nada (%d ofertas).", len(jobs))
        return jobs

    if jobs:
        notifier.send(jobs)  # si lanza, NO se marca nada y se reintenta en la próxima ejecución
        if store:
            store.mark_seen(jobs)

    logger.info("Pipeline finalizado. Ofertas procesadas: %d", len(jobs))
    return jobs


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CurroBot: alertas de empleo")
    parser.add_argument(
        "--dry-run", action="store_true", help="No envía notificaciones ni guarda estado."
    )
    parser.add_argument(
        "--test-notify", action="store_true", help="Envía una oferta de prueba y termina."
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    parser.add_argument("--feeds-file", default=str(DEFAULT_FEEDS_FILE), help="JSON de feeds.")
    parser.add_argument("--config", default=None, help="JSON de filtros (por defecto config/).")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="Ruta del estado.")
    parser.add_argument(
        "--max-alerts", type=int, default=DEFAULT_MAX_ALERTS, help="Máximo de ofertas por envío."
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    load_dotenv()  # no-op si no existe .env (caso de GitHub Actions)
    notifier = build_notifier_from_env()

    try:
        if args.test_notify:
            if notifier is None:
                logger.error("No hay ningún canal configurado (revisa .env / Secrets).")
                return 1
            notifier.send([TEST_JOB])
            logger.info("Mensaje de prueba enviado.")
            return 0

        filters_file = args.config or (
            str(DEFAULT_FILTERS_FILE) if DEFAULT_FILTERS_FILE.exists() else None
        )
        run_pipeline(
            feeds=load_feeds(args.feeds_file),
            job_filter=create_job_filter_from_config(filters_file),
            store=PersistenceEngine(args.state_file),
            notifier=notifier,
            dry_run=args.dry_run,
            max_alerts=args.max_alerts,
        )
    except AllFeedsFailedError:
        logger.error("Pipeline abortado: ninguna fuente respondió.")
        return 1
    except NotificationError as err:
        logger.error("No se pudo notificar: %s", err)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
