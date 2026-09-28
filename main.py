import os
import logging
import sys
from typing import TypedDict, List

# Contrato de datos estricto para todo el equipo
class JobOffer(TypedDict):
    id: str           # Hash MD5 único
    title: str        # Título de la oferta
    company: str      # Nombre de la empresa ('Desconocida' si falta)
    location: str     # Ubicación o modalidad ('Remoto', 'Madrid', etc.)
    url: str          # Enlace canónico directo
    source: str       # Plataforma de origen ('Tecnoempleo', 'RemoteOK', etc.)
    published_at: str # Fecha en formato ISO 8601 (YYYY-MM-DD HH:MM)

# Configuración global de Logging profesional para CLI
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("JobAlertBot")


def check_environment() -> None:
    """Valida la presencia de secretos o variables necesarias sin exponer sus valores."""
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


def run_pipeline() -> List[JobOffer]:
    """
    Punto de entrada orquestador.
    Coordinará las llamadas secuenciales a los módulos de Martín, Sergio, Breixo y René.
    """
    logger.info("Iniciando pipeline del Bot de Alertas de Empleo...")
    check_environment()

    # Stub inicial mientras se integran los módulos del resto del equipo
    processed_jobs: List[JobOffer] = []

    logger.info("Pipeline finalizado con éxito. Ofertas procesadas: %d", len(processed_jobs))
    return processed_jobs


if __name__ == "__main__":
    run_pipeline()