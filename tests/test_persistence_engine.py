import json
from datetime import datetime, timedelta, timezone

from persistence.persistence_engine import PersistenceEngine


def _job(job_id: str) -> dict:
    return {
        "id": job_id,
        "title": "Dev",
        "company": "X",
        "location": "Remoto",
        "url": f"https://x.com/{job_id}",
        "source": "Test",
        "published_at": "2026-10-08 10:00",
    }


def test_first_run_does_not_crash_and_creates_nothing(tmp_path):
    path = tmp_path / "data" / "seen.json"
    engine = PersistenceEngine(path)
    assert engine.only_new([_job("a")]) == [_job("a")]
    assert not path.exists()  # el constructor no escribe


def test_mark_seen_persists_and_is_idempotent(tmp_path):
    path = tmp_path / "data" / "seen.json"
    PersistenceEngine(path).mark_seen([_job("a"), _job("b")])

    reloaded = PersistenceEngine(path)
    assert reloaded.is_seen("a")
    assert [j["id"] for j in reloaded.only_new([_job("a"), _job("c")])] == ["c"]


def test_corrupt_file_starts_empty(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{no es json")
    assert PersistenceEngine(path).seen_jobs == {}


def test_valid_json_without_seen_jobs_starts_empty(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"version": "1.0"}))
    assert PersistenceEngine(path).seen_jobs == {}


def test_purge_old_handles_naive_and_invalid_dates(tmp_path):
    engine = PersistenceEngine(tmp_path / "seen.json", retention_days=30)
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    naive_old = (datetime.now() - timedelta(days=40)).replace(tzinfo=None).isoformat()
    engine.seen_jobs.update(
        {
            "old": {"first_seen_at": old},
            "naive_old": {"first_seen_at": naive_old},
            "broken": {"first_seen_at": "ayer"},
            "fresh": {"first_seen_at": datetime.now(timezone.utc).isoformat()},
        }
    )
    assert engine.purge_old() == 2
    assert set(engine.seen_jobs) == {"broken", "fresh"}


def test_first_seen_is_preserved_on_remark(tmp_path):
    engine = PersistenceEngine(tmp_path / "seen.json")
    engine.mark_seen([_job("a")])
    first = engine.seen_jobs["a"]["first_seen_at"]
    engine.mark_seen([_job("a")])
    assert engine.seen_jobs["a"]["first_seen_at"] == first
