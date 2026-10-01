"""PDF report tests (no network: OpenRouter is mocked).   python tests/test_report_pdf.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import DEMO_DIR, settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.report import TrustReport  # noqa: E402
from app.services import flow, report_writer, reporter  # noqa: E402

client = TestClient(app)


def demo_report(name: str, kind: str) -> TrustReport:
    fixture = json.loads((DEMO_DIR / f"{name}.crew.json").read_text())
    text = (DEMO_DIR / {"scam_sms": "demo_scam_sms.txt", "viral_claim": "demo_claim.txt"}[name]).read_text().strip()
    return reporter.build(flow.run_sync(kind, text=text, fixture=fixture))


def pdf_text(data: bytes) -> str:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    return " ".join(" ".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf))).split())


class FakeResponse:
    def __init__(self, status: int, content: str):
        self.status_code, self._content = status, content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def with_openrouter(monkey_post, model="some/model:free"):
    settings.OPENROUTER_API_KEY, settings.OPENROUTER_REPORT_MODEL = "test-key", model
    report_writer.httpx.post = monkey_post


def reset():
    settings.OPENROUTER_API_KEY = settings.OPENROUTER_REPORT_MODEL = ""
    report_writer.httpx.post = httpx.post


def post_pdf(report: TrustReport):
    return client.post("/api/report/pdf", json={"report": report.model_dump()})


def main() -> None:
    scam, debunked = demo_report("scam_sms", "text"), demo_report("viral_claim", "claim")
    claim = reporter.build(flow.run_sync("claim", text="A new tax on bicycles starts next week.", fixture={
        "claim_evidence": {"claim": "A new tax on bicycles starts next week.", "evidence": []}, "tool_urls": {}}))

    # direct mode: HIGH RISK report
    r = post_pdf(scam)
    t = pdf_text(r.content)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    assert r.headers["x-trustlens-report-writer"] == "direct"
    assert f"{scam.trust_score} / 100" in t and "HIGH RISK" in t and "SOURCE: RULE" in t and "SOURCE: GEMINI" in t
    assert "not proof of authenticity or fraud" in t and "RECOMMENDED ACTION" in t
    print("ok direct HIGH")

    # UNVERIFIED claim never becomes true/false
    t = pdf_text(post_pdf(claim).content)
    assert "UNVERIFIED" in t and "remains unverified" in t and "DEBUNKED" not in t and "VERIFIED BY SOURCE" not in t
    print("ok UNVERIFIED")
    t = pdf_text(post_pdf(debunked).content)
    assert debunked.verdict == "DEBUNKED_BY_SOURCE" and "DEBUNKED BY SOURCE" in t and "EXTERNAL SOURCE" in t
    print("ok DEBUNKED with external sources")

    # tampered score is refused
    bad = scam.model_copy(update={"trust_score": 95, "risk_level": "LOW"})
    assert post_pdf(bad).status_code == 422
    print("ok tampered score refused")

    # OpenRouter: model tries to change score, risk, sources and add a signal -> facts stay pinned
    lying = {"title": "x", "executive_summary": "The message shows several detected signals that warrant caution.",
             "trust_score": 99, "risk_level": "LOW RISK", "input_type": "message",
             "signals": [{"severity": "LOW", "title": "Renamed", "source": "GEMINI", "explanation": "Reworded explanation."}
                         for _ in scam.signals],
             "evidence_summary": ["The link uses a shortener."], "recommendation": "Go ahead and pay.",
             "verification_steps": ["none"], "limitations": [], "disclaimer": "none"}
    with_openrouter(lambda *a, **k: FakeResponse(200, json.dumps(lying)))
    r = post_pdf(scam)
    t = pdf_text(r.content)
    assert r.headers["x-trustlens-report-writer"] == "openrouter"
    assert f"{scam.trust_score} / 100" in t and "HIGH RISK" in t and "99 / 100" not in t
    assert "Go ahead and pay" not in t and "Renamed" not in t and scam.signals[0].title in t
    assert "Reworded explanation." in t and "SOURCE: RULE" in t
    print("ok openrouter facts pinned")

    # extra signal invented -> model's signal text discarded entirely
    extra = dict(lying, signals=lying["signals"] + [{"severity": "HIGH", "title": "Invented", "source": "RULE", "explanation": "Invented."}])
    with_openrouter(lambda *a, **k: FakeResponse(200, json.dumps(extra)))
    t = pdf_text(post_pdf(scam).content)
    assert "Invented" not in t and "Reworded explanation." not in t
    print("ok invented signal dropped")

    # malformed JSON / HTTP error / timeout / over-claim / invented URL / paid model -> direct fallback, still a PDF
    cases = {
        "malformed": lambda *a, **k: FakeResponse(200, "Sure! Here is your report: {oops"),
        "http 404 (model gone)": lambda *a, **k: FakeResponse(404, ""),
        "timeout": lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("t")),
        "over-claim": lambda *a, **k: FakeResponse(200, json.dumps(dict(lying, executive_summary="This is definitely fake."))),
        "invented url": lambda *a, **k: FakeResponse(200, json.dumps(dict(lying, evidence_summary=["See https://evil.example/proof"]))),
    }
    for name, fn in cases.items():
        with_openrouter(fn)
        r = post_pdf(scam)
        assert r.status_code == 200 and r.headers["x-trustlens-report-writer"] == "direct", name
        assert "definitely" not in pdf_text(r.content) and "evil.example" not in pdf_text(r.content)
        print("ok fallback:", name)
    called = []
    with_openrouter(lambda *a, **k: called.append(1) or FakeResponse(200, json.dumps(lying)), model="openai/gpt-paid")
    r = post_pdf(scam)
    assert r.headers["x-trustlens-report-writer"] == "direct" and not called
    print("ok paid model never called")
    reset()

    # analysis itself is independent of OpenRouter
    assert client.post("/api/analyze/demo/genuine_notice").status_code == 200
    assert client.post("/api/report/pdf", json={"report": {"nope": 1}}).status_code == 422
    assert client.post("/api/report/pdf", json={}).status_code == 422
    print("ALL PASSED")


if __name__ == "__main__":
    main()
