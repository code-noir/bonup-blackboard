# backend/api/sol/pdf_views.py
#
# PDF export endpoints for the Sol domain.
#
# Manager export: full Sol record — members, all payouts, contribution grid, tips.
# Member export: personal record — own contract, contribution history, payout status.

import io
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from rest_framework.views import APIView

from backend.sol.models import Sol, SolMember, SolContribution, SolPayout

from .views import _is_manager, _member_of_sol


# ---------------------------------------------------------------------------
# Shared PDF primitives
# ---------------------------------------------------------------------------

_BRAND_TEAL = colors.HexColor("#00796B")
_BRAND_LIGHT = colors.HexColor("#E0F2F1")
_GREY_TEXT = colors.HexColor("#555555")
_BLACK = colors.black
_WHITE = colors.white


def _base_doc(buf, title):
    return SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title=title,
    )


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(
        "BrandTitle",
        parent=ss["Title"],
        textColor=_BRAND_TEAL,
        fontSize=20,
        spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        "SectionHeader",
        parent=ss["Heading2"],
        textColor=_BRAND_TEAL,
        fontSize=12,
        spaceBefore=14,
        spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        "SubLabel",
        parent=ss["Normal"],
        textColor=_GREY_TEXT,
        fontSize=8,
        spaceAfter=1,
    ))
    ss.add(ParagraphStyle(
        "Body",
        parent=ss["Normal"],
        fontSize=9,
        leading=13,
        spaceAfter=3,
    ))
    ss.add(ParagraphStyle(
        "SmallMono",
        parent=ss["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        spaceAfter=2,
    ))
    ss.add(ParagraphStyle(
        "Disclaimer",
        parent=ss["Normal"],
        textColor=_GREY_TEXT,
        fontSize=7.5,
        leading=11,
        spaceAfter=2,
    ))
    return ss


def _header_block(story, ss, title, subtitle=None, generated_at=None):
    story.append(Paragraph("bonUP", ParagraphStyle(
        "BrandMark", parent=ss["Normal"], textColor=_BRAND_TEAL,
        fontSize=10, fontName="Helvetica-Bold",
    )))
    story.append(Paragraph(title, ss["BrandTitle"]))
    if subtitle:
        story.append(Paragraph(subtitle, ss["Body"]))
    ts = generated_at or timezone.now()
    story.append(Paragraph(
        f"Generated: {ts.strftime('%B %d, %Y at %H:%M UTC')}",
        ss["SubLabel"],
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_BRAND_TEAL, spaceAfter=8))


def _kv_table(pairs, col_widths=(2.2 * inch, 4.5 * inch)):
    """Two-column key/value info block."""
    data = [[k, v] for k, v in pairs]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), _GREY_TEXT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _data_table(headers, rows, col_widths=None):
    """Standard data grid with teal header row."""
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    n = len(rows)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND_TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, _BRAND_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]
    t.setStyle(TableStyle(style))
    return t


def _disclaimer(ss):
    return Paragraph(
        "bonUP is a record-keeping platform only. bonUP does not process, hold, "
        "transmit, or guarantee any payments. All financial transactions occur "
        "directly between members and the manager.",
        ss["Disclaimer"],
    )


def _pdf_response(buf, filename):
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Manager Export
# ---------------------------------------------------------------------------

