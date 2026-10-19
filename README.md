# 🤖 CurroBot — Bot de Alertas de Empleo (IPE · DAM)

Bot en Python (presupuesto 0 €) que descarga ofertas de feeds RSS, las filtra por palabras
clave, descarta las ya notificadas y envía las nuevas por Telegram y/o Discord. Se ejecuta
solo cada 3 horas con GitHub Actions.

```
config/feeds.json ─> fetcher ─> filters ─> persistence.only_new ─> notifier ─> persistence.mark_seen
                    (Martín)   (Sergio)       (Breixo)              (René)        (Breixo)
                                     main.py + workflows (Felipe)
```

## Puesta en marcha (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # rellena los secretos (nunca se suben)

python main.py --dry-run          # descarga y filtra; NO envía ni guarda
python main.py --test-notify      # envía una oferta de prueba (verifica los secretos)
python main.py                    # ejecución real
black . && flake8 . && pytest -q  # lo mismo que corre el CI
```

Opciones: `--max-alerts N` (por defecto 20), `--feeds-file`, `--config`, `--state-file`,
`--log-level DEBUG`. Códigos de salida: `0` ok · `1` ningún feed respondió / sin canal ·
`2` fallo al notificar.

## Configurar los canales

**Telegram**
1. En Telegram habla con `@BotFather` → `/newbot` → copia el **token**.
2. Escribe cualquier mensaje a tu bot (o añádelo a un grupo y escribe allí).
3. Abre `https://api.telegram.org/bot<TOKEN>/getUpdates` y copia `chat.id` → `TELEGRAM_CHAT_ID`.

**Discord**: Ajustes del canal → Integraciones → Webhooks → Nuevo webhook → copia la URL
→ `DISCORD_WEBHOOK_URL`.

Con uno de los dos canales basta. Si hay ambos, se usan los dos.

## Despliegue en GitHub Actions

1. *Settings → Secrets and variables → Actions → New repository secret*:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` y/o `DISCORD_WEBHOOK_URL`.
2. *Settings → Actions → General → Workflow permissions* → **Read and write permissions**.
3. Pestaña *Actions → Job alerts → Run workflow* para lanzarlo a mano. Después corre solo.

El estado (`data/seen_jobs.json`) se guarda con un commit automático tras cada envío correcto,
así no se repite ninguna oferta.

## Personalizar

- Fuentes: `config/feeds.json` (`default_location` rellena la ubicación si el feed no la trae).
- Filtros: `config/filters.json` (`forbidden_keywords`, `required_keywords`, `require_remote`…).

## Contrato de datos

Todos los módulos consumen y devuelven `JobOffer` (definido solo en `models.py`):
`id, title, company, location, url, source, published_at (YYYY-MM-DD HH:MM)`.

## Equipo

| Persona | Módulo |
|---|---|
| Felipe (DevOps) | `main.py`, `.github/workflows/`, secretos |
| Martín (Fetcher) | `fetcher/`, `config/feeds.json` |
| Sergio (Filtro) | `filters/`, `config/filters.json` |
| Breixo (Persistencia) | `persistence/` |
| René (Notifier) | `notifier/` |
