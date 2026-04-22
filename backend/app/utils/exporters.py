import io
import logging
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


def export_csv(data: list[dict], filename: str) -> bytes:
    """Convert a list of dicts to CSV bytes."""
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8")
    logger.info("Exported CSV: %s (%d rows)", filename, len(data))
    return buffer.getvalue()


def export_pdf(data: dict, filename: str) -> bytes:
    """Generate a professional PDF sentiment report.

    Expected *data* keys:
        title, company_name, ticker, report_date,
        sentiment_summary (dict), correlations (list[dict]),
        social_sentiment (dict), articles (list[dict])
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=20,
        textColor=colors.HexColor("#1a237e"),
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#283593"),
    )
    body_style = styles["BodyText"]
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["BodyText"],
        fontSize=8,
        textColor=colors.grey,
        spaceBefore=24,
    )

    elements: list = []

    # --- Title ---
    elements.append(Paragraph(data.get("title", "Financial Sentiment Report"), title_style))
    elements.append(Spacer(1, 6))

    # --- Company info ---
    company = data.get("company_name", "N/A")
    ticker = data.get("ticker", "N/A")
    report_date = data.get("report_date", datetime.utcnow().strftime("%Y-%m-%d"))
    elements.append(Paragraph(f"<b>Company:</b> {company} ({ticker})", body_style))
    elements.append(Paragraph(f"<b>Report Date:</b> {report_date}", body_style))
    elements.append(Spacer(1, 12))

    # --- Sentiment summary ---
    elements.append(Paragraph("Sentiment Summary", heading_style))
    sentiment = data.get("sentiment_summary", {})
    if sentiment:
        sent_data = [
            ["Metric", "Value"],
            ["Overall Label", str(sentiment.get("label", "N/A"))],
            ["Positive Score", f"{sentiment.get('positive', 0):.4f}"],
            ["Negative Score", f"{sentiment.get('negative', 0):.4f}"],
            ["Neutral Score", f"{sentiment.get('neutral', 0):.4f}"],
            ["Confidence", f"{sentiment.get('confidence', 0):.4f}"],
            ["Articles Analyzed", str(sentiment.get("article_count", 0))],
        ]
        t = Table(sent_data, colWidths=[2.5 * inch, 3 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(t)
    else:
        elements.append(Paragraph("No sentiment data available.", body_style))
    elements.append(Spacer(1, 12))

    # --- Sentiment chart placeholder ---
    elements.append(Paragraph("Sentiment Distribution Chart", heading_style))
    elements.append(
        Paragraph(
            "<i>[Chart placeholder — integrate matplotlib/plotly rendering for production]</i>",
            body_style,
        )
    )
    elements.append(Spacer(1, 12))

    # --- Correlation table ---
    elements.append(Paragraph("Sentiment–Price Correlations", heading_style))
    correlations = data.get("correlations", [])
    if correlations:
        corr_header = ["Type", "Value", "P-Value", "Lag (days)", "Samples"]
        corr_rows = [corr_header] + [
            [
                str(c.get("correlation_type", "")),
                f"{c.get('correlation_value', 0):.4f}",
                f"{c.get('p_value', 0):.6f}",
                str(c.get("time_lag", "")),
                str(c.get("sample_size", "")),
            ]
            for c in correlations
        ]
        ct = Table(corr_rows, colWidths=[1.5 * inch, 1 * inch, 1.2 * inch, 1 * inch, 1 * inch])
        ct.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(ct)
    else:
        elements.append(Paragraph("No correlation data available.", body_style))
    elements.append(Spacer(1, 12))

    # --- Social sentiment ---
    elements.append(Paragraph("Social Sentiment (X / Twitter)", heading_style))
    social = data.get("social_sentiment", {})
    if social:
        elements.append(Paragraph(f"<b>Buzz Score:</b> {social.get('buzz_score', 'N/A')}", body_style))
        elements.append(Paragraph(f"<b>Bullish Ratio:</b> {social.get('bullish_ratio', 'N/A')}", body_style))
        elements.append(Paragraph(f"<b>Bearish Ratio:</b> {social.get('bearish_ratio', 'N/A')}", body_style))
        elements.append(Paragraph(f"<b>Post Volume:</b> {social.get('post_volume', 'N/A')}", body_style))
        elements.append(Paragraph(f"<b>Trend:</b> {social.get('sentiment_trend', 'N/A')}", body_style))
    else:
        elements.append(Paragraph("No social sentiment data available.", body_style))
    elements.append(Spacer(1, 12))

    # --- Disclaimers ---
    elements.append(Paragraph("Disclaimers", heading_style))
    elements.append(
        Paragraph(
            "This report is generated automatically by the Financial Sentiment Analyzer. "
            "It is intended for informational and educational purposes only and does not "
            "constitute financial advice, investment recommendations, or an offer to buy or "
            "sell any securities. Sentiment scores are derived from NLP models and may contain "
            "inaccuracies. Always consult a qualified financial advisor before making investment "
            "decisions. Past performance is not indicative of future results.",
            disclaimer_style,
        )
    )

    doc.build(elements)
    logger.info("Exported PDF: %s", filename)
    return buffer.getvalue()
