"""Contrato de datos compartido por todos los módulos del proyecto."""

from typing import TypedDict


class JobOffer(TypedDict):
    id: str  # Hash MD5 único derivado de la URL canónica o GUID del RSS
    title: str  # Título de la oferta
    company: str  # Nombre de la empresa ('Desconocida' si falta)
    location: str  # Ubicación o modalidad ('Remoto', 'Madrid', etc.)
    url: str  # Enlace canónico directo
    source: str  # Plataforma de origen ('Tecnoempleo', 'RemoteOK', etc.)
    published_at: str  # ISO 8601: YYYY-MM-DD HH:MM
