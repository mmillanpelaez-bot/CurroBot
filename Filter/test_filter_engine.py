"""Tests del motor de filtrado."""
import logging
from typing import Dict, List

import pytest

from Filter.filter_engine import create_job_filter_from_config
from Filter.Model import JobOffer


def make_offer(title, location="Remoto", **kw) -> dict:
    base = {
        "id": "x", "title": title, "company": "Desconocida", "location": location,
        "url": "https://example.com/x", "source": "Test",
        "published_at": "2026-10-05 10:00",
    }
    base.update(kw)
    return base


def run(cfg: dict, *offers) -> list:
    return create_job_filter_from_config(cfg).filter_offers(list(offers))


@pytest.fixture
def sample_offers() -> List[JobOffer]:
    return [
        make_offer("Desarrollador Python Junior", id="1", company="Company A",
                   source="Tecnoempleo", published_at="2026-10-01 10:00"),
        make_offer("Frontend React Developer", location="Madrid", id="2",
                   company="Company B", source="RemoteOK", published_at="2026-10-01 11:00"),
    ]


@pytest.fixture
def base_config() -> Dict[str, list]:
    return {"forbidden_keywords": ["senior"], "required_keywords": ["python"]}


# --- Modo dual ---
def test_default_base_config_mode(sample_offers, base_config):
    """Modo 1: usa la configuración base sin sobreescrituras."""
    filtered = create_job_filter_from_config(base_config).filter_offers(sample_offers)
    assert [o["id"] for o in filtered] == ["1"]


def test_runtime_override_mode(sample_offers, base_config):
    """Modo 2: criterios dinámicos en tiempo de ejecución."""
    engine = create_job_filter_from_config(base_config, runtime_overrides={"required_keywords": ["react"]})
    assert [o["id"] for o in engine.filter_offers(sample_offers)] == ["2"]


def test_runtime_override_replaces_not_merges():
    engine = create_job_filter_from_config(
        {"required_keywords": ["python"]}, runtime_overrides={"required_keywords": ["react"]}
    )
    assert engine.filter_offers([make_offer("Python Dev")]) == []


# --- Ofertas ambiguas ---
@pytest.mark.parametrize("keyword, title, expected", [
    ("java", "JavaScript Developer", 0),
    ("c++", "Programador C++", 1),
    ("c#", "Desarrollador C# .NET", 1),
    ("c++", "Programador C", 0),
    (".net", "Backend .NET", 1),
    ("programacion", "Técnico de Programación", 1),
])
def test_ambiguous_keywords(keyword, title, expected):
    assert len(run({"required_keywords": [keyword]}, make_offer(title))) == expected


def test_senior_not_matched_inside_other_word():
    cfg = {"forbidden_keywords": ["senior"], "required_keywords": ["python"]}
    assert len(run(cfg, make_offer("Python Seniority Program"))) == 1


# --- Descartes ---
def test_blacklist_discards():
    cfg = {"forbidden_keywords": ["senior"], "required_keywords": ["python"]}
    assert run(cfg, make_offer("Senior Python Developer")) == []


def test_require_remote_discards_onsite():
    cfg = {"required_keywords": ["python"], "require_remote": True}
    assert run(cfg, make_offer("Python Dev", location="Madrid")) == []


def test_allowed_locations():
    cfg = {"required_keywords": ["python"], "allowed_locations": ["Madrid"]}
    assert run(cfg, make_offer("Python Dev", location="Barcelona")) == []
    assert len(run(cfg, make_offer("Python Dev", location="Madrid"))) == 1


def test_remote_is_word_not_substring():
    cfg = {"required_keywords": ["python"], "require_remote": True}
    assert run(cfg, make_offer("Python Dev", location="Remotely located office")) == []


def test_teletrabajo_is_remote():
    cfg = {"required_keywords": ["python"], "require_remote": True}
    assert len(run(cfg, make_offer("Python Dev", location="Teletrabajo"))) == 1


# --- match_all ---
def test_match_all_requires_every_keyword():
    cfg = {"required_keywords": ["python", "django"], "match_all_keywords": True}
    assert run(cfg, make_offer("Python Dev")) == []
    assert len(run(cfg, make_offer("Python Django Dev"))) == 1


def test_match_any_is_default():
    assert len(run({"required_keywords": ["python", "django"]}, make_offer("Python Dev"))) == 1


# --- Sinónimos ---
def test_synonyms():
    assert len(run({"required_keywords": ["python"]}, make_offer("Py Developer"))) == 1


def test_nodejs_synonym():
    assert len(run({"required_keywords": ["node.js"]}, make_offer("Backend NodeJS"))) == 1


def test_custom_synonym_keys_are_normalized():
    cfg = {"required_keywords": ["Programación"], "synonyms": {"programacion": ["coding"]}}
    assert len(run(cfg, make_offer("Coding Wizard"))) == 1


# --- Robustez ---
def test_empty_list_and_invalid_items(caplog):
    engine = create_job_filter_from_config({})
    assert engine.filter_offers([]) == []
    with caplog.at_level(logging.WARNING):
        assert engine.filter_offers(["no soy dict", None]) == []
    assert "tipo inválido" in caplog.text


def test_none_fields_do_not_crash():
    assert run({"required_keywords": ["python"]}, make_offer(None, location=None)) == []


def test_none_title_is_not_text_none():
    assert run({"required_keywords": ["none"]}, make_offer(None)) == []


def test_missing_config_file_uses_defaults(caplog):
    with caplog.at_level(logging.ERROR):
        assert create_job_filter_from_config("no_existe.json") is not None
    assert "No se pudo cargar" in caplog.text


def test_invalid_json_file_uses_defaults(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{no es json")
    assert create_job_filter_from_config(str(bad)) is not None


def test_valid_json_file(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text('{"required_keywords": ["rust"]}')
    engine = create_job_filter_from_config(str(f))
    assert len(engine.filter_offers([make_offer("Rust Dev")])) == 1


# --- Orden y logging ---
def test_sorted_by_score():
    cfg = {"required_keywords": ["python", "junior"]}
    low, high = make_offer("Python Dev", location="Madrid"), make_offer("Python Junior")
    assert run(cfg, low, high)[0] == high


def test_discard_reason_is_logged(caplog):
    cfg = {"forbidden_keywords": ["senior"], "required_keywords": ["python"]}
    with caplog.at_level(logging.DEBUG):
        run(cfg, make_offer("Senior Python"))
    assert "palabra prohibida" in caplog.text