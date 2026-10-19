"""Motor de filtrado de ofertas de empleo basado en reglas (Patrón Estrategia)."""

import abc
import json
import logging
import os
import re
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from models import JobOffer

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
    """Devuelve 'título ubicación' normalizado (None-safe)."""
    title = offer.get("title") or ""
    location = offer.get("location") or ""
    return normalize_text(f"{title} {location}")


def build_tech_pattern(keyword: str) -> re.Pattern:
    """Regex precompilada con soporte para símbolos técnicos (c++, c#, .net).

    Solo se exige frontera de palabra en los extremos alfanuméricos, de modo que
    'java' no case con 'javascript' pero '.net' sí case con 'asp.net'.
    """
    norm_kw = normalize_text(keyword)
    start = r"(?<!\w)" if norm_kw and norm_kw[0].isalnum() else ""
    end = r"(?!\w)" if norm_kw and norm_kw[-1].isalnum() else ""
    return re.compile(f"{start}{re.escape(norm_kw)}{end}", re.IGNORECASE)


class BaseFilterRule(abc.ABC):
    """Interfaz abstracta para implementar el Patrón Estrategia."""

    @abc.abstractmethod
    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        """Evalúa una oferta y devuelve (pasa, puntuación, motivo_de_descarte)."""


class BlacklistRule(BaseFilterRule):
    """Descarta ofertas que contengan alguna palabra prohibida."""

    def __init__(self, forbidden_keywords: List[str]) -> None:
        self.forbidden_patterns = [(kw, build_tech_pattern(kw)) for kw in forbidden_keywords if kw]

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
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
        self.match_all = match_all
        self.synonyms = {normalize_text(k): v for k, v in (synonyms or {}).items()}
        self.compiled_rules: List[Tuple[str, List[re.Pattern]]] = []

        for kw in required_keywords:
            if not kw:
                continue
            terms = [kw] + self.synonyms.get(normalize_text(kw), [])
            self.compiled_rules.append((kw, [build_tech_pattern(t) for t in terms]))

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        if not self.compiled_rules:
            return True, 0, ""

        target_text = offer_text(offer)
        matched = [
            kw
            for kw, patterns in self.compiled_rules
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
        self.require_remote = require_remote
        self.allowed_locations = [normalize_text(loc) for loc in (allowed_locations or []) if loc]

    def evaluate(self, offer: JobOffer) -> Tuple[bool, int, str]:
        loc_text = normalize_text(offer.get("location") or "")
        is_remote = bool(REMOTE_PATTERN.search(offer_text(offer)))

        if self.require_remote and not is_remote:
            return False, 0, "Requiere modalidad remota"

        if self.allowed_locations and not is_remote:
            if not any(loc in loc_text for loc in self.allowed_locations):
                return False, 0, f"Ubicación no permitida: {offer.get('location')}"

        return True, (REMOTE_BONUS if is_remote else 0), ""


class JobFilterEngine:
    """Aplica una lista de reglas a las ofertas y las ordena por puntuación."""

    def __init__(self, rules: Optional[List[BaseFilterRule]] = None) -> None:
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
        """Filtra y ordena (mayor puntuación primero; estable), registrando descartes."""
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


def _as_list(cfg: Dict[str, Any], key: str, default: List[str]) -> List[str]:
    """Lee una lista de la config; None/ausente -> default; un str suelto -> [str]."""
    value = cfg.get(key)
    if value is None:
        return default
    return [value] if isinstance(value, str) else list(value)


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

    if isinstance(config_source, (str, os.PathLike)):
        try:
            with open(config_source, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg = loaded
            else:
                logger.error("%s no es un objeto JSON. Usando defaults.", config_source)
        except (OSError, json.JSONDecodeError) as err:
            logger.error("No se pudo cargar la configuración base (%s). Usando defaults.", err)
    elif isinstance(config_source, dict):
        cfg = config_source.copy()

    if runtime_overrides:
        cfg.update(runtime_overrides)

    synonyms = cfg.get("synonyms")
    rules: List[BaseFilterRule] = [
        BlacklistRule(_as_list(cfg, "forbidden_keywords", DEFAULT_FORBIDDEN)),
        KeywordMatchRule(
            required_keywords=_as_list(cfg, "required_keywords", DEFAULT_REQUIRED),
            synonyms=DEFAULT_SYNONYMS if synonyms is None else synonyms,
            match_all=bool(cfg.get("match_all_keywords", False)),
        ),
        RemoteOrLocationRule(
            require_remote=bool(cfg.get("require_remote", False)),
            allowed_locations=_as_list(cfg, "allowed_locations", []),
        ),
    ]
    return JobFilterEngine(rules=rules)
