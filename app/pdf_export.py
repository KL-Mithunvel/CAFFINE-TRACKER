"""Generates a structured PDF report of all tracked data: summary stats,
per-drink breakdown, and the full entry log. No Flask imports — takes an
open sqlite3.Connection and returns PDF bytes, so it's testable standalone.
"""
import io
import sqlite3

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import models, stats


def _entries_table_data(conn: sqlite3.Connection) -> list[list[str]]:
    header = ["Date/Time", "Drink", "Volume (ml)", "Caffeine (mg)", "Notes"]
    rows = [header]
    for e in models.list_entries(conn):
        caffeine = f"{e['caffeine_mg']:.1f}" if e["caffeine_mg"] is not None else "pending"
        rows.append([e["consumed_at"], e["drink_name"], f"{e['volume_ml']:g}", caffeine, e["notes"] or ""])
    return rows


def _breakdown_table_data(breakdown: list[dict]) -> list[list[str]]:
    header = ["Drink", "Total (mg)", "Entries"]
    rows = [header]
    for b in breakdown:
        rows.append([b["drink_name"], f"{b['total_mg']:.1f}", str(b["entry_count"])])
    return rows


def _styled_table(data: list[list[str]]) -> Table:
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3a3a3a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def build_report_pdf(conn: sqlite3.Connection) -> bytes:
    """Builds the full report and returns it as PDF bytes."""
    dashboard = stats.get_dashboard_stats(conn, range_key="all")
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
    )

    story = [
        Paragraph("Caffeine Tracker Report", styles["Title"]),
        Paragraph(f"Generated {models.now_local()}", styles["Normal"]),
        Spacer(1, 10 * mm),
        Paragraph("Summary", styles["Heading2"]),
    ]

    avg = dashboard["averages"]
    streaks = dashboard["streaks"]
    days_over = dashboard["days_above_limit"]
    summary_lines = [
        f"Daily limit: {dashboard['daily_limit_mg']:.0f} mg",
        f"Today's intake: {dashboard['today_vs_limit']['today_mg']:.1f} mg "
        f"({dashboard['today_vs_limit']['pct_of_limit']:.0f}% of limit)",
        f"Days tracked: {avg['days_tracked']} — drinking days: {avg['drinking_days']}",
        f"Average per day: {avg['avg_per_day']:.1f} mg — average per drinking day: {avg['avg_per_drinking_day']:.1f} mg",
        f"Days over limit: {days_over['days_over']} of {days_over['days_tracked']} ({days_over['pct_over']:.0f}%)",
        f"Current under-limit streak: {streaks['current_streak']} days — longest: {streaks['longest_streak']} days",
        f"Unresolved (pending lookup) entries: {dashboard['unresolved_entry_count']}",
    ]
    if dashboard["max_intake_day"]:
        summary_lines.append(
            f"Highest single day: {dashboard['max_intake_day']['day']} "
            f"({dashboard['max_intake_day']['total_mg']:.1f} mg)"
        )
    for line in summary_lines:
        story.append(Paragraph(line, styles["Normal"]))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Breakdown by Drink", styles["Heading2"]))
    breakdown = dashboard["per_drink_breakdown"]
    if breakdown:
        story.append(_styled_table(_breakdown_table_data(breakdown)))
    else:
        story.append(Paragraph("No resolved entries yet.", styles["Normal"]))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Entry Log", styles["Heading2"]))
    entries_data = _entries_table_data(conn)
    if len(entries_data) > 1:
        story.append(_styled_table(entries_data))
    else:
        story.append(Paragraph("No entries logged yet.", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
