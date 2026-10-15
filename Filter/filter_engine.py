"""Motor de filtrado de ofertas de empleo basado en reglas (Patrón Estrategia)."""
import abc
import json
import logging
import re
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from Filter.Model import JobOffer

logger = logging.getLogger(__name__)

REMOTE_BONUS = 2
KEYWORD_SCORE = 10
REMOTE_PATTERN = re.compile(r"\b(?:remoto|remote|teletrabajo)\b")

DEFAULT_FORBIDDEN = ["senior", "lead", "head of"]
DEFAULT_REQUIRED = ["python", "java", "c++", "node.js"]
DEFAULT_SYNONYMS: Dict[str, List[str]] = {
    "python": ["py"],
    "javascript": ["js", "ecmascript"],
    "react": ["react.js", "reactjs"],
    "node.js": ["nodejs", "node"],
}


@lru_cache(maxsize=4096)
def normalize_text(text: Optional[str]) -> str:
    """Sanea campos vacíos/None, convierte a minúsculas y elimina acentos."""
    if not text:
        return ""
    nfd_form = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in nfd_form if unicodedata.category(char) != "Mn")


def offer_text(offer: JobOffer) -> str:
    """Devuelve 'título ubicación' normalizado (None-safe, cacheado por normalize_text)."""
    title = offer.get("title") or ""
    location = offer.get("location") or ""
    return normalize_text(f"{title} {location}")


def build_tech_pattern(keyword: str) -> re.Pattern:
    """Construye una regex precompilada con soporte para símbolos técnicos (c++, c#, .net)."""
    norm_kw = normalize_text(keyword)
    escaped_kw = re.escape(norm_kw)

    start_b = r"\b" if norm_kw and norm_kw[0].isalnum() else r"(?:^|\s|[^\w])"
    end_b = r"\b" if norm_kw and norm_kw[-1].isalnum() else r"(?:$|\s|[^\w])"

    return re.compile(f"{start_b}{escaped_kw}{end_b}", re.IGNORECASE)


class BaseFilterRule(abc.ABC):
    """Interfaz abstracta para implementar el Patrón Estrategia."""

    @abc.abstractmethod
    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        """Evalúa una oferta y devuelve (pasa, puntuación, motivo_de_descarte)."""


class BlacklistRule(BaseFilterRule):
    """Descarta ofertas que contengan alguna palabra prohibida."""

    def __init__(self, forbidden_keywords: List[str]) -> None:
        """Precompila un patrón por cada palabra prohibida."""
        self.forbidden_patterns = [
            (kw, build_tech_pattern(kw)) for kw in forbidden_keywords if kw
        ]

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        """Rechaza la oferta si título o ubicación contienen una palabra prohibida."""
        target_text = offer_text(offer)
        for raw_kw, pattern in self.forbidden_patterns:
            if pattern.search(target_text):
                return False, 0, f"Contiene palabra prohibida: {raw_kw}"
        return True, 0, ""


class KeywordMatchRule(BaseFilterRule):
    """Puntúa ofertas según las palabras clave (y sinónimos) que contengan.

    Con ``match_all=False`` (por defecto) basta con una keyword (modo OR).
    Con ``match_all=True`` se exigen todas (modo AND).
    """

    def __init__(
        self,
        required_keywords: List[str],
        synonyms: Optional[Dict[str, List[str]]] = None,
        match_all: bool = False,
    ) -> None:
        """Precompila patrones por keyword, incluyendo sus sinónimos normalizados."""
        self.match_all = match_all
        self.synonyms = {normalize_text(k): v for k, v in (synonyms or {}).items()}
        self.compiled_rules: List[Tuple[str, List[re.Pattern]]] = []

        for kw in required_keywords:
            if not kw:
                continue
            terms = [kw] + self.synonyms.get(normalize_text(kw), [])
            patterns = [build_tech_pattern(term) for term in terms]
            self.compiled_rules.append((kw, patterns))

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        """Calcula la puntuación y aplica el modo OR/AND."""
        if not self.compiled_rules:
            return True, 0, ""

        target_text = offer_text(offer)
        matched = [
            kw for kw, patterns in self.compiled_rules
            if any(p.search(target_text) for p in patterns)
        ]

        if self.match_all:
            missing = [kw for kw, _ in self.compiled_rules if kw not in matched]
            if missing:
                return False, 0, f"Faltan palabras clave: {', '.join(missing)}"
        elif not matched:
            return False, 0, "No incluye ninguna palabra clave requerida"

        return True, KEYWORD_SCORE * len(matched), ""


