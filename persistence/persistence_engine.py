"""Persistencia ligera de ofertas ya notificadas (idempotencia)."""

import contextlib
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from models import JobOffer

logger = logging.getLogger("PersistenceEngine")

STATE_VERSION = "1.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(value: Any) -> Optional[datetime]:
    """Parsea ISO 8601; las fechas sin zona horaria se interpretan como UTC."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class PersistenceEngine:
    """Registro de ofertas vistas en JSON. Implementa el protocolo JobStore de main."""

    def __init__(
        self, filepath: Union[str, Path] = "data/seen_jobs.json", retention_days: int = 90
    ) -> None:
        self.filepath = Path(filepath)
        self.retention_days = retention_days
        self._data: Dict[str, Any] = self._load()

    @staticmethod
    def _empty_state() -> Dict[str, Any]:
        return {"version": STATE_VERSION, "last_updated": _now().isoformat(), "seen_jobs": {}}

    def _load(self) -> Dict[str, Any]:
        """Carga el estado; ante ausencia, corrupción o estructura inválida parte de cero."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return self._empty_state()
        except (OSError, json.JSONDecodeError) as err:
            logger.error("Estado ilegible (%s); se parte de cero.", err)
            return self._empty_state()

        if not isinstance(data, dict) or not isinstance(data.get("seen_jobs"), dict):
            logger.error("Estructura de estado inválida; se parte de cero.")
            return self._empty_state()
        return data

    @property
    def seen_jobs(self) -> Dict[str, Dict[str, Any]]:
        return self._data["seen_jobs"]

    def is_seen(self, job_id: str) -> bool:
        """Comprobación O(1) en memoria."""
        return job_id in self.seen_jobs

    def only_new(self, jobs: List[JobOffer]) -> List[JobOffer]:
        """Devuelve solo las ofertas que aún no se han notificado."""
        return [job for job in jobs if job["id"] not in self.seen_jobs]

    def mark_seen(self, jobs: List[JobOffer]) -> None:
        """Registra las ofertas, purga las caducadas y persiste (una sola escritura)."""
        now = _now().isoformat()
        for job in jobs:
            previous = self.seen_jobs.get(job["id"], {})
            self.seen_jobs[job["id"]] = {
                "title": job["title"],
                "url": job["url"],
                "source": job["source"],
                "first_seen_at": previous.get("first_seen_at", now),
            }
        self.purge_old()
        self.save()

    def purge_old(self, days: Optional[int] = None) -> int:
        """Elimina ofertas vistas hace más de `days` días. Devuelve cuántas se eliminaron."""
        cutoff = _now() - timedelta(days=self.retention_days if days is None else days)
        kept: Dict[str, Dict[str, Any]] = {}
        for job_id, info in self.seen_jobs.items():
            first_seen = _parse_utc(info.get("first_seen_at"))
            if first_seen is None:  # fecha rota: se reinicia para que caduque algún día
                first_seen = _now()
                info["first_seen_at"] = first_seen.isoformat()
            if first_seen >= cutoff:
                kept[job_id] = info
        removed = len(self.seen_jobs) - len(kept)
        self._data["seen_jobs"] = kept
        return removed

    def save(self) -> None:
        """Escritura atómica: archivo temporal + os.replace (sin JSON a medias)."""
        self._data["last_updated"] = _now().isoformat()
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self.filepath.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(self._data, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, self.filepath)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
