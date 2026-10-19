import urllib.error

import pytest

from notifier import CompositeNotifier, NotificationError, build_notifier_from_env
from notifier import http
from notifier.discord import DiscordNotifier
from notifier.formatter import (
    DISCORD_LIMIT,
    TELEGRAM_LIMIT,
    build_messages,
    format_job_html,
    format_job_markdown,
)
from notifier.telegram import TelegramNotifier


def _job(n: int = 1, title: str = "Python Dev") -> dict:
    return {
        "id": str(n),
        "title": title,
        "company": "Acme",
        "location": "Remoto",
        "url": f"https://x.com/{n}",
        "source": "Test",
        "published_at": "2026-10-08 10:00",
    }


class Recorder:
    def __init__(self, fail: bool = False):
        self.calls, self.fail = [], fail

    def __call__(self, url, payload):
        if self.fail:
            raise NotificationError("caído")
        self.calls.append((url, payload))
        return 200


# --- Formato ---
def test_html_escapes_untrusted_content():
    text = format_job_html(_job(title="<script>alert(1)</script> & co"))
    assert "<script>" not in text and "&lt;script&gt;" in text and "&amp;" in text
    assert '<a href="https://x.com/1">' in text


def test_html_escapes_quotes_in_url():
    job = _job()
    job["url"] = 'https://x.com/"><b>'
    assert '"><b>' not in format_job_html(job)


def test_markdown_escapes_and_wraps_url():
    text = format_job_markdown(_job(title="**negrita** _x_"))
    assert "\\*\\*negrita\\*\\*" in text and text.endswith("<https://x.com/1>")


def test_long_fields_are_truncated():
    assert len(format_job_html(_job(title="x" * 5000))) < 800


@pytest.mark.parametrize("limit, fmt", [(2000, format_job_markdown), (4096, format_job_html)])
def test_build_messages_respects_limit_and_loses_nothing(limit, fmt):
    jobs = [_job(i) for i in range(60)]
    messages = build_messages(jobs, fmt, limit, header="HEADER")
    assert len(messages) > 1
    assert all(len(m) <= limit for m in messages)
    assert messages[0].startswith("HEADER") and not messages[1].startswith("HEADER")
    joined = "\n".join(messages)
    assert all(f"https://x.com/{i}" in joined for i in range(60))


def test_build_messages_empty():
    assert build_messages([], format_job_html, TELEGRAM_LIMIT, "H") == []
    assert DISCORD_LIMIT < TELEGRAM_LIMIT


# --- Telegram / Discord ---
def test_telegram_payload():
    rec = Recorder()
    TelegramNotifier("TOK", "42", pause=0, post=rec).send([_job()])
    url, payload = rec.calls[0]
    assert url == "https://api.telegram.org/botTOK/sendMessage"
    assert payload["chat_id"] == "42" and payload["parse_mode"] == "HTML"
    assert "1 oferta nueva" in payload["text"]


def test_telegram_requires_credentials():
    with pytest.raises(ValueError):
        TelegramNotifier("", "42")


def test_telegram_sends_nothing_for_empty_list():
    rec = Recorder()
    TelegramNotifier("T", "1", pause=0, post=rec).send([])
    assert rec.calls == []


def test_telegram_splits_into_several_messages():
    rec = Recorder()
    TelegramNotifier("T", "1", pause=0, post=rec).send([_job(i) for i in range(60)])
    assert len(rec.calls) > 1
    assert all(len(p["text"]) <= TELEGRAM_LIMIT for _, p in rec.calls)


def test_discord_payload_and_https_only():
    rec = Recorder()
    DiscordNotifier("https://discord.com/api/webhooks/1/abc", pause=0, post=rec).send([_job()])
    assert rec.calls[0][1]["content"].startswith("📢 **1 oferta nueva**")
    with pytest.raises(ValueError):
        DiscordNotifier("http://inseguro")


def test_notifier_propagates_failure():
    with pytest.raises(NotificationError):
        TelegramNotifier("T", "1", pause=0, post=Recorder(fail=True)).send([_job()])


# --- Composite ---
def test_composite_tolerates_partial_failure():
    ok, bad = Recorder(), Recorder(fail=True)
    CompositeNotifier(
        [
            TelegramNotifier("T", "1", pause=0, post=ok),
            DiscordNotifier("https://d.com/h", pause=0, post=bad),
        ]
    ).send([_job()])
    assert len(ok.calls) == 1


def test_composite_raises_when_all_fail():
    bad = Recorder(fail=True)
    composite = CompositeNotifier([TelegramNotifier("T", "1", pause=0, post=bad)])
    with pytest.raises(NotificationError):
        composite.send([_job()])


# --- Factory ---
def test_factory_no_channels():
    assert build_notifier_from_env({}) is None
    assert build_notifier_from_env({"TELEGRAM_BOT_TOKEN": "t"}) is None  # falta chat_id
    assert build_notifier_from_env({"TELEGRAM_BOT_TOKEN": "", "DISCORD_WEBHOOK_URL": ""}) is None


def test_factory_builds_both_channels():
    env = {
        "TELEGRAM_BOT_TOKEN": "t",
        "TELEGRAM_CHAT_ID": "1",
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/1/x",
    }
    assert len(build_notifier_from_env(env).notifiers) == 2


def test_factory_ignores_insecure_discord_url():
    assert build_notifier_from_env({"DISCORD_WEBHOOK_URL": "http://x"}) is None


# --- HTTP ---
def test_post_json_sends_user_agent_and_returns_status(mocker):
    urlopen = mocker.patch("urllib.request.urlopen")
    urlopen.return_value.__enter__.return_value.status = 204
    assert http.post_json("https://d.com/h", {"a": 1}) == 204
    request = urlopen.call_args[0][0]
    assert request.get_header("User-agent") == http.USER_AGENT
    assert request.get_method() == "POST"


def test_http_error_does_not_leak_secret(mocker):
    secret_url = "https://api.telegram.org/botSECRET123/sendMessage"
    mocker.patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(secret_url, 401, "Unauthorized", {}, None),
    )
    with pytest.raises(NotificationError) as info:
        http.post_json(secret_url, {})
    assert "SECRET123" not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_network_error_is_wrapped(mocker):
    mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sin red"))
    with pytest.raises(NotificationError):
        http.post_json("https://x.com", {})