class SolManagerExportView(APIView):
    """GET /api/sol/<sol_id>/export/pdf/"""

    def get(self, request, sol_id):
        sol = get_object_or_404(Sol, pk=sol_id)
        if not _is_manager(request.user, sol):
            from rest_framework import status
            from rest_framework.response import Response
            return Response({"error": "Not authorised."}, status=status.HTTP_403_FORBIDDEN)

        buf = io.BytesIO()
        doc = _base_doc(buf, f"Sol Record — {sol.sol_id}")
        ss = _styles()
        story = []

        # ── Header ──────────────────────────────────────────────────────────
        _header_block(
            story, ss,
            title=f"Sol Group Record",
            subtitle=f"{sol.name}  ·  {sol.sol_id}",
        )

        # ── Group Summary ────────────────────────────────────────────────────
        story.append(Paragraph("Group Summary", ss["SectionHeader"]))
        freq_map = dict(Sol.FREQUENCY_CHOICES)
        status_map = dict(Sol.STATUS_CHOICES)
        story.append(_kv_table([
            ("Sol ID", sol.sol_id),
            ("Name", sol.name),
            ("Status", status_map.get(sol.status, sol.status)),
            ("Frequency", freq_map.get(sol.frequency, sol.frequency)),
            ("Contribution", f"{sol.contribution_amount} {sol.currency} / period"),
            ("Tip Expectation", f"{sol.tip_expectation} {sol.currency}"),
            ("Start Date", str(sol.start_date)),
            ("Expected End", str(sol.expected_end_date) if sol.expected_end_date else "—"),
            ("Type", sol.sol_type.capitalize()),
            ("Primary Manager", str(sol.primary_manager)),
            ("Co-Manager", str(sol.co_manager) if sol.co_manager else "—"),
            ("Total Active Members", str(sol.members.filter(is_active=True).count())),
        ]))

        if sol.description:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<i>{sol.description}</i>", ss["Body"]))

        # ── Members ──────────────────────────────────────────────────────────
        story.append(Paragraph("Members", ss["SectionHeader"]))
        members = list(sol.members.filter(is_active=True).order_by("hand_number"))
        if members:
            rows = [
                [
                    str(m.hand_number),
                    m.name,
                    m.email,
                    m.phone,
                    "✓" if m.is_bonup_member else "—",
                    "✓" if m.has_received else "—",
                ]
                for m in members
            ]
            story.append(_data_table(
                ["Hand #", "Name", "Email", "Phone", "bonUP", "Received"],
                rows,
                col_widths=[0.55*inch, 1.5*inch, 1.8*inch, 1.1*inch, 0.55*inch, 0.65*inch],
            ))
        else:
            story.append(Paragraph("No active members.", ss["Body"]))

        # ── Payouts ──────────────────────────────────────────────────────────
        story.append(Paragraph("Payout Schedule", ss["SectionHeader"]))
        payouts = list(sol.payouts.order_by("cycle_number", "hand_number"))
        if payouts:
            rows = [
                [
                    p.payout_id,
                    str(p.cycle_number),
                    str(p.hand_number),
                    p.recipient.name,
                    str(p.expected_date),
                    str(p.paid_date) if p.paid_date else "—",
                    f"{p.expected_amount} {sol.currency}",
                    p.status.capitalize(),
                    "✓" if p.was_rearranged else "—",
                ]
                for p in payouts
            ]
            story.append(_data_table(
                ["Payout ID", "Cycle", "Hand", "Recipient", "Expected", "Paid", "Amount", "Status", "Rearranged"],
                rows,
                col_widths=[0.9*inch, 0.45*inch, 0.45*inch, 1.1*inch,
                            0.75*inch, 0.75*inch, 0.9*inch, 0.6*inch, 0.75*inch],
            ))
        else:
            story.append(Paragraph("No payouts created yet.", ss["Body"]))

        # ── Contribution Grid ────────────────────────────────────────────────
        story.append(Paragraph("Contribution Tracker", ss["SectionHeader"]))
        contributions = (
            SolContribution.objects
            .filter(sol=sol)
            .select_related("member", "payout")
            .order_by("payout__cycle_number", "payout__hand_number", "member__hand_number")
        )
        if contributions.exists():
            rows = [
                [
                    c.payout.payout_id,
                    str(c.payout.hand_number),
                    c.member.name,
                    f"{c.amount} {sol.currency}",
                    c.status.capitalize(),
                    str(c.due_date),
                    str(c.paid_date) if c.paid_date else "—",
                ]
                for c in contributions
            ]
            story.append(_data_table(
                ["Payout", "Hand", "Member", "Amount", "Status", "Due", "Paid"],
                rows,
                col_widths=[0.9*inch, 0.45*inch, 1.4*inch, 0.95*inch,
                            0.7*inch, 0.75*inch, 0.75*inch],
            ))
        else:
            story.append(Paragraph("No contributions recorded yet.", ss["Body"]))

        # ── Fund Summary ─────────────────────────────────────────────────────
        story.append(Paragraph("Fund Summary", ss["SectionHeader"]))
        total_expected = sum(c.amount for c in contributions)
        total_paid = sum(c.amount for c in contributions if c.status == "paid")
        total_missed = sum(c.amount for c in contributions if c.status == "missed")
        total_outstanding = total_expected - total_paid
        payouts_paid = sol.payouts.filter(status="paid").count()
        total_payouts = sol.payouts.count()

        story.append(_kv_table([
            ("Total Expected Contributions", f"{total_expected} {sol.currency}"),
            ("Total Collected", f"{total_paid} {sol.currency}"),
            ("Total Outstanding", f"{total_outstanding} {sol.currency}"),
            ("Total Missed", f"{total_missed} {sol.currency}"),
            ("Payouts Completed", f"{payouts_paid} / {total_payouts}"),
        ]))

        # ── Tips ─────────────────────────────────────────────────────────────
        tips = list(sol.tips.select_related("from_member").order_by("-created_at"))
        if tips:
            story.append(Paragraph("Tips Received", ss["SectionHeader"]))
            tip_rows = [
                [
                    t.from_member.name,
                    f"{t.amount} {t.currency}",
                    t.note or "—",
                    t.created_at.strftime("%Y-%m-%d"),
                ]
                for t in tips
            ]
            story.append(_data_table(
                ["From", "Amount", "Note", "Date"],
                tip_rows,
                col_widths=[1.5*inch, 0.9*inch, 3.0*inch, 0.8*inch],
            ))

        # ── Notes ────────────────────────────────────────────────────────────
        notes = list(sol.notes.order_by("-created_at"))
        if notes:
            story.append(Paragraph("Manager Notes", ss["SectionHeader"]))
            for note in notes:
                story.append(Paragraph(
                    f"<b>{note.created_at.strftime('%Y-%m-%d')}</b>  {note.text}",
                    ss["Body"],
                ))

        # ── Footer ───────────────────────────────────────────────────────────
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=0.5, color=_GREY_TEXT))
        story.append(Spacer(1, 4))
        story.append(_disclaimer(ss))

        doc.build(story)
        filename = f"sol-{sol.sol_id}-record.pdf"
        return _pdf_response(buf, filename)