class RemoteOrLocationRule(BaseFilterRule):
    """Filtra por modalidad remota y/o ubicaciones permitidas."""

    def __init__(
        self,
        require_remote: bool = False,
        allowed_locations: Optional[List[str]] = None,
    ) -> None:
        """Normaliza las ubicaciones permitidas."""
        self.require_remote = require_remote
        self.allowed_locations = [
            normalize_text(loc) for loc in (allowed_locations or []) if loc
        ]

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        """Aplica las restricciones de remoto/ubicación y otorga un pequeño bonus al remoto."""
        loc_text = normalize_text(offer.get("location") or "")
        full_text = offer_text(offer)
        is_remote = bool(REMOTE_PATTERN.search(full_text))

        if self.require_remote and not is_remote:
            return False, 0, "Requiere modalidad remota"

        if self.allowed_locations and not is_remote:
            if not any(loc in loc_text for loc in self.allowed_locations):
                return False, 0, f"Ubicación no permitida: {offer.get('location')}"

        return True, (REMOTE_BONUS if is_remote else 0), ""


class JobFilterEngine:
    """Aplica una lista de reglas a las ofertas y las ordena por puntuación."""

    def __init__(self, rules: Optional[List[BaseFilterRule]] = None) -> None:
        """Guarda las reglas a aplicar, en orden."""
        self.rules: List[BaseFilterRule] = rules or []

    def is_relevant(self, offer: JobOffer) -> Tuple[bool, int, str]:
        """Devuelve (pasa, puntuación_total, motivo) para una oferta."""
        total_score = 0
        for rule in self.rules:
            passed, score, reason = rule.evaluate(offer)
            if not passed:
                return False, 0, reason
            total_score += score
        return True, total_score, ""

    def filter_offers(self, offers: List[JobOffer]) -> List[JobOffer]:
        """Filtra y ordena (mayor puntuación primero), registrando los descartes."""
        evaluated: List[Tuple[JobOffer, int]] = []
        for offer in offers:
            if not isinstance(offer, dict):
                logger.warning("Oferta ignorada: tipo inválido (%s)", type(offer).__name__)
                continue
            passed, score, reason = self.is_relevant(offer)
            if passed:
                evaluated.append((offer, score))
            else:
                logger.debug(
                    "Descartada [%s] %s -> %s", offer.get("id"), offer.get("title"), reason
                )

        logger.info("Filtro: %d de %d ofertas aceptadas", len(evaluated), len(offers))
        evaluated.sort(key=lambda item: item[1], reverse=True)
        return [item[0] for item in evaluated]


def create_job_filter_from_config(
    config_source: Optional[Any] = None,
    runtime_overrides: Optional[Dict[str, Any]] = None,
) -> JobFilterEngine:
    """Fábrica híbrida de motores de filtrado.

    1. Carga la configuración base (ruta a archivo JSON o diccionario).
    2. Aplica ``runtime_overrides`` si se solicita una búsqueda dinámica puntual.
    3. Usa valores por defecto para lo que no esté definido.
    """
    cfg: Dict[str, Any] = {}

    if isinstance(config_source, str):
        try:
            with open(config_source, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg = loaded
            else:
                logger.error("La configuración %s no es un objeto JSON. Usando defaults.", config_source)
        except (OSError, json.JSONDecodeError) as err:
            logger.error("No se pudo cargar la configuración base (%s). Usando defaults.", err)
    elif isinstance(config_source, dict):
        cfg = config_source.copy()

    if runtime_overrides:
        cfg.update(runtime_overrides)

    rules: List[BaseFilterRule] = [
        BlacklistRule(cfg.get("forbidden_keywords", DEFAULT_FORBIDDEN)),
        KeywordMatchRule(
            required_keywords=cfg.get("required_keywords", DEFAULT_REQUIRED),
            synonyms=cfg.get("synonyms", DEFAULT_SYNONYMS),
            match_all=cfg.get("match_all_keywords", False),
        ),
        RemoteOrLocationRule(
            require_remote=cfg.get("require_remote", False),
            allowed_locations=cfg.get("allowed_locations", []),
        ),
    ]

    return JobFilterEngine(rules=rules)