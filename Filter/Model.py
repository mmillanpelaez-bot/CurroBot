"""Modelos de datos compartidos del proyecto IPE.

Única fuente de verdad del contrato JobOffer. main.py, rss_fetcher.py y
filter_engine.py deben importarlo desde aquí: ``from src.models import JobOffer``.
"""
from typing import TypedDict


class JobOffer(TypedDict):
    """Contrato de datos estandarizado estricto del proyecto IPE."""

    id: str            # Hash MD5 único
    title: str         # Título de la oferta
    company: str       # Nombre de la empresa ('Desconocida' si falta)
    location: str      # Ubicación o modalidad ('Remoto', 'Madrid', etc.)
    url: str           # Enlace directo
    source: str        # Plataforma de origen ('Tecnoempleo', 'RemoteOK', etc.)
    published_at: str  # Fecha ISO 8601 (YYYY-MM-DD HH:MM)