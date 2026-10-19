"""Configuración de fuentes RSS (config/feeds.json)."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger("DataFetcher")


@dataclass(frozen=True)
class Feed:
    url: str
    source: str
    default_location: str = "No especificada"


DEFAULT_FEEDS: List[Feed] = [
    Feed("https://remoteok.com/remote-jobs.rss", "RemoteOK", "Remoto"),
]


def load_feeds(path: Optional[Union[str, Path]]) -> List[Feed]:
    """Lee los feeds del JSON; ante cualquier problema usa DEFAULT_FEEDS."""
    if path is None or not Path(path).exists():
        logger.warning("Sin fichero de feeds (%s); se usan los de por defecto.", path)
        return list(DEFAULT_FEEDS)
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = raw["feeds"]
        if not isinstance(items, list):
            raise TypeError("'feeds' debe ser una lista")
    except (OSError, ValueError, KeyError, TypeError) as err:
        logger.error("feeds.json inválido (%s); se usan los de por defecto.", err)
        return list(DEFAULT_FEEDS)

    feeds: List[Feed] = []
    for item in items:
        if isinstance(item, dict) and item.get("url") and item.get("source"):
            feeds.append(
                Feed(
                    str(item["url"]),
                    str(item["source"]),
                    str(item.get("default_location") or "No especificada"),
                )
            )
        else:
            logger.warning("Feed ignorado (falta url/source): %r", item)
    return feeds or list(DEFAULT_FEEDS)
