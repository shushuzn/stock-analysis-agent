"""PDF report export using reportlab."""

from __future__ import annotations

import io
from typing import Any


def generate_pdf(symbol: str, query: str, report_text: str, tool_results: list[dict[str, Any]]) -> bytes:
    """Generate a PDF report and return bytes."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise ImportError("reportlab not installed: pip install reportlab") from None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = {
        "title": ParagraphStyle("title", fontSize=18, leading=22, spaceAfter=10),
        "h2": ParagraphStyle("h2", fontSize=13, leading=16, spaceAfter=6, textColor=colors.HexColor("#0969da")),
        "body": ParagraphStyle("body", fontSize=10, leading=14, spaceAfter=6),
        "muted": ParagraphStyle("muted", fontSize=9, leading=12, textColor=colors.HexColor("#656d76")),
    }

    story = []
    story.append(Paragraph(f"📊 {symbol} — Stock Analysis Report", styles["title"]))
    story.append(Paragraph(f"Query: {query}", styles["muted"]))
    story.append(Spacer(1, 0.3*cm))

    for line in report_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.2*cm))
            continue
        if line.startswith("## "):
            story.append(Paragraph(line.replace("## ", ""), styles["h2"]))
        elif line.startswith("# "):
            story.append(Paragraph(f"<b>{line.replace('# ', '')}</b>", styles["title"]))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(f"<b>{line.strip('*')}</b>", styles["body"]))
        else:
            story.append(Paragraph(line, styles["body"]))

    # Tool results summary
    if tool_results:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("Tool Results", styles["h2"]))
        data = [["Tool", "Key Values"]]
        for r in tool_results:
            tool = r.get("tool", "?")
            data_kv = {k: v for k, v in r.get("data", {}).items() if not k.startswith("_")}
            vals = ", ".join(f"{k}={v}" for k, v in list(data_kv.items())[:4])
            data.append([tool, vals[:80]])
        t = Table(data, colWidths=[4*cm, 13*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0969da")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7de")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")]),
        ]))
        story.append(t)

    doc.build(story)
    return buffer.getvalue()
