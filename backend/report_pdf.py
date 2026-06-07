# Student report PDF builder.
#
# Produces a single, self-contained PDF for one student combining the two
# governed outputs of the tracker: the formal Misk Diploma (manual award +
# mandatory-objective progress) and the Misk Skills Profile (the computed
# 31-dimension MSHPL developmental profile). Pure rendering: it takes an
# already-assembled `report` dict from the route layer and returns PDF bytes.
# It does no DB access and writes nothing to disk — the route streams the bytes
# straight to the authenticated teacher (school-controlled; no third-party host).
#
# The two outputs are kept visibly separate per misk_source_of_truth.md: the
# diploma award is a manual teacher selection (never computed), the skills
# profile is formula-driven and developmental (not a psychometric judgement).

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect

# MISK palette.
GREEN = colors.HexColor("#02664b")
GREEN_DEEP = colors.HexColor("#1a5c45")
GREEN_SOFT = colors.HexColor("#e8f1ed")
ACP_ACCENT = colors.HexColor("#02664b")
VAA_ACCENT = colors.HexColor("#0fb989")
BAR_TRACK = colors.HexColor("#eef2f0")
MUTED = colors.HexColor("#9aa6a1")
INK = colors.HexColor("#334039")
RULE = colors.HexColor("#d7e3de")

_STATUS_LABEL = {
    "approved": "Approved",
    "submitted": "Submitted",
    "under_review": "Under review",
    "pending_review": "Pending review",
    "rejected": "Rejected",
    "not_started": "Not started",
}
_STATUS_COLOR = {
    "approved": colors.HexColor("#1e8e5a"),
    "rejected": colors.HexColor("#c0392b"),
    "not_started": MUTED,
}
_STATUS_DEFAULT_COLOR = colors.HexColor("#b9770e")  # in-flight states


def _styles():
    base = getSampleStyleSheet()
    s = {}
    s["title"] = ParagraphStyle(
        "miskTitle", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=22, textColor=GREEN_DEEP, spaceAfter=2, leading=26,
    )
    s["subtitle"] = ParagraphStyle(
        "miskSubtitle", parent=base["Normal"], fontName="Helvetica",
        fontSize=10.5, textColor=MUTED, spaceAfter=2,
    )
    s["h2"] = ParagraphStyle(
        "miskH2", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, textColor=GREEN, spaceBefore=14, spaceAfter=8,
    )
    s["body"] = ParagraphStyle(
        "miskBody", parent=base["Normal"], fontName="Helvetica",
        fontSize=10, textColor=INK, leading=14,
    )
    s["small"] = ParagraphStyle(
        "miskSmall", parent=base["Normal"], fontName="Helvetica",
        fontSize=8.5, textColor=MUTED, leading=11,
    )
    s["award"] = ParagraphStyle(
        "miskAward", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=15, textColor=GREEN_DEEP, leading=18,
    )
    s["awardSub"] = ParagraphStyle(
        "miskAwardSub", parent=base["Normal"], fontName="Helvetica",
        fontSize=9.5, textColor=INK, leading=13,
    )
    s["cellL"] = ParagraphStyle(
        "cellL", parent=base["Normal"], fontName="Helvetica",
        fontSize=9.5, textColor=INK, leading=12,
    )
    s["cellMuted"] = ParagraphStyle(
        "cellMuted", parent=base["Normal"], fontName="Helvetica",
        fontSize=9.5, textColor=MUTED, leading=12,
    )
    return s


def _score_bar(score, accent):
    """A small horizontal bar (0–100) for use inside a table cell."""
    w, h = 88, 7
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, rx=3, ry=3, fillColor=BAR_TRACK, strokeColor=None))
    try:
        val = float(score)
    except (TypeError, ValueError):
        val = 0.0
    if val > 0:
        fw = max(2.0, w * min(100.0, val) / 100.0)
        d.add(Rect(0, 0, fw, h, rx=3, ry=3, fillColor=accent, strokeColor=None))
    return d


