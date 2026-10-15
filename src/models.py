from typing import TypedDict

class JobOffer(TypedDict):
    id: str           # Hash MD5 único
    title: str        # Título de la oferta
    company: str      # Empresa
    location: str     # Ubicación / Remoto
    url: str          # URL canónica
    source: str       # Fuente ('Tecnoempleo')
    published_at: str # Fecha de publicación