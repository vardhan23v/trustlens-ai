"""PDF Trust Report. The posted TrustLens analysis is the source of truth; nothing is re-analysed."""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.report import TrustReport
from app.rules.scoring import band
from app.services import pdf_report_service, report_writer, reporter

router = APIRouter()
log = logging.getLogger("trustlens.report")
UNAVAILABLE = "PDF generation is temporarily unavailable. Your TrustLens analysis is still available."


class PdfIn(BaseModel):
    report: TrustReport


def _verify(report: TrustReport) -> None:
    """The app is stateless, so the score is re-derived from the posted signals with the real scoring
    code. A report whose score or risk level does not follow from its signals is refused."""
    score, _ = reporter.score([s.model_copy() for s in report.signals])
    risk = band(score)
    if risk == "LOW" and any(s.severity == "high" for s in report.signals):
        risk = "MEDIUM"
    if score != report.trust_score or risk != report.risk_level:
        raise HTTPException(422, "This analysis result is inconsistent and cannot be turned into a report. "
                                 "Please run the analysis again.")


@router.post("/report/pdf")
def report_pdf(body: PdfIn):
    _verify(body.report)
    try:
        doc, writer = report_writer.write(body.report)
        pdf, report_id = pdf_report_service.build_pdf(doc, body.report, writer)
    except Exception:
        log.exception("PDF generation failed")
        raise HTTPException(503, UNAVAILABLE)
    name = f"TrustLens_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "X-TrustLens-Report-Id": report_id, "X-TrustLens-Report-Writer": writer,
    })
