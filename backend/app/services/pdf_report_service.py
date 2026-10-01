"""TrustLens PDF report (ReportLab Platypus), generated in memory. LLM → JSON, Python → PDF."""
import io
import re
import uuid
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.report import TrustReport
from app.services.report_writer import ReportDoc

INK, MUTED, LINE, PANEL = colors.HexColor("#0B0F17"), colors.HexColor("#5B6678"), colors.HexColor("#D5DBE5"), colors.HexColor("#F3F5F9")
ACCENT = colors.HexColor("#0E7490")
RISK = {"LOW": colors.HexColor("#15803D"), "MEDIUM": colors.HexColor("#B45309"), "HIGH": colors.HexColor("#B91C1C")}
SEV = {"HIGH": colors.HexColor("#B91C1C"), "MEDIUM": colors.HexColor("#C2410C"), "LOW": colors.HexColor("#A16207")}
SOURCE = {"RULE": "#4F46E5", "GEMINI": "#0F766E"}

_REPL = {"₹": "Rs ", "—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...", "×": "x", "·": "-", "≈": "~"}


def _t(text: str, limit: int = 1200) -> str:
    """Escape for Paragraph markup. The built-in PDF fonts are Latin-only, so other scripts are marked."""
    text = str(text or "")
    for a, b in _REPL.items():
        text = text.replace(a, b)
    text = re.sub(r"[^\x09\x0a\x20-\x7e\xa0-\xff]+", " [non-Latin text] ", text)
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return escape(text)


def _styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="Helvetica", fontSize=10, leading=14.5, textColor=INK)
    return {
        "body": ParagraphStyle("body", **base),
        "muted": ParagraphStyle("muted", **{**base, "fontSize": 8.5, "leading": 12, "textColor": MUTED}),
        "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=ACCENT, spaceBefore=14, spaceAfter=6),
        "brand": ParagraphStyle("brand", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.white),
        "sub": ParagraphStyle("sub", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=colors.HexColor("#67E8F9")),
        "tag": ParagraphStyle("tag", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=colors.HexColor("#CBD5E1")),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_CENTER),
        "big": ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, alignment=TA_CENTER),
        "sig": ParagraphStyle("sig", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=INK),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#334155")),
        "rec": ParagraphStyle("rec", fontName="Helvetica-Bold", fontSize=10.5, leading=15, textColor=INK),
    }


def _source_badges(source: str) -> str:
    out = []
    for name in [s.strip() for s in source.split("+") if s.strip()]:
        out.append(f'<font face="Helvetica-Bold" size="7.5" color="{SOURCE.get(name, "#475569")}">SOURCE: {escape(name)}</font>')
    return " &nbsp; ".join(out)


