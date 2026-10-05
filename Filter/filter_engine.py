import abc
import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)


class JobOffer(TypedDict):
    """Contrato de datos estandarizado estricto del proyecto IPE."""
    id: str           # Hash MD5 único
    title: str        # Título de la oferta
    company: str      # Nombre de la empresa ('Desconocida' si falta)
    location: str     # Ubicación o modalidad ('Remoto', 'Madrid', etc.)
    url: str          # Enlace directo
    source: str       # Plataforma de origen ('Tecnoempleo', 'RemoteOK', etc.)
    published_at: str # Fecha formateada ISO 8601 (YYYY-MM-DD HH:MM)


def normalize_text(text: Optional[str]) -> str:
    """Sanea campos vacíos/None, convierte a minúsculas y elimina acentos."""
    if not text:
        return ""
    nfd_form = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in nfd_form if unicodedata.category(char) != "Mn")


def build_tech_pattern(keyword: str) -> re.Pattern:
    """Construye una expresión regular precompilada con soporte para símbolos técnicos."""
    norm_kw = normalize_text(keyword)
    escaped_kw = re.escape(norm_kw)

    start_b = r"\b" if norm_kw and norm_kw[0].isalnum() else r"(?:^|\s|[^\w])"
    end_b = r"\b" if norm_kw and norm_kw[-1].isalnum() else r"(?:$|\s|[^\w])"

    return re.compile(f"{start_b}{escaped_kw}{end_b}", re.IGNORECASE)


class BaseFilterRule(abc.ABC):
    """Interfaz abstracta para implementar el Patrón Estrategia."""

    @abc.abstractmethod
    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        pass


class BlacklistRule(BaseFilterRule):
    def __init__(self, forbidden_keywords: List[str]):
        self.forbidden_patterns = [
            (kw, build_tech_pattern(kw)) for kw in forbidden_keywords if kw
        ]

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        target_text = normalize_text(f"{offer.get('title', '')} {offer.get('location', '')}")
        for raw_kw, pattern in self.forbidden_patterns:
            if pattern.search(target_text):
                return False, 0, f"Contiene palabra prohibida: {raw_kw}"
        return True, 0, ""


class RequiredKeywordsRule(BaseFilterRule):
    def __init__(self, required_keywords: List[str], synonyms: Optional[Dict[str, List[str]]] = None):
        self.synonyms = synonyms or {}
        self.compiled_rules: List[Tuple[str, List[re.Pattern]]] = []

        for kw in required_keywords:
            if not kw:
                continue
            terms = [kw] + self.synonyms.get(kw.lower(), [])
            patterns = [build_tech_pattern(term) for term in terms]
            self.compiled_rules.append((kw, patterns))

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        if not self.compiled_rules:
            return True, 0, ""

        target_text = normalize_text(f"{offer.get('title', '')} {offer.get('location', '')}")
        score = 0

        for _, patterns in self.compiled_rules:
            if any(p.search(target_text) for p in patterns):
                score += 10

        if score == 0:
            return False, 0, "No incluye ninguna palabra clave requerida"

        return True, score, ""


class RemoteOrLocationRule(BaseFilterRule):
    def __init__(self, require_remote: bool = False, allowed_locations: Optional[List[str]] = None):
        self.require_remote = require_remote
        self.allowed_locations = [normalize_text(loc) for loc in (allowed_locations or []) if loc]

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        title_text = normalize_text(offer.get("title", ""))
        loc_text = normalize_text(offer.get("location", ""))
        full_text = f"{title_text} {loc_text}"

        is_remote = "remoto" in full_text or "remote" in full_text

        if self.require_remote and not is_remote:
            return False, 0, "Requiere modalidad remota"

        if self.allowed_locations and not is_remote:
            if not any(loc in loc_text for loc in self.allowed_locations):
                return False, 0, f"Ubicación no permitida: {offer.get('location')}"

        bonus_score = 5 if is_remote else 0
        return True, bonus_score, ""


class JobFilterEngine:
    def __init__(self, rules: Optional[List[BaseFilterRule]] = None):
        self.rules: List[BaseFilterRule] = rules or []

    def is_relevant(self, offer: JobOffer) -> Tuple[bool, int, str]:
        total_score = 0
        for rule in self.rules:
            passed, score, reason = rule.evaluate(offer)
            if not passed:
                return False, 0, reason
            total_score += score
        return True, total_score, ""

    def filter_offers(self, offers: List[JobOffer]) -> List[JobOffer]:
        logger.info(f"Procesando {len(offers)} ofertas...")
        evaluated: List[Tuple[JobOffer, int]] = []

        for offer in offers:
            if not isinstance(offer, dict):
                continue
            passed, score, _ = self.is_relevant(offer)
            if passed:
                evaluated.append((offer, score))

        evaluated.sort(key=lambda item: item[1], reverse=True)
        return [item[0] for item in evaluated]


def create_job_filter_from_config(
    config_source: Optional[Any] = None,
    runtime_overrides: Optional[Dict[str, Any]] = None
) -> JobFilterEngine:
    """
    Fábrica híbrida:
    1. Carga la configuración base (archivo JSON o diccionario).
    2. Aplica 'runtime_overrides' si se solicita una búsqueda dinámica puntual.
    3. Usa valores de respaldo por defecto si no existe ninguno de los anteriores.
    """
    cfg: Dict[str, Any] = {}

    # 1. Cargar configuración base
    if isinstance(config_source, str):
        try:
            with open(config_source, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as err:
            logger.warning(f"No se pudo cargar la configuración base ({err}). Usandodefaults.")
    elif isinstance(config_source, dict):
        cfg = config_source.copy()

    # 2. Aplicar sobreescritura dinámica si existe (Modo Ad-hoc)
    if runtime_overrides:
        cfg.update(runtime_overrides)

    # 3. Construir reglas usando la combinación final
    synonyms_map = cfg.get("synonyms", {
        "python": ["py"],
        "javascript": ["js", "ecmascript"],
        "react": ["react.js", "reactjs"],
        "node": ["node.js", "nodejs"]
    })

    rules: List[BaseFilterRule] = [
        BlacklistRule(cfg.get("forbidden_keywords", ["senior", "lead", "head of"])),
        RequiredKeywordsRule(
            required_keywords=cfg.get("required_keywords", ["python", "java", "c++", "node.js"]),
            synonyms=synonyms_map
        ),
        RemoteOrLocationRule(
            require_remote=cfg.get("require_remote", False),
            allowed_locations=cfg.get("allowed_locations", [])
        )
    ]

    return JobFilterEngine(rules=rules)