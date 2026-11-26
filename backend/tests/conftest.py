"""Test setup: isolated auth DB, real Neo4j/Chroma (tenant-scoped users),
Gemini extraction stubbed so tests never bill the LLM.

Run from the repo root:  .venv/bin/python -m pytest backend/tests -v
Requires Neo4j on bolt://localhost:7687 and the repo .env (JWT_SECRET etc.).
"""
import os
import sys
import tempfile
import uuid

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

# Isolated auth DB for tests; must be set before backend imports read it.
os.environ.setdefault("AUTH_DB_PATH", os.path.join(tempfile.mkdtemp(prefix="lw-test-auth-"), "auth.db"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(REPO_ROOT, ".env"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import backend.app.api.v1.ingest as ingest_mod  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models.graph import ExtractedEntity as E, ExtractedRelationship as R  # noqa: E402

SAMPLE_PDF = os.path.join(REPO_ROOT, "..", "test-fixtures", "sample.pdf")
if not os.path.exists(SAMPLE_PDF):
    SAMPLE_PDF = os.path.join(REPO_ROOT, "frontend", "public", "sample.pdf")

ENTS = [
    E(name="Alice Johnson", type="Person", description="Lead Architect", source_section="s", page_number=1),
    E(name="Atlas Platform", type="Organization", description="Team", source_section="s", page_number=1),
    E(name="Query Engine", type="System", description="Answers queries", source_section="s", page_number=2),
    E(name="Bob Smith", type="Person", description="Leads the Query Engine", source_section="s", page_number=1),
]
RELS = [
    R(source="Bob Smith", target="Query Engine", type="LEADS", description="leads", confidence=0.9, source_section="s", page_number=1),
    R(source="Alice Johnson", target="Atlas Platform", type="LEADS", description="leads", confidence=0.9, source_section="s", page_number=1),
]


class StubExtractor:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def extract_from_sections(self, sections):
        StubExtractor.calls += 1
        return list(ENTS), list(RELS), 0


@pytest.fixture(scope="session")
def client():
    ingest_mod.EntityExtractor = StubExtractor
    with TestClient(app) as c:
        yield c


def make_user(client: TestClient) -> dict:
    email = f"pytest-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "PytestPass123!", "display_name": "Pytest"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return {"email": email, "token": body["access_token"], "headers": {"Authorization": f"Bearer {body['access_token']}"}}


def upload_sample(client: TestClient, headers: dict, params: str = ""):
    with open(SAMPLE_PDF, "rb") as f:
        return client.post(
            f"/api/v1/ingest{params}",
            headers=headers,
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