def _footer(report_id: str, generated: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"TrustLens AI - Digital Trust Report - {report_id} - {generated}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def build_pdf(doc: ReportDoc, report: TrustReport, writer: str) -> tuple[bytes, str]:
    """Return (pdf bytes, report id). Score, risk level and signals are printed from the TrustLens result."""
    st = _styles()
    report_id = "TL-" + uuid.uuid4().hex[:10].upper()
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    width = A4[0] - 36 * mm
    story = []

    header = Table([[Paragraph("TRUSTLENS AI", st["brand"])], [Paragraph("DIGITAL TRUST REPORT", st["sub"])],
                    [Paragraph("See Beyond the Digital Surface.", st["tag"])]], colWidths=[width])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), INK), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                ("TOPPADDING", (0, 0), (0, 0), 14), ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
                                ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 1)]))
    story += [header, Spacer(1, 10)]

    risk_color = RISK.get(report.risk_level, INK)
    big_risk = ParagraphStyle("risk", parent=st["big"], textColor=risk_color, fontSize=15)
    big_score = ParagraphStyle("score", parent=st["big"], textColor=risk_color)
    cells = [[Paragraph("TRUST SCORE", st["label"]), Paragraph("RISK LEVEL", st["label"]), Paragraph("INPUT TYPE", st["label"])],
             [Paragraph(f"{report.trust_score} / 100", big_score), Paragraph(_t(doc.risk_level), big_risk),
              Paragraph(_t(doc.input_type).upper(), ParagraphStyle("it", parent=st["big"], fontSize=12))]]
    if report.verdict:  # claims: the fact-check status sits beside the message-level risk, never hidden by it
        tone = {"DEBUNKED_BY_SOURCE": RISK["HIGH"], "VERIFIED_BY_SOURCE": RISK["LOW"]}.get(report.verdict, RISK["MEDIUM"])
        cells[0].insert(2, Paragraph("FACT-CHECK STATUS", st["label"]))
        cells[1].insert(2, Paragraph(report.verdict.replace("_", " "),
                                     ParagraphStyle("fc", parent=st["big"], fontSize=11, leading=13, textColor=tone)))
    n = len(cells[0])
    summary = Table(cells, colWidths=[width / n] * n, rowHeights=[16, 34])
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                                 ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(summary)

    meta = [f"Report ID: {report_id}", f"Generated: {generated}", f"Analysis type: {_t(doc.input_type)}"]
    if report.analysis_intent:
        meta.append("Intent: " + {"synthetic_detection": "AI / Synthetic Detection",
                                  "artifact_authenticity": "Artifact Authenticity"}[report.analysis_intent])
    if report.verdict:
        meta.append("Fact-check status: " + report.verdict.replace("_", " "))
    if report.overall_assessment:
        meta.append("Assessment: " + _t(report.overall_assessment.label))
    if report.analysis_mode == "demo_cached":
        meta.append("Demo: Gemini output pre-recorded")
    story += [Spacer(1, 6), Paragraph(" &nbsp;|&nbsp; ".join(meta), st["muted"])]

    story += [Paragraph("EXECUTIVE SUMMARY", st["h"]), Paragraph(_t(doc.executive_summary, 2000), st["body"])]

    if report.media_assessment and report.artifact_assessment:
        rows = [[Paragraph("<b>Media authenticity</b><br/>" + _t(report.media_assessment.label) + "<br/>"
                           + f'<font size="8.5" color="#5B6678">{_t(report.media_assessment.summary)}</font>', st["body"]),
                 Paragraph("<b>Claim / artifact authenticity</b><br/>" + _t(report.artifact_assessment.label) + "<br/>"
                           + f'<font size="8.5" color="#5B6678">{_t(report.artifact_assessment.summary)}</font>', st["body"])]]
        axes = Table(rows, colWidths=[width / 2] * 2)
        axes.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                                  ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story += [Spacer(1, 8), axes]

    story.append(Paragraph(f"DETECTED SIGNALS ({len(doc.signals)})", st["h"]))
    if not doc.signals:
        story.append(Paragraph("No risk signals were detected by the rule checks or Gemini. This does not verify "
                               "the content as authentic.", st["body"]))
    for s in doc.signals:
        sev = SEV.get(s.severity, MUTED)
        left = Paragraph(f'<font face="Helvetica-Bold" size="8" color="{sev.hexval()[:2] and "#" + sev.hexval()[2:]}">{escape(s.severity)}</font>', st["body"])
        body = [Paragraph(_t(s.title, 120) + f' &nbsp; <font size="8" color="#5B6678">-{s.points} pts</font>', st["sig"]),
                Paragraph(_source_badges(s.source), st["muted"]), Spacer(1, 2), Paragraph(_t(s.explanation, 700), st["body"])]
        if s.evidence:
            body += [Spacer(1, 2), Paragraph("Evidence: " + _t(s.evidence, 320), st["mono"])]
        card = Table([[left, body]], colWidths=[20 * mm, width - 20 * mm])
        card.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBEFORE", (0, 0), (0, -1), 3, sev),
                                  ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (0, -1), 9)]))
        story += [KeepTogether(card), Spacer(1, 5)]

    if report.score_breakdown:
        applied = " - ".join(str(int(b.applied)) for b in report.score_breakdown)
        capped = "; ".join(f"{b.category.replace('_', ' ')}: {int(b.applied)} of {int(b.raw)}"
                           + (" (capped)" if b.raw > b.cap else "") for b in report.score_breakdown)
        story += [Spacer(1, 2), Paragraph(f"Score: 100 - {applied} = {report.trust_score}. Deductions by category: {_t(capped)}. "
                                          "The score is computed in code from the signals above, not chosen by a model.", st["muted"])]

    if doc.evidence_summary:
        story.append(Paragraph("EVIDENCE SUMMARY", st["h"]))
        story += [Paragraph("- " + _t(e, 500), st["body"]) for e in doc.evidence_summary[:14]]

    story.append(Paragraph("RECOMMENDED ACTION", st["h"]))
    rec = Table([[Paragraph(_t(doc.recommendation, 1500), st["rec"])]], colWidths=[width])
    rec.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("LINEBEFORE", (0, 0), (0, -1), 3, risk_color),
                             ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                             ("LEFTPADDING", (0, 0), (-1, -1), 11)]))
    story.append(rec)

    if doc.verification_steps:
        story.append(Paragraph("VERIFICATION STEPS", st["h"]))
        story += [Paragraph(f"{i}. " + _t(v, 500), st["body"]) for i, v in enumerate(doc.verification_steps[:8], 1)]

    if report.input_type != "image" and report.extracted.extracted_text.strip():
        story += [Paragraph("ANALYSED CONTENT (EXCERPT)", st["h"]),
                  Paragraph(_t(report.extracted.extracted_text, 420), st["mono"])]

    if doc.limitations:
        story.append(Paragraph("LIMITATIONS", st["h"]))
        story += [Paragraph("- " + _t(l, 500), st["body"]) for l in doc.limitations[:10]]

    story += [Spacer(1, 12), HRFlowable(width="100%", thickness=0.6, color=LINE), Spacer(1, 6),
              Paragraph("<b>DISCLAIMER</b> &nbsp; " + _t(doc.disclaimer), st["muted"]),
              Paragraph("Report wording: " + ("free OpenRouter model, facts pinned to the TrustLens analysis"
                                              if writer == "openrouter" else "generated directly from the TrustLens analysis")
                        + ". Signals marked RULE come from deterministic checks; signals marked GEMINI come from Gemini reasoning.",
                        st["muted"])]

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title="TrustLens AI - Digital Trust Report", author="TrustLens AI")
    draw = _footer(report_id, generated)
    pdf.build(story, onFirstPage=draw, onLaterPages=draw)
    return buf.getvalue(), report_id
