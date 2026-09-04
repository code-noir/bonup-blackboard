# backend/api/search/views.py

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import (
    Contract,
    ContractObligation,
    ContractServiceObligation,
)
from backend.contract_templates.models import ContractTemplate
from backend.documents.models import ContractDocument
from backend.notifications.models import Notification
from backend.payments.models import Payment
from backend.sessions.models import LiveSession
from backend.uploads.models import Upload
from backend.uploads.services import get_active_uploads_for_user, get_upload_url
from backend.users.models import BonUserProfile
from backend.sol.models import Sol, SolMember

User = get_user_model()

GLOBAL_RESULT_LIMIT = 10


# ---------------------------------------------------------------------------
# Party / ownership helpers
# ---------------------------------------------------------------------------

def _party_q(user):
    return Q(initiator=user) | Q(counterparty_email=user.email)


def _payment_party_q(user):
    return Q(payer=user) | Q(payee=user)


def _obligation_party_q(user):
    return Q(obligor=user) | Q(obligee=user)


def _session_party_q(user):
    return (
        Q(contract__initiator=user)
        | Q(contract__counterparty_email=user.email)
        | Q(created_by=user)
    )


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_contract(c):
    return {
        "id": str(c.id),
        "counterparty_email": c.counterparty_email,
        "structure_type": c.structure_type,
        "state": c.state,
        "is_active": c.is_active,
        "created_at": c.created_at,
    }


def _serialize_payment_obligation(o):
    return {
        "id": str(o.id),
        "obligation_type": "payment",
        "contract_id": str(o.contract_id),
        "state": o.state,
        "amount_due": str(o.amount_due),
        "due_date": o.due_date,
        "created_at": o.created_at,
    }


def _serialize_service_obligation(o):
    return {
        "id": str(o.id),
        "obligation_type": "service",
        "contract_id": str(o.contract_id),
        "state": o.state,
        "description": o.description,
        "due_date": o.due_date,
        "created_at": o.created_at,
    }


def _serialize_payment(p):
    return {
        "id": str(p.id),
        "contract_id": str(p.contract_id) if p.contract_id else None,
        "amount": str(p.amount),
        "currency": p.currency,
        "status": p.status,
        "payment_method": p.payment_method,
        "reference": p.reference,
        "created_at": p.created_at,
    }


def _serialize_session(s):
    return {
        "id": str(s.id),
        "contract_id": str(s.contract_id) if s.contract_id else None,
        "title": s.title,
        "status": s.status,
        "scheduled_at": s.scheduled_at,
        "created_at": s.created_at,
    }


def _serialize_document(d):
    return {
        "id": str(d.id),
        "contract_id": str(d.contract_id),
        "title": d.title,
        "description": d.description,
        "file_name": d.upload.file_name,
        "file_url": get_upload_url(d.upload),
        "is_proof": d.is_proof,
        "attached_at": d.attached_at,
    }


def _serialize_upload(u):
    return {
        "id": str(u.id),
        "file_name": u.file_name,
        "file_type": u.file_type,
        "file_url": get_upload_url(u),
        "file_size": u.file_size,
        "uploaded_at": u.uploaded_at,
    }


def _serialize_notification(n):
    return {
        "id": str(n.id),
        "notification_type": n.notification_type,
        "title": n.title,
        "message": n.message,
        "is_read": n.is_read,
        "created_at": n.created_at,
    }


def _serialize_user(profile):
    return {
        "bon_id": profile.bon_id,
        "username": profile.user.username,
        "first_name": profile.user.first_name,
        "last_name": profile.user.last_name,
        "email": profile.user.email,
    }


def _serialize_sol(sol):
    return {
        "id": str(sol.id),
        "sol_id": sol.sol_id,
        "name": sol.name,
        "description": sol.description,
        "status": sol.status,
        "frequency": sol.frequency,
        "contribution_amount": str(sol.contribution_amount),
        "currency": sol.currency,
        "active_member_count": sol.active_member_count(),
        "created_at": sol.created_at,
    }


def _serialize_sol_member(member):
    return {
        "source": "sol_member",
        "id": str(member.id),
        "name": member.name,
        "email": member.email,
        "phone": member.phone,
        "sol_id": member.sol.sol_id,
        "sol_name": member.sol.name,
        "hand_number": member.hand_number,
    }


# ---------------------------------------------------------------------------
# User search with prioritization
# ---------------------------------------------------------------------------

