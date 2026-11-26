"""Regression tests for the QA defect log (BUG-01/02/03/04/07/14/24)."""
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from backend.app.services.auth import security
from conftest import StubExtractor, make_user, upload_sample

PASSWORD = "PytestPass123!"


def test_forged_token_with_old_default_secret_rejected(client):
    forged = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "exp": 9999999999},
        "change-me-in-production-linkwise-graph",
        algorithm="HS256",
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_expired_token_rejected(client):
    user = make_user(client)
    expired = pyjwt.encode(
        {
            "sub": "x",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iss": security.JWT_ISSUER,
            "aud": security.JWT_AUDIENCE,
            "tv": 0,
        },
        security.JWT_SECRET,
        algorithm="HS256",
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert user  # silence unused


def test_login_rate_limit_returns_429(client):
    user = make_user(client)
    codes = []
    for _ in range(6):
        r = client.post("/api/v1/auth/login", json={"email": user["email"], "password": "WrongPass123!"})
        codes.append(r.status_code)
    assert 429 in codes, codes


def test_two_user_isolation_and_ingest_on_nonempty_db(client):
    # Non-empty DB: other tenants + quarantined legacy nodes already exist.
    user_a = make_user(client)
    r = upload_sample(client, user_a["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["nodes_created"] > 0

    user_b = make_user(client)
    graph_b = client.get("/api/v1/graph", headers=user_b["headers"])
    assert graph_b.status_code == 200
    assert graph_b.json()["total_nodes"] == 0

    graph_a = client.get("/api/v1/graph", headers=user_a["headers"])
    assert graph_a.json()["total_nodes"] > 0


def test_ingest_dedupe_does_not_rebill_extraction(client):
    user = make_user(client)
    before = StubExtractor.calls
    r1 = upload_sample(client, user["headers"])
    assert r1.status_code == 200, r1.text
    started = time.monotonic()
    r2 = upload_sample(client, user["headers"])
    elapsed = time.monotonic() - started
    assert r2.status_code == 200
    assert StubExtractor.calls == before + 1, "second identical upload must hit the dedupe cache"
    assert elapsed < 5


def test_clear_with_corrupt_file_keeps_existing_data(client):
    user = make_user(client)
    r = upload_sample(client, user["headers"])
    assert r.status_code == 200, r.text

    corrupt = client.post(
        "/api/v1/ingest?clear_existing=true",
        headers=user["headers"],
        files={"file": ("fake.pdf", b"definitely not a pdf", "application/pdf")},
    )
    assert corrupt.status_code == 422, corrupt.text
    assert "Stream has ended" not in corrupt.text

    graph = client.get("/api/v1/graph", headers=user["headers"])
    assert graph.json()["total_nodes"] > 0, "clear+corrupt must not wipe existing data"


def test_failed_ingest_leaves_no_queryable_data(client, monkeypatch):
    """BUG-03: a Neo4j failure mid-ingest must not leave vectors behind."""
    import backend.app.api.v1.ingest as ingest_mod

    def boom(self, nodes):
        raise RuntimeError("simulated Neo4j failure")

    monkeypatch.setattr(ingest_mod.GraphBuilder, "ingest_nodes", boom)
    user = make_user(client)
    r = upload_sample(client, user["headers"])
    assert r.status_code == 500, r.text
    monkeypatch.undo()

    q = client.post(
        "/api/v1/query",
        headers=user["headers"],
        json={"query": "Who leads the Query Engine?", "mode": "vector", "top_k": 3},
    )
    assert q.status_code == 200
    assert q.json()["matched_chunks"] == [], "failed ingest left queryable vectors behind"


def test_synthesis_failure_is_friendly_503_without_provider_payload(client, monkeypatch):
    """QA residual: Gemini 503 during synthesis -> friendly 503, no raw JSON."""
    import backend.app.api.v1.query as query_mod
    from backend.app.services.llm_errors import SynthesisUnavailableError

    class FailingSynthesizer:
        def synthesize(self, *args, **kwargs):
            raise SynthesisUnavailableError(SynthesisUnavailableError.friendly_message)

    monkeypatch.setattr(query_mod, "VectorSynthesizer", FailingSynthesizer)
    user = make_user(client)
    r = client.post(
        "/api/v1/query",
        headers=user["headers"],
        json={"query": "Who leads the Query Engine?", "mode": "vector", "top_k": 3},
    )
    assert r.status_code == 503, r.text
    assert "UNAVAILABLE" not in r.text and "503" not in r.json()["detail"]
    assert "try again" in r.json()["detail"].lower()


def test_synthesizer_maps_provider_exception_without_leaking():
    from backend.app.models.vector import MatchedChunk
    from backend.app.services.llm_errors import SynthesisUnavailableError
    from backend.app.services.vector.vector_synthesizer import VectorSynthesizer

    synth = VectorSynthesizer.__new__(VectorSynthesizer)
    synth.model_name = "stub"

    class FakeModels:
        def generate_content(self, **kwargs):
            raise RuntimeError("503 UNAVAILABLE {'error': {'code': 503}}")

    synth.client = type("C", (), {"models": FakeModels()})()
    chunk = MatchedChunk(
        chunk_id="c1", document_name="sample.pdf", page_number=1,
        section_title="S", content="Bob Smith leads the Query Engine.", score=0.9,
    )
    try:
        synth.synthesize("Who leads the Query Engine?", [chunk], top_k=3)
        raise AssertionError("expected SynthesisUnavailableError")
    except SynthesisUnavailableError as e:
        assert "UNAVAILABLE" not in str(e)
        assert "try again" in str(e).lower()


def test_logout_revokes_token(client):
    user = make_user(client)
    r = client.post("/api/v1/auth/logout", headers=user["headers"])
    assert r.status_code == 200
    r = client.get("/api/v1/auth/me", headers=user["headers"])
    assert r.status_code == 401
