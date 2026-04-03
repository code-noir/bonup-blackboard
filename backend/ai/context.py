# backend/ai/context.py
#
# Builds a runtime user context string injected into system prompts.

from django.db.models import Q
from django.utils import timezone

from backend.billing.gates import get_ai_tier, get_user_subscription
from backend.contract_templates.models import ContractTemplate
from backend.contracts.models import Contract, ContractObligation, ContractServiceObligation
from backend.users.models import BonUserProfile


def build_user_context(user) -> str:
    lines = []

    # --- Identity ---
    try:
        profile = BonUserProfile.objects.get(user=user)
        bon_id = profile.bon_id
    except BonUserProfile.DoesNotExist:
        bon_id = "N/A"

    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    lines.append(f"User: {full_name} (@{user.username})")
    lines.append(f"Email: {user.email}")
    lines.append(f"bonID: {bon_id}")

    # --- Subscription ---
    sub = get_user_subscription(user)
    if sub:
        lines.append(f"Subscription: {sub.plan.display_name} ({sub.status})")
        lines.append(f"AI Tier: {sub.plan.ai_tier}")
    else:
        lines.append("Subscription: None")
        lines.append("AI Tier: none")

    # --- Active contracts ---
    contracts = Contract.objects.filter(
        Q(initiator=user) | Q(counterparty_email=user.email)
    ).order_by("-created_at")[:10]

    if contracts:
        lines.append(f"\nActive Contracts ({contracts.count()}):")
        for c in contracts:
            role = "initiator" if c.initiator_id == user.pk else "counterparty"
            lines.append(
                f"  - Contract {str(c.id)[:8]}... | {c.structure_type} | "
                f"state={c.state} | {role} | counterparty={c.counterparty_email}"
            )
    else:
        lines.append("\nActive Contracts: None")

    # --- Obligations due in next 7 days ---
    now = timezone.now()
    horizon = now + timezone.timedelta(days=7)

    pay_due = ContractObligation.objects.filter(
        Q(obligor=user) | Q(obligee=user),
        due_date__gte=now,
        due_date__lte=horizon,
        state__in=["active", "due"],
    ).order_by("due_date")[:10]

    svc_due = ContractServiceObligation.objects.filter(
        Q(obligor=user) | Q(obligee=user),
        due_date__gte=now,
        due_date__lte=horizon,
        state__in=["active", "due"],
    ).order_by("due_date")[:10]

    obligations_due = list(pay_due) + list(svc_due)
    if obligations_due:
        lines.append(f"\nObligations Due in Next 7 Days ({len(obligations_due)}):")
        for o in pay_due:
            lines.append(
                f"  - Payment obligation | contract={str(o.contract_id)[:8]}... | "
                f"amount={o.amount_due} | due={o.due_date.strftime('%Y-%m-%d')} | state={o.state}"
            )
        for o in svc_due:
            lines.append(
                f"  - Service obligation | contract={str(o.contract_id)[:8]}... | "
                f"desc={o.description[:60]} | due={o.due_date.strftime('%Y-%m-%d')} | state={o.state}"
            )
    else:
        lines.append("\nObligations Due in Next 7 Days: None")

    # --- Available templates ---
    if sub:
        plan = sub.plan
        template_qs = ContractTemplate.objects.filter(is_active=True)
        excluded = plan.excluded_categories or []
        if excluded:
            template_qs = template_qs.exclude(category__in=excluded)
        templates = template_qs.order_by("category", "name")[:50]
        if templates:
            lines.append(f"\nAvailable Templates ({templates.count()}):")
            for t in templates:
                lines.append(f"  - [{t.id}] {t.name} ({t.category} / {t.subcategory})")
        else:
            lines.append("\nAvailable Templates: None")
    else:
        lines.append("\nAvailable Templates: None (no active subscription)")

    return "\n".join(lines)