def _search_users(q, exclude_user, limit=GLOBAL_RESULT_LIMIT, include_sol_members=False):
    """
    BonID and email exact matches surface first, then partial matches.
    Phone exact match is also prioritized.
    Returns up to `limit` serialized user dicts.
    """
    base_qs = BonUserProfile.objects.select_related("user").exclude(user=exclude_user)

    exact_ids = set()
    results = []

    # 1. BonID exact match
    bon_exact = base_qs.filter(bon_id=q).first()
    if bon_exact:
        exact_ids.add(bon_exact.pk)
        results.append(_serialize_user(bon_exact))

    if len(results) >= limit:
        return results

    # 2. Email exact match
    email_exact = base_qs.exclude(pk__in=exact_ids).filter(user__email__iexact=q).first()
    if email_exact:
        exact_ids.add(email_exact.pk)
        results.append(_serialize_user(email_exact))

    if len(results) >= limit:
        return results

    # 3. Phone exact match
    phone_exact = base_qs.exclude(pk__in=exact_ids).filter(phone=q).first()
    if phone_exact:
        exact_ids.add(phone_exact.pk)
        results.append(_serialize_user(phone_exact))

    if len(results) >= limit:
        return results

    # 4. Partial matches
    remaining = limit - len(results)
    partial_qs = (
        base_qs
        .exclude(pk__in=exact_ids)
        .filter(
            Q(bon_id__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
            | Q(phone__icontains=q)
        )
        .order_by("bon_id")[:remaining]
    )
    results.extend(_serialize_user(p) for p in partial_qs)

    # Sol member lookup across managed Sols
    if include_sol_members and len(results) < limit:
        managed_sol_ids = Sol.objects.filter(
            Q(primary_manager=exclude_user) | Q(co_manager=exclude_user)
        ).values_list("id", flat=True)
        sol_members = (
            SolMember.objects
            .select_related("sol")
            .filter(
                sol_id__in=managed_sol_ids,
                is_active=True,
            )
            .filter(
                Q(name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
            )
            .order_by("sol__sol_id", "hand_number")[: limit - len(results)]
        )
        results.extend(_serialize_sol_member(m) for m in sol_members)

    return results


# ---------------------------------------------------------------------------
# GET /api/search/?q=   (global)
# ---------------------------------------------------------------------------

class GlobalSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"error": "q parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        # Contracts
        contracts = (
            Contract.objects
            .filter(_party_q(user))
            .filter(
                Q(counterparty_email__icontains=q)
                | Q(structure_type__icontains=q)
                | Q(state__icontains=q)
            )
            .order_by("-created_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Obligations — payment type
        pay_obligs = (
            ContractObligation.objects
            .filter(_obligation_party_q(user))
            .filter(Q(state__icontains=q))
            .order_by("due_date")[:GLOBAL_RESULT_LIMIT]
        )
        # Obligations — service type (has description)
        svc_obligs = (
            ContractServiceObligation.objects
            .filter(_obligation_party_q(user))
            .filter(
                Q(state__icontains=q)
                | Q(description__icontains=q)
            )
            .order_by("due_date")[:GLOBAL_RESULT_LIMIT]
        )
        obligations = (
            [_serialize_payment_obligation(o) for o in pay_obligs]
            + [_serialize_service_obligation(o) for o in svc_obligs]
        )[:GLOBAL_RESULT_LIMIT]

        # Payments
        payments = (
            Payment.objects
            .filter(_payment_party_q(user))
            .filter(
                Q(status__icontains=q)
                | Q(currency__icontains=q)
                | Q(reference__icontains=q)
                | Q(payment_method__icontains=q)
            )
            .order_by("-created_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Sessions
        sessions = (
            LiveSession.objects
            .filter(_session_party_q(user))
            .filter(
                Q(title__icontains=q)
                | Q(status__icontains=q)
                | Q(room_name__icontains=q)
            )
            .distinct()
            .order_by("-created_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Documents
        documents = (
            ContractDocument.objects
            .select_related("upload")
            .filter(
                Q(contract__initiator=user) | Q(contract__counterparty_email=user.email)
            )
            .filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(upload__file_name__icontains=q)
            )
            .order_by("-attached_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Uploads
        uploads = (
            get_active_uploads_for_user(user)
            .filter(
                Q(file_name__icontains=q)
                | Q(file_type__icontains=q)
            )
            .order_by("-uploaded_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Notifications
        notifications = (
            Notification.objects
            .filter(user=user)
            .filter(
                Q(title__icontains=q)
                | Q(message__icontains=q)
                | Q(notification_type__icontains=q)
            )
            .order_by("-created_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Templates
        templates = (
            ContractTemplate.objects
            .filter(is_active=True)
            .filter(
                Q(name__icontains=q)
                | Q(category__icontains=q)
                | Q(subcategory__icontains=q)
            )
            .order_by("name")[:GLOBAL_RESULT_LIMIT]
        )

        # Sol groups (manager or member)
        member_sol_ids = SolMember.objects.filter(
            bonup_user=user, is_active=True
        ).values_list("sol_id", flat=True)
        sols = (
            Sol.objects
            .filter(
                Q(primary_manager=user) | Q(co_manager=user) | Q(id__in=member_sol_ids)
            )
            .filter(
                Q(name__icontains=q)
                | Q(sol_id__icontains=q)
                | Q(description__icontains=q)
            )
            .distinct()
            .order_by("-created_at")[:GLOBAL_RESULT_LIMIT]
        )

        # Users
        users = _search_users(q, exclude_user=user, include_sol_members=True)

        return Response({
            "contracts": [_serialize_contract(c) for c in contracts],
            "obligations": obligations,
            "payments": [_serialize_payment(p) for p in payments],
            "sessions": [_serialize_session(s) for s in sessions],
            "documents": [_serialize_document(d) for d in documents],
            "uploads": [_serialize_upload(u) for u in uploads],
            "notifications": [_serialize_notification(n) for n in notifications],
            "templates": [_serialize_template(t) for t in templates],
            "sol": [_serialize_sol(s) for s in sols],
            "users": users,
        })


# ---------------------------------------------------------------------------
# GET /api/search/contracts/?q=&status=&structure_type=&date_from=&date_to=
# ---------------------------------------------------------------------------

def _serialize_template(t):
    return {
        "id": str(t.id),
        "name": t.name,
        "category": t.category,
        "subcategory": t.subcategory,
        "structure_type": t.structure_type,
        "tier_required": t.tier_required,
    }


class ContractSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        user = request.user

        qs = Contract.objects.filter(_party_q(user))

        if q:
            qs = qs.filter(
                Q(counterparty_email__icontains=q)
                | Q(structure_type__icontains=q)
                | Q(state__icontains=q)
            )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(state=status_filter)

        structure_type = request.query_params.get("structure_type")
        if structure_type:
            qs = qs.filter(structure_type=structure_type)

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return Response([_serialize_contract(c) for c in qs.order_by("-created_at")])


# ---------------------------------------------------------------------------
# GET /api/search/obligations/?q=&status=&obligation_type=
# ---------------------------------------------------------------------------

class ObligationSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        user = request.user
        obligation_type = request.query_params.get("obligation_type", "").strip().lower()
        status_filter = request.query_params.get("status", "").strip()

        results = []

        if obligation_type != "service":
            pay_qs = ContractObligation.objects.filter(_obligation_party_q(user))
            if q:
                pay_qs = pay_qs.filter(Q(state__icontains=q))
            if status_filter:
                pay_qs = pay_qs.filter(state=status_filter)
            results += [_serialize_payment_obligation(o) for o in pay_qs.order_by("due_date")]

        if obligation_type != "payment":
            svc_qs = ContractServiceObligation.objects.filter(_obligation_party_q(user))
            if q:
                svc_qs = svc_qs.filter(
                    Q(state__icontains=q) | Q(description__icontains=q)
                )
            if status_filter:
                svc_qs = svc_qs.filter(state=status_filter)
            results += [_serialize_service_obligation(o) for o in svc_qs.order_by("due_date")]

        return Response(results)


# ---------------------------------------------------------------------------
# GET /api/search/payments/?q=&status=
# ---------------------------------------------------------------------------

class PaymentSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        user = request.user

        qs = Payment.objects.filter(_payment_party_q(user))

        if q:
            qs = qs.filter(
                Q(status__icontains=q)
                | Q(currency__icontains=q)
                | Q(reference__icontains=q)
                | Q(payment_method__icontains=q)
            )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response([_serialize_payment(p) for p in qs.order_by("-created_at")])


# ---------------------------------------------------------------------------
# GET /api/search/sessions/?q=&status=
# ---------------------------------------------------------------------------

class SessionSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        user = request.user

        qs = LiveSession.objects.filter(_session_party_q(user)).distinct()

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(status__icontains=q)
                | Q(room_name__icontains=q)
            )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response([_serialize_session(s) for s in qs.order_by("-created_at")])


# ---------------------------------------------------------------------------
# GET /api/search/documents/?q=
# ---------------------------------------------------------------------------

class DocumentSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        user = request.user

        qs = (
            ContractDocument.objects
            .select_related("upload")
            .filter(
                Q(contract__initiator=user) | Q(contract__counterparty_email=user.email)
            )
        )

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(upload__file_name__icontains=q)
            )

        return Response([_serialize_document(d) for d in qs.order_by("-attached_at")])


# ---------------------------------------------------------------------------
# GET /api/search/templates/?q=&category=
# ---------------------------------------------------------------------------

class TemplateSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()

        qs = ContractTemplate.objects.filter(is_active=True)

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(category__icontains=q)
                | Q(subcategory__icontains=q)
            )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        return Response([_serialize_template(t) for t in qs.order_by("name")])


# ---------------------------------------------------------------------------
# GET /api/search/sol/?q=&status=&frequency=
# ---------------------------------------------------------------------------

class SolSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        user = request.user

        member_sol_ids = SolMember.objects.filter(
            bonup_user=user, is_active=True
        ).values_list("sol_id", flat=True)

        qs = Sol.objects.filter(
            Q(primary_manager=user) | Q(co_manager=user) | Q(id__in=member_sol_ids)
        ).distinct()

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(sol_id__icontains=q)
                | Q(description__icontains=q)
            )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        frequency_filter = request.query_params.get("frequency")
        if frequency_filter:
            qs = qs.filter(frequency=frequency_filter)

        return Response([_serialize_sol(s) for s in qs.order_by("-created_at")])