# ---------------------------------------------------------------------------
# Member Export
# ---------------------------------------------------------------------------

class SolMemberExportView(APIView):
    """GET /api/sol/memberships/<sol_id>/export/pdf/"""

    def get(self, request, sol_id):
        member, sol, err = _member_of_sol(request.user, sol_id)
        if err:
            return err

        buf = io.BytesIO()
        doc = _base_doc(buf, f"Sol Personal Record — {sol.sol_id}")
        ss = _styles()
        story = []

        # ── Header ──────────────────────────────────────────────────────────
        _header_block(
            story, ss,
            title="Sol Personal Record",
            subtitle=f"{sol.name}  ·  {sol.sol_id}  ·  Hand #{member.hand_number}",
        )

        # ── Membership Summary ───────────────────────────────────────────────
        story.append(Paragraph("My Membership", ss["SectionHeader"]))
        freq_map = dict(Sol.FREQUENCY_CHOICES)
        story.append(_kv_table([
            ("Member Name", member.name),
            ("Hand Number", str(member.hand_number)),
            ("Sol Group", sol.name),
            ("Sol ID", sol.sol_id),
            ("Frequency", freq_map.get(sol.frequency, sol.frequency)),
            ("My Contribution", f"{sol.contribution_amount} {sol.currency} / period"),
            ("Tip Expectation", f"{sol.tip_expectation} {sol.currency}"),
            ("Received Payout", "Yes" if member.has_received else "Not yet"),
            ("bonUP Member", "Yes" if member.is_bonup_member else "No"),
            ("Joined", member.joined_at.strftime("%B %d, %Y")),
        ]))

        # ── Contract ─────────────────────────────────────────────────────────
        contract = getattr(member, "contract", None)
        if contract:
            story.append(Paragraph("My Agreement", ss["SectionHeader"]))
            story.append(_kv_table([
                ("Agreed Contribution", f"{contract.agreed_contribution_amount} {sol.currency}"),
                ("Agreed Hand Number", str(contract.agreed_hand_number)),
                ("Agreed Tip", f"{contract.agreed_tip_amount} {sol.currency}"),
                ("Signed", "Yes" if contract.signed_by_member else "Pending"),
                ("Signed At", contract.signed_at.strftime("%Y-%m-%d %H:%M UTC") if contract.signed_at else "—"),
                ("Contract Date", contract.created_at.strftime("%B %d, %Y")),
            ]))
            story.append(Spacer(1, 6))
            story.append(Paragraph("Full Agreement Text:", ss["SubLabel"]))
            # Split contract text into paragraphs to preserve formatting
            for line in contract.contract_text.split("\n"):
                stripped = line.strip()
                if stripped:
                    story.append(Paragraph(stripped, ss["SmallMono"]))
                else:
                    story.append(Spacer(1, 3))

        # ── Contribution History ─────────────────────────────────────────────
        story.append(Paragraph("My Contribution History", ss["SectionHeader"]))
        contributions = (
            SolContribution.objects
            .filter(member=member)
            .select_related("payout")
            .order_by("-due_date")
        )
        if contributions.exists():
            rows = [
                [
                    c.payout.payout_id,
                    str(c.payout.hand_number),
                    f"{c.amount} {sol.currency}",
                    c.status.capitalize(),
                    str(c.due_date),
                    str(c.paid_date) if c.paid_date else "—",
                    c.notes or "—",
                ]
                for c in contributions
            ]
            story.append(_data_table(
                ["Payout", "Hand", "Amount", "Status", "Due", "Paid", "Notes"],
                rows,
                col_widths=[0.9*inch, 0.5*inch, 0.9*inch, 0.7*inch,
                            0.75*inch, 0.75*inch, 1.75*inch],
            ))
            total_paid = sum(c.amount for c in contributions if c.status == "paid")
            total_pending = sum(c.amount for c in contributions if c.status in ("pending", "late"))
            story.append(Spacer(1, 6))
            story.append(_kv_table([
                ("Total Paid", f"{total_paid} {sol.currency}"),
                ("Total Pending / Late", f"{total_pending} {sol.currency}"),
            ]))
        else:
            story.append(Paragraph("No contributions recorded yet.", ss["Body"]))

        # ── My Payouts ───────────────────────────────────────────────────────
        my_payouts = SolPayout.objects.filter(recipient=member).order_by("cycle_number")
        if my_payouts.exists():
            story.append(Paragraph("My Payout Records", ss["SectionHeader"]))
            rows = [
                [
                    p.payout_id,
                    str(p.cycle_number),
                    str(p.expected_date),
                    str(p.paid_date) if p.paid_date else "—",
                    f"{p.expected_amount} {sol.currency}",
                    f"{p.actual_amount} {sol.currency}" if p.actual_amount else "—",
                    p.status.capitalize(),
                ]
                for p in my_payouts
            ]
            story.append(_data_table(
                ["Payout ID", "Cycle", "Expected Date", "Paid Date",
                 "Expected", "Actual", "Status"],
                rows,
                col_widths=[0.9*inch, 0.5*inch, 0.85*inch, 0.85*inch,
                            1.0*inch, 1.0*inch, 0.7*inch],
            ))

        # ── Upcoming payout for this member ─────────────────────────────────
        upcoming = SolPayout.objects.filter(recipient=member, status="upcoming").order_by("expected_date").first()
        if upcoming:
            story.append(Spacer(1, 8))
            story.append(Paragraph(
                f"<b>Your next payout:</b>  {upcoming.payout_id}  ·  "
                f"Expected {upcoming.expected_date}  ·  "
                f"{upcoming.expected_amount} {sol.currency}",
                ss["Body"],
            ))

        # ── Footer ───────────────────────────────────────────────────────────
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=0.5, color=_GREY_TEXT))
        story.append(Spacer(1, 4))
        story.append(_disclaimer(ss))

        doc.build(story)
        filename = f"sol-{sol.sol_id}-hand{member.hand_number}-record.pdf"
        return _pdf_response(buf, filename)
