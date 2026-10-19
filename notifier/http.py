"""Cliente HTTP mínimo (stdlib) para los notificadores."""

import json
import urllib.error
import urllib.request
from typing import Any, Dict

USER_AGENT = "CurroBot/1.0 (job alerts; educational project)"
REQUEST_TIMEOUT = 15


class NotificationError(RuntimeError):
    """No se pudo entregar una notificación."""


def post_json(url: str, payload: Dict[str, Any], timeout: int = REQUEST_TIMEOUT) -> int:
    """POST JSON y devuelve el código HTTP.

    Las URLs de Telegram/Discord contienen secretos, así que los errores se
    relanzan SIN encadenar la excepción original (``from None``): ni el mensaje
    ni el traceback pueden filtrar el token.
    """
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as err:
        raise NotificationError(f"HTTP {err.code} al enviar la notificación") from None
    except (urllib.error.URLError, OSError) as err:
        raise NotificationError(f"Error de red al notificar ({type(err).__name__})") from None
