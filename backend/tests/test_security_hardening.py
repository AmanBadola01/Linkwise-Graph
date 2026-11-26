"""Security hardening tests (malware scan 2026-11-25).

Covers: Text2Cypher validator (LLM output is untrusted) and the PDF
active-content upload check. Pure unit tests - no DB/LLM needed.
"""
import os

from backend.app.api.v1.ingest import find_active_pdf_content
from backend.app.services.graph.graph_retriever import validate_readonly_cypher

ACC = "acc-123"
GOOD = "MATCH (n:Entity {account_id: 'acc-123'}) RETURN n.name AS name"


def test_cypher_allows_tenant_scoped_read_and_adds_limit():
    out = validate_readonly_cypher(GOOD, ACC)
    assert out is not None and out.endswith("LIMIT 100")


def test_cypher_clamps_oversized_limit():
    out = validate_readonly_cypher(GOOD + " LIMIT 99999", ACC)
    assert out is not None and out.endswith("LIMIT 100")


def test_cypher_rejects_writes_and_admin():
    for bad in [
        "MATCH (n:Entity {account_id: 'acc-123'}) DELETE n",
        "MATCH (n:Entity {account_id: 'acc-123'}) SET n.x = 1 RETURN n",
        "CREATE (n:Entity {account_id: 'acc-123'}) RETURN n",
        "MATCH (n:Entity {account_id: 'acc-123'}) MERGE (m:Entity) RETURN m",
    ]:
        assert validate_readonly_cypher(bad, ACC) is None, bad


def test_cypher_rejects_load_csv_and_call_bypasses():
    # LOAD CSV reads local files / remote URLs; CALL was previously allowed
    # whenever the text contained "db.index".
    assert validate_readonly_cypher(
        "LOAD CSV FROM 'file:///etc/passwd' AS row RETURN row", ACC) is None
    assert validate_readonly_cypher(
        "MATCH (n:Entity {account_id: 'acc-123'}) CALL db.index.fulltext.queryNodes('x','y') RETURN n", ACC) is None
    assert validate_readonly_cypher(
        "CALL apoc.load.json('http://169.254.169.254/latest/meta-data') YIELD value RETURN value", ACC) is None


def test_cypher_rejects_cross_tenant_and_multi_statement():
    assert validate_readonly_cypher("MATCH (n:Entity) RETURN n", ACC) is None
    assert validate_readonly_cypher(
        "MATCH (n:Entity {account_id: 'other-tenant'}) RETURN n", ACC) is None
    assert validate_readonly_cypher(GOOD + "; MATCH (m:Entity {account_id: 'acc-123'}) RETURN m", ACC) is None


def _write_pdf(path: str, extra_catalog: str = "") -> None:
    objs = [
        f"<< /Type /Catalog /Pages 2 0 R {extra_catalog} >>",
        "<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        "<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 740 Td (Hello World Test) Tj ET\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as f:
        f.write(out)


def test_pdf_active_content_detected(tmp_path):
    evil = str(tmp_path / "evil.pdf")
    _write_pdf(evil, "/OpenAction << /S /JavaScript /JS (app.alert\\(1\\)) >>")
    found = find_active_pdf_content(evil)
    assert "/JS" in found or "/JavaScript" in found


def test_pdf_clean_file_passes(tmp_path):
    clean = str(tmp_path / "clean.pdf")
    _write_pdf(clean)
    assert find_active_pdf_content(clean) == []
    sample = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test-fixtures", "sample.pdf")
    if os.path.exists(sample):
        assert find_active_pdf_content(sample) == []