def _diploma_block(report, s):
    """The formal diploma award callout + the per-quadrant progress tables."""
    out = [Paragraph("Misk Diploma", s["h2"])]

    d = report.get("diploma", {}) or {}
    award_level = d.get("award_level")
    if award_level:
        headline = "Diploma awarded &mdash; %s" % award_level
        by = d.get("selected_by_name")
        when = (d.get("selected_at") or "")[:10]
        line = "Selected by %s%s." % (
            by or "a teacher",
            (" on %s" % when) if when else "",
        )
    elif d.get("eligible"):
        headline = "Eligible &mdash; awaiting final award"
        line = ("All mandatory objectives are approved. The final award "
                "(Pass / Merit / Distinction) is a manual teacher decision and "
                "has not yet been selected.")
    else:
        appr = d.get("approved_count", 0)
        act = d.get("active_count", 0)
        headline = "In progress"
        line = ("%d of %d mandatory objectives approved. The diploma award is "
                "selected manually once all are complete." % (appr, act))

    callout = Table(
        [[Paragraph(headline, s["award"])], [Paragraph(line, s["awardSub"])]],
        colWidths=[170 * mm],
    )
    callout.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN_SOFT),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
    ]))
    out.append(callout)
    out.append(Spacer(1, 6))

    quadrants = report.get("quadrants", []) or []
    if not quadrants:
        out.append(Paragraph("No mandatory objectives are configured.", s["small"]))
        return out

    for q in quadrants:
        color = colors.HexColor(q.get("color") or "#02664b")
        rows = [[Paragraph("<b>%s</b>" % q["name"], s["cellL"]), "", ""]]
        body_style = TableStyle([
            ("SPAN", (0, 0), (2, 0)),
            ("BACKGROUND", (0, 0), (2, 0), color),
            ("TEXTCOLOR", (0, 0), (2, 0), colors.white),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
        # Header cell needs white bold text; override the Paragraph colour.
        rows[0][0] = Paragraph(
            '<font color="#ffffff"><b>%s</b></font>' % q["name"], s["cellL"])

        for i, obj in enumerate(q.get("objectives", []), start=1):
            status = obj.get("status", "not_started")
            label = _STATUS_LABEL.get(status, status)
            scolor = _STATUS_COLOR.get(status, _STATUS_DEFAULT_COLOR)
            rows.append([
                Paragraph(obj.get("title", ""), s["cellL"]),
                Paragraph(obj.get("result_display", "&mdash;"), s["cellL"]),
                Paragraph('<font color="#%s"><b>%s</b></font>'
                          % (scolor.hexval()[2:], label), s["cellL"]),
            ])

        tbl = Table(rows, colWidths=[92 * mm, 40 * mm, 38 * mm])
        tbl.setStyle(body_style)
        out.append(KeepTogether([tbl, Spacer(1, 8)]))

    return out


def _grouped_skill_rows(groups, accent, s):
    """Build a flat row list (with group sub-headers) for a grouped skill table.

    groups: list of (group_name, [ {dimension, score, status} ]).
    Returns (rows, style_commands).
    """
    rows = []
    cmds = [
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
    ]
    r = 0
    for gname, leaves in groups:
        rows.append([
            Paragraph('<font color="#02664b"><b>%s</b></font>' % gname, s["cellL"]),
            "", "", "",
        ])
        cmds.append(("SPAN", (0, r), (3, r)))
        cmds.append(("BACKGROUND", (0, r), (3, r), GREEN_SOFT))
        r += 1
        for leaf in leaves:
            muted = leaf.get("status") == "no_evidence"
            score = leaf.get("score", 0)
            name_style = s["cellMuted"] if muted else s["cellL"]
            rows.append([
                Paragraph(leaf.get("dimension", ""), name_style),
                "",  # spacer column keeps the leaf indented under its group
                _score_bar(0 if muted else score, accent),
                Paragraph(
                    '<font color="#9aa6a1">&mdash;</font>' if muted
                    else '<font color="#02664b"><b>%s</b></font>' % score,
                    s["cellL"]),
            ])
            r += 1
    return rows, cmds


def _skills_block(report, s):
    skills = report.get("skills", {}) or {}
    out = [Paragraph("Misk Skills Profile", s["h2"])]

    summary = Table(
        [[
            Paragraph('<font color="#9aa6a1">Overall</font><br/>'
                      '<font color="#02664b" size="15"><b>%s</b></font>'
                      % skills.get("overall_average", 0), s["body"]),
            Paragraph('<font color="#9aa6a1">How I Think (ACP)</font><br/>'
                      '<font color="#02664b" size="15"><b>%s</b></font>'
                      % skills.get("acp_average", 0), s["body"]),
            Paragraph('<font color="#9aa6a1">Who I Am (VAA)</font><br/>'
                      '<font color="#02664b" size="15"><b>%s</b></font>'
                      % skills.get("vaa_average", 0), s["body"]),
        ]],
        colWidths=[56 * mm, 57 * mm, 57 * mm],
    )
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN_SOFT),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    out.append(summary)
    out.append(Spacer(1, 4))
    out.append(Paragraph(
        "A developmental evidence profile drawn from approved diploma evidence. "
        "It is not a qualification result, a ranking, or a fixed judgement of "
        "character.", s["small"]))
    out.append(Spacer(1, 8))

    # ACP — the 20 leaf characteristics grouped by their 5 groups.
    acp_leaves = skills.get("acp_leaves", []) or []
    out.append(Paragraph("How I Think &mdash; cognitive characteristics", s["body"]))
    out.append(Spacer(1, 4))
    acp_groups = _group_rows(acp_leaves)
    rows, cmds = _grouped_skill_rows(acp_groups, ACP_ACCENT, s)
    acp_tbl = Table(rows, colWidths=[70 * mm, 6 * mm, 70 * mm, 24 * mm])
    acp_tbl.setStyle(TableStyle(cmds))
    out.append(acp_tbl)
    out.append(Spacer(1, 12))

    # VAA — the 11 dimensions grouped by HPL cluster.
    vaa = [d for d in (skills.get("dimensions", []) or []) if d.get("group") == "VAA"]
    out.append(Paragraph("Who I Am &mdash; values, attitudes and attributes", s["body"]))
    out.append(Spacer(1, 4))
    vaa_groups = _group_rows(vaa)
    rows, cmds = _grouped_skill_rows(vaa_groups, VAA_ACCENT, s)
    vaa_tbl = Table(rows, colWidths=[70 * mm, 6 * mm, 70 * mm, 24 * mm])
    vaa_tbl.setStyle(TableStyle(cmds))
    out.append(vaa_tbl)
    return out


def _group_rows(rows):
    """Group dimension rows by their `category`, preserving first-seen order."""
    order = []
    by_cat = {}
    for row in rows:
        cat = row.get("category") or "Other"
        if cat not in by_cat:
            by_cat[cat] = []
            order.append(cat)
        by_cat[cat].append(row)
    return [(cat, by_cat[cat]) for cat in order]


def _make_footer(generated_at):
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, 16 * mm, 190 * mm, 16 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            20 * mm, 11 * mm,
            "Misk Schools Diploma Tracker  ·  Confidential student record  ·  "
            "Generated %s" % generated_at)
        canvas.drawRightString(190 * mm, 11 * mm, "Page %d" % doc.page)
        # Top accent rule.
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(2)
        canvas.line(20 * mm, 285 * mm, 190 * mm, 285 * mm)
        canvas.restoreState()
    return _footer


def build_student_report_pdf(report):
    """Render the assembled `report` dict to PDF bytes.

    Expected keys: student_name, generated_at, diploma{...}, quadrants[...],
    skills{...} (the compute_skills_profile payload).
    """
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=24 * mm, bottomMargin=22 * mm,
        title="Misk Diploma Report — %s" % report.get("student_name", ""),
        author="Misk Schools Diploma Tracker",
    )

    elements = [
        Paragraph("Misk Diploma &mdash; Student Report", s["title"]),
        Paragraph(report.get("student_name", ""), s["award"]),
        Spacer(1, 2),
        Paragraph("Generated %s" % report.get("generated_at", ""), s["subtitle"]),
        Spacer(1, 6),
    ]
    elements += _diploma_block(report, s)
    elements += _skills_block(report, s)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        "The Misk Diploma award is selected manually by teachers and is never "
        "computed by the system. The Misk Skills Profile is a formula-driven "
        "developmental profile intended for self-reflection and mentoring; it "
        "should not be used to rank or stream students.", s["small"]))

    footer = _make_footer(report.get("generated_at", ""))
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()