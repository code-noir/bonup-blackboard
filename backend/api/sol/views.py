# backend/api/sol/views.py
#
# Sol (sou-sou / tontine / susu) rotating savings group API.

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.billing.gates import can_create_sol, can_join_sol, auto_upgrade_to_sol_member, auto_downgrade_from_sol_member
from backend.sol.models import (
    Sol, SolMember, SolContract, SolPayout, SolContribution, SolTip, SolNote,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_manager(user, sol):
    return sol.primary_manager_id == user.pk or sol.co_manager_id == user.pk


def _manager_sol_or_404(user, sol_id):
    sol = get_object_or_404(Sol, pk=sol_id)
    if not _is_manager(user, sol):
        return None, Response({"error": "Not authorised."}, status=status.HTTP_403_FORBIDDEN)
    return sol, None


def _member_of_sol(user, sol_id):
    """Return (SolMember, None) if user is an active member of this sol, else (None, Response)."""
    sol = get_object_or_404(Sol, pk=sol_id)
    try:
        member = SolMember.objects.get(sol=sol, bonup_user=user, is_active=True)
        return member, sol, None
    except SolMember.DoesNotExist:
        return None, sol, Response({"error": "Not a member of this Sol."}, status=status.HTTP_403_FORBIDDEN)


def _serialize_sol(sol, include_members=False, include_payouts=False):
    d = {
        "id": str(sol.id),
        "sol_id": sol.sol_id,
        "name": sol.name,
        "description": sol.description,
        "status": sol.status,
        "frequency": sol.frequency,
        "contribution_amount": str(sol.contribution_amount),
        "currency": sol.currency,
        "tip_expectation": str(sol.tip_expectation),
        "is_private": sol.is_private,
        "sol_type": sol.sol_type,
        "start_date": str(sol.start_date),
        "expected_end_date": str(sol.expected_end_date) if sol.expected_end_date else None,
        "primary_manager_id": sol.primary_manager_id,
        "co_manager_id": sol.co_manager_id,
        "active_member_count": sol.active_member_count(),
        "created_at": sol.created_at,
        "updated_at": sol.updated_at,
    }
    if include_members:
        d["members"] = [_serialize_member(m) for m in sol.members.filter(is_active=True).order_by("hand_number")]
    if include_payouts:
        d["payouts"] = [_serialize_payout(p) for p in sol.payouts.all()]
    return d


def _serialize_member(m):
    return {
        "id": str(m.id),
        "name": m.name,
        "email": m.email,
        "phone": m.phone,
        "employer": m.employer,
        "emergency_contact_name": m.emergency_contact_name,
        "emergency_contact_phone": m.emergency_contact_phone,
        "is_bonup_member": m.is_bonup_member,
        "hand_number": m.hand_number,
        "has_received": m.has_received,
        "is_manager_participant": m.is_manager_participant,
        "is_active": m.is_active,
        "joined_at": m.joined_at,
        "notes": m.notes,
    }


def _serialize_payout(p):
    return {
        "id": str(p.id),
        "payout_id": p.payout_id,
        "cycle_number": p.cycle_number,
        "hand_number": p.hand_number,
        "recipient_id": str(p.recipient_id),
        "recipient_name": p.recipient.name,
        "expected_date": str(p.expected_date),
        "paid_date": str(p.paid_date) if p.paid_date else None,
        "expected_amount": str(p.expected_amount),
        "actual_amount": str(p.actual_amount) if p.actual_amount else None,
        "status": p.status,
        "was_rearranged": p.was_rearranged,
        "rearranged_reason": p.rearranged_reason,
        "created_at": p.created_at,
    }


def _serialize_contribution(c):
    return {
        "id": str(c.id),
        "member_id": str(c.member_id),
        "member_name": c.member.name,
        "amount": str(c.amount),
        "status": c.status,
        "due_date": str(c.due_date),
        "paid_date": str(c.paid_date) if c.paid_date else None,
        "notes": c.notes,
    }


def _generate_contract_text(sol, member, total_members):
    payout_amount = sol.contribution_amount * (total_members - 1)
    freq_display = dict(Sol.FREQUENCY_CHOICES).get(sol.frequency, sol.frequency)
    return f"""SOL PARTICIPATION AGREEMENT
==========================================

Sol Group: {sol.name}
Sol ID: {sol.sol_id}
Member Name: {member.name}
Hand Number: {member.hand_number}
Date Generated: {timezone.now().strftime('%Y-%m-%d')}

------------------------------------------
CONTRIBUTION TERMS
------------------------------------------

Contribution Amount: {sol.contribution_amount} {sol.currency} per period
Payment Frequency: {freq_display}
Group Size: {total_members} members

You are required to pay your contribution every period EXCEPT the period in \
which you receive your hand (payout).

------------------------------------------
PAYOUT TERMS
------------------------------------------

Expected Payout Amount: {payout_amount} {sol.currency}
(Calculated as: {sol.contribution_amount} × {total_members - 1} contributing members)
Expected Tip to Manager: {sol.tip_expectation} {sol.currency}

Your payout will be disbursed on the date designated for Hand #{member.hand_number} \
in the payout schedule maintained by the manager.

------------------------------------------
MEMBER OBLIGATIONS
------------------------------------------

1. Pay your contribution in full and on time every period, except your own hand period.
2. Contact your manager immediately if you anticipate difficulty making a payment.
3. Any missed payment remains your personal obligation and must be resolved \
directly with the manager.
4. Repeated missed payments may result in removal from the group.

------------------------------------------
MANAGER OBLIGATIONS
------------------------------------------

1. Collect all contributions from members each period.
2. Deliver the full payout to the designated recipient each period.
3. Cover any member defaults to ensure the recipient receives the full payout amount.
4. Maintain accurate records of all contributions, payouts, and tips.
5. Notify members of schedule changes in advance when possible.

------------------------------------------
DEFAULT POLICY
------------------------------------------

If you miss a contribution payment, the full amount remains owed. This is a \
private financial arrangement between you and the manager. Defaults must be \
resolved directly — bonUP does not mediate, collect, or guarantee any payments.

------------------------------------------
PLATFORM DISCLAIMER
------------------------------------------

bonUP is a record-keeping and agreement platform only. bonUP does not process, \
hold, transmit, or guarantee any payments. All financial transactions occur \
directly between members and the manager outside of this platform. This document \
serves solely as a record of the terms agreed upon between the parties.

------------------------------------------
SIGNATURES
------------------------------------------

Member: {member.name}
Agreed to Terms: [ Pending Member Signature ]

Manager: {sol.primary_manager}
Sol Group: {sol.name} ({sol.sol_id})

==========================================
"""


# ---------------------------------------------------------------------------
# Manager: Sol CRUD
# ---------------------------------------------------------------------------

class SolListCreateView(APIView):
    """GET/POST /api/sol/"""

    def get(self, request):
        sols = Sol.objects.filter(
            Q(primary_manager=request.user) | Q(co_manager=request.user)
        ).order_by("-created_at")
        return Response({"results": [_serialize_sol(s) for s in sols]})

    def post(self, request):
        allowed, msg = can_create_sol(request.user)
        if not allowed:
            return Response({"error": msg}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        required = ["name", "frequency", "contribution_amount", "start_date"]
        for field in required:
            if not data.get(field):
                return Response({"error": f"{field} is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            contribution_amount = Decimal(str(data["contribution_amount"]))
            tip_expectation = Decimal(str(data.get("tip_expectation", "0")))
        except Exception:
            return Response({"error": "Invalid decimal value."}, status=status.HTTP_400_BAD_REQUEST)

        if data["frequency"] not in dict(Sol.FREQUENCY_CHOICES):
            return Response({"error": "Invalid frequency."}, status=status.HTTP_400_BAD_REQUEST)

        sol = Sol.objects.create(
            name=data["name"],
            description=data.get("description", ""),
            primary_manager=request.user,
            frequency=data["frequency"],
            contribution_amount=contribution_amount,
            currency=data.get("currency", "USD"),
            tip_expectation=tip_expectation,
            is_private=data.get("is_private", True),
            sol_type=data.get("sol_type", "single"),
            start_date=data["start_date"],
            expected_end_date=data.get("expected_end_date") or None,
        )
        return Response(_serialize_sol(sol), status=status.HTTP_201_CREATED)


class SolDetailView(APIView):
    """GET/PATCH /api/sol/<sol_id>/"""

    def get(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        return Response(_serialize_sol(sol, include_members=True, include_payouts=True))

    def patch(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err

        data = request.data
        updatable = ["name", "description", "status", "is_private", "expected_end_date", "tip_expectation", "co_manager"]
        for field in updatable:
            if field in data:
                if field == "co_manager":
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    try:
                        sol.co_manager = User.objects.get(pk=data["co_manager"]) if data["co_manager"] else None
                    except User.DoesNotExist:
                        return Response({"error": "co_manager user not found."}, status=status.HTTP_400_BAD_REQUEST)
                elif field == "tip_expectation":
                    sol.tip_expectation = Decimal(str(data[field]))
                else:
                    setattr(sol, field, data[field])
        sol.save()
        return Response(_serialize_sol(sol))


# ---------------------------------------------------------------------------
# Manager: Members
# ---------------------------------------------------------------------------

class SolMemberListCreateView(APIView):
    """POST /api/sol/<sol_id>/members/"""

    def post(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err

        data = request.data
        for field in ["name", "email", "phone", "hand_number"]:
            if not data.get(field):
                return Response({"error": f"{field} is required."}, status=status.HTTP_400_BAD_REQUEST)

        hand_number = int(data["hand_number"])
        if SolMember.objects.filter(sol=sol, hand_number=hand_number, is_active=True).exists():
            return Response({"error": f"Hand number {hand_number} is already taken."}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve bonUP user if email matches a registered user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        bonup_user = None
        is_bonup_member = False
        try:
            bonup_user = User.objects.get(email=data["email"])
            # Check Sol join gate
            allowed, msg = can_join_sol(bonup_user)
            if not allowed:
                return Response({"error": f"Cannot link bonUP account: {msg}"}, status=status.HTTP_403_FORBIDDEN)
            is_bonup_member = True
            auto_upgrade_to_sol_member(bonup_user)
        except User.DoesNotExist:
            pass

        is_manager_participant = (bonup_user == request.user) if bonup_user else False

        with transaction.atomic():
            member = SolMember.objects.create(
                sol=sol,
                bonup_user=bonup_user,
                name=data["name"],
                email=data["email"],
                phone=data["phone"],
                employer=data.get("employer", ""),
                emergency_contact_name=data.get("emergency_contact_name", ""),
                emergency_contact_phone=data.get("emergency_contact_phone", ""),
                is_bonup_member=is_bonup_member,
                hand_number=hand_number,
                is_manager_participant=is_manager_participant,
                notes=data.get("notes", ""),
            )

            # Auto-generate contract
            total_members = sol.members.filter(is_active=True).count()
            contract_text = _generate_contract_text(sol, member, total_members)
            SolContract.objects.create(
                sol=sol,
                member=member,
                agreed_contribution_amount=sol.contribution_amount,
                agreed_hand_number=hand_number,
                agreed_tip_amount=sol.tip_expectation,
                contract_text=contract_text,
            )

            # Auto-create contribution for any open (upcoming) payout period
            open_payout = sol.payouts.filter(status="upcoming").order_by("cycle_number", "hand_number").first()
            if open_payout and open_payout.recipient_id != member.id:
                SolContribution.objects.get_or_create(
                    payout=open_payout,
                    member=member,
                    defaults={
                        "sol": sol,
                        "amount": sol.contribution_amount,
                        "due_date": open_payout.expected_date,
                    },
                )

        return Response(_serialize_member(member), status=status.HTTP_201_CREATED)


class SolMemberDeleteView(APIView):
    """DELETE /api/sol/<sol_id>/members/<member_id>/"""

    def delete(self, request, sol_id, member_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        member = get_object_or_404(SolMember, pk=member_id, sol=sol)
        member.is_active = False
        member.save(update_fields=["is_active"])
        if member.bonup_user:
            auto_downgrade_from_sol_member(member.bonup_user)
        return Response({"status": "deactivated"})


class SolMemberContractView(APIView):
    """GET /api/sol/<sol_id>/members/<member_id>/contract/"""

    def get(self, request, sol_id, member_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        member = get_object_or_404(SolMember, pk=member_id, sol=sol)
        contract = get_object_or_404(SolContract, member=member)
        return Response({
            "id": str(contract.id),
            "member_name": member.name,
            "hand_number": contract.agreed_hand_number,
            "agreed_contribution_amount": str(contract.agreed_contribution_amount),
            "agreed_tip_amount": str(contract.agreed_tip_amount),
            "contract_text": contract.contract_text,
            "signed_by_member": contract.signed_by_member,
            "signed_at": contract.signed_at,
            "created_at": contract.created_at,
        })


# ---------------------------------------------------------------------------
# Manager: Payouts
# ---------------------------------------------------------------------------

class SolPayoutListCreateView(APIView):
    """GET/POST /api/sol/<sol_id>/payouts/"""

    def get(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        payouts = sol.payouts.prefetch_related("contributions__member")
        return Response({"results": [_serialize_payout(p) for p in payouts]})

    def post(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err

        data = request.data
        if not data.get("expected_date"):
            return Response({"error": "expected_date is required."}, status=status.HTTP_400_BAD_REQUEST)

        active_members = list(sol.members.filter(is_active=True).order_by("hand_number"))
        if not active_members:
            return Response({"error": "No active members in this Sol."}, status=status.HTTP_400_BAD_REQUEST)

        # Determine cycle and next hand number
        existing_payouts = sol.payouts.order_by("cycle_number", "hand_number")
        paid_hands_this_cycle = {}
        for p in existing_payouts:
            paid_hands_this_cycle.setdefault(p.cycle_number, set()).add(p.hand_number)

        total_hands = len(active_members)
        hand_numbers = [m.hand_number for m in active_members]

        # Find current cycle
        cycle_number = 1
        if paid_hands_this_cycle:
            last_cycle = max(paid_hands_this_cycle.keys())
            if set(hand_numbers).issubset(paid_hands_this_cycle.get(last_cycle, set())):
                # All hands in last cycle paid — start next cycle (only for recurring)
                if sol.sol_type == "single":
                    return Response({"error": "Single-cycle Sol is complete."}, status=status.HTTP_400_BAD_REQUEST)
                cycle_number = last_cycle + 1
            else:
                cycle_number = last_cycle

        paid_in_cycle = paid_hands_this_cycle.get(cycle_number, set())
        remaining = [h for h in hand_numbers if h not in paid_in_cycle]
        if not remaining:
            return Response({"error": "All hands for this cycle already scheduled."}, status=status.HTTP_400_BAD_REQUEST)

        next_hand = remaining[0]
        recipient = next(m for m in active_members if m.hand_number == next_hand)
        expected_amount = sol.contribution_amount * (total_hands - 1)

        with transaction.atomic():
            payout = SolPayout.objects.create(
                sol=sol,
                cycle_number=cycle_number,
                hand_number=next_hand,
                recipient=recipient,
                expected_date=data["expected_date"],
                expected_amount=expected_amount,
            )

            # Auto-create contributions for all active members EXCEPT recipient
            contributors = [m for m in active_members if m.id != recipient.id]
            SolContribution.objects.bulk_create([
                SolContribution(
                    sol=sol,
                    payout=payout,
                    member=m,
                    amount=sol.contribution_amount,
                    due_date=data["expected_date"],
                )
                for m in contributors
            ])

        return Response(_serialize_payout(payout), status=status.HTTP_201_CREATED)


class SolPayoutDetailView(APIView):
    """PATCH /api/sol/<sol_id>/payouts/<payout_id>/"""

    def patch(self, request, sol_id, payout_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        payout = get_object_or_404(SolPayout, pk=payout_id, sol=sol)

        data = request.data
        if "status" in data:
            if data["status"] not in dict(SolPayout.STATUS_CHOICES):
                return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
            payout.status = data["status"]
            if data["status"] == "paid":
                payout.paid_date = data.get("paid_date") or timezone.now().date()
                payout.actual_amount = Decimal(str(data["actual_amount"])) if data.get("actual_amount") else payout.expected_amount
                payout.recipient.has_received = True
                payout.recipient.save(update_fields=["has_received"])
        if "expected_date" in data:
            payout.expected_date = data["expected_date"]
        payout.save()
        return Response(_serialize_payout(payout))


class SolPayoutRearrangeView(APIView):
    """POST /api/sol/<sol_id>/payouts/<payout_id>/rearrange/"""

    def post(self, request, sol_id, payout_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        payout = get_object_or_404(SolPayout, pk=payout_id, sol=sol)

        if payout.status not in ("upcoming", "delayed"):
            return Response({"error": "Can only rearrange upcoming or delayed payouts."}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        new_recipient_id = data.get("new_recipient_id")
        reason = data.get("reason", "")

        if not new_recipient_id:
            return Response({"error": "new_recipient_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        new_recipient = get_object_or_404(SolMember, pk=new_recipient_id, sol=sol, is_active=True)

        with transaction.atomic():
            original = payout.recipient
            payout.original_recipient = original
            payout.recipient = new_recipient
            payout.hand_number = new_recipient.hand_number
            payout.was_rearranged = True
            payout.rearranged_reason = reason
            payout.rearranged_by = request.user
            payout.save()

            # Fix contributions: remove new recipient's contribution, add original recipient's
            SolContribution.objects.filter(payout=payout, member=new_recipient).delete()
            SolContribution.objects.get_or_create(
                payout=payout,
                member=original,
                defaults={
                    "sol": sol,
                    "amount": sol.contribution_amount,
                    "due_date": payout.expected_date,
                },
            )

        return Response(_serialize_payout(payout))


class SolContributionUpdateView(APIView):
    """POST /api/sol/<sol_id>/payouts/<payout_id>/contributions/<contribution_id>/"""

    def post(self, request, sol_id, payout_id, contribution_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        payout = get_object_or_404(SolPayout, pk=payout_id, sol=sol)
        contribution = get_object_or_404(SolContribution, pk=contribution_id, payout=payout)

        data = request.data
        if "status" in data:
            if data["status"] not in dict(SolContribution.STATUS_CHOICES):
                return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
            contribution.status = data["status"]
            if data["status"] == "paid":
                contribution.paid_date = data.get("paid_date") or timezone.now().date()
        if "notes" in data:
            contribution.notes = data["notes"]
        contribution.save()
        return Response(_serialize_contribution(contribution))


# ---------------------------------------------------------------------------
# Manager: Dashboard
# ---------------------------------------------------------------------------

class SolDashboardView(APIView):
    """GET /api/sol/<sol_id>/dashboard/"""

    def get(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err

        active_members = sol.members.filter(is_active=True)
        total_members = active_members.count()
        members_received = active_members.filter(has_received=True).count()

        current_payout = sol.payouts.filter(status="upcoming").order_by("cycle_number", "hand_number").first()
        current_payout_data = None
        contribution_summary = None

        if current_payout:
            contributions = current_payout.contributions.select_related("member")
            paid = [c for c in contributions if c.status == "paid"]
            pending = [c for c in contributions if c.status == "pending"]
            late = [c for c in contributions if c.status == "late"]
            missed = [c for c in contributions if c.status == "missed"]
            current_payout_data = _serialize_payout(current_payout)
            contribution_summary = {
                "paid": [_serialize_contribution(c) for c in paid],
                "pending": [_serialize_contribution(c) for c in pending],
                "late": [_serialize_contribution(c) for c in late],
                "missed": [_serialize_contribution(c) for c in missed],
                "paid_count": len(paid),
                "pending_count": len(pending),
                "fund_collected": str(sum(c.amount for c in paid)),
                "fund_outstanding": str(sum(c.amount for c in pending) + sum(c.amount for c in late)),
            }

        # Completion percentage (by hands received / total members)
        completion_pct = round((members_received / total_members * 100), 1) if total_members else 0

        return Response({
            "sol_id": sol.sol_id,
            "name": sol.name,
            "status": sol.status,
            "total_members": total_members,
            "members_received": members_received,
            "completion_percentage": completion_pct,
            "current_payout": current_payout_data,
            "contribution_summary": contribution_summary,
            "total_payouts": sol.payouts.count(),
            "paid_payouts": sol.payouts.filter(status="paid").count(),
        })


# ---------------------------------------------------------------------------
# Manager: Notes
# ---------------------------------------------------------------------------

class SolNotesListCreateView(APIView):
    """GET/POST /api/sol/<sol_id>/notes/"""

    def get(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        notes = sol.notes.all()
        return Response({"results": [
            {"id": str(n.id), "text": n.text, "author_id": n.author_id, "created_at": n.created_at}
            for n in notes
        ]})

    def post(self, request, sol_id):
        sol, err = _manager_sol_or_404(request.user, sol_id)
        if err:
            return err
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"error": "text is required."}, status=status.HTTP_400_BAD_REQUEST)
        note = SolNote.objects.create(sol=sol, author=request.user, text=text)
        return Response({"id": str(note.id), "text": note.text, "created_at": note.created_at}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Tips
# ---------------------------------------------------------------------------

class SolTipCreateView(APIView):
    """POST /api/sol/<sol_id>/tips/ — any active Sol member"""

    def post(self, request, sol_id):
        sol = get_object_or_404(Sol, pk=sol_id)

        # Must be an active member OR the manager
        if _is_manager(request.user, sol):
            from_member = sol.members.filter(is_manager_participant=True, bonup_user=request.user).first()
            if not from_member:
                return Response({"error": "Manager is not a participant member."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                from_member = SolMember.objects.get(sol=sol, bonup_user=request.user, is_active=True)
            except SolMember.DoesNotExist:
                return Response({"error": "Not a member of this Sol."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        if not data.get("amount"):
            return Response({"error": "amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        tip = SolTip.objects.create(
            sol=sol,
            from_member=from_member,
            to_manager=sol.primary_manager,
            amount=Decimal(str(data["amount"])),
            currency=data.get("currency", sol.currency),
            note=data.get("note", ""),
        )
        return Response({
            "id": str(tip.id),
            "from_member": from_member.name,
            "amount": str(tip.amount),
            "currency": tip.currency,
            "note": tip.note,
            "created_at": tip.created_at,
        }, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Member: Own memberships
# ---------------------------------------------------------------------------

class SolMembershipListView(APIView):
    """GET /api/sol/memberships/ — list all Sols the user is an active member of"""

    def get(self, request):
        memberships = SolMember.objects.filter(
            bonup_user=request.user,
            is_active=True,
        ).select_related("sol").order_by("-joined_at")
        return Response({"results": [
            {
                "sol_id": str(m.sol.id),
                "sol_code": m.sol.sol_id,
                "sol_name": m.sol.name,
                "hand_number": m.hand_number,
                "has_received": m.has_received,
                "frequency": m.sol.frequency,
                "contribution_amount": str(m.sol.contribution_amount),
                "currency": m.sol.currency,
                "status": m.sol.status,
                "joined_at": m.joined_at,
            }
            for m in memberships
        ]})


class SolMembershipDetailView(APIView):
    """GET /api/sol/memberships/<sol_id>/ — own membership detail"""

    def get(self, request, sol_id):
        member, sol, err = _member_of_sol(request.user, sol_id)
        if err:
            return err

        # Own contributions
        contributions = SolContribution.objects.filter(member=member).order_by("-due_date")[:20]

        # Next upcoming payout for this member
        next_payout = sol.payouts.filter(
            recipient=member,
            status="upcoming",
        ).order_by("expected_date").first()

        # Own contract
        contract = getattr(member, "contract", None)

        return Response({
            "hand_number": member.hand_number,
            "has_received": member.has_received,
            "sol_name": sol.name,
            "sol_code": sol.sol_id,
            "frequency": sol.frequency,
            "contribution_amount": str(sol.contribution_amount),
            "currency": sol.currency,
            "status": sol.status,
            "contract": {
                "id": str(contract.id),
                "agreed_contribution_amount": str(contract.agreed_contribution_amount),
                "agreed_tip_amount": str(contract.agreed_tip_amount),
                "contract_text": contract.contract_text,
                "signed_by_member": contract.signed_by_member,
                "signed_at": contract.signed_at,
            } if contract else None,
            "next_payout": {
                "payout_id": next_payout.payout_id,
                "expected_date": str(next_payout.expected_date),
                "expected_amount": str(next_payout.expected_amount),
            } if next_payout else None,
            "contribution_history": [_serialize_contribution(c) for c in contributions],
        })
