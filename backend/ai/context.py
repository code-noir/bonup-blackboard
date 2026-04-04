# backend/ai/context.py
#
# Builds a runtime user context string injected into system prompts.

from django.db.models import Q
from django.utils import timezone

from backend.billing.gates import get_ai_tier, get_user_subscription
from backend.contract_templates.models import ContractTemplate
from backend.contracts.models import Contract, ContractObligation, ContractServiceObligation
from backend.users.models import BonUserProfile
from backend.sol.models import Sol, SolMember, SolContribution


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

    # --- Sol manager view ---
    today = timezone.now().date()
    managed_sols = Sol.objects.filter(
        Q(primary_manager=user) | Q(co_manager=user),
        status="active",
    ).order_by("sol_id")

    if managed_sols.exists():
        lines.append(f"\nSol Groups Managed ({managed_sols.count()}):")
        for sol in managed_sols:
            active_count = sol.active_member_count()
            lines.append(f"  Sol: {sol.name} ({sol.sol_id}) | {active_count} active members | {sol.frequency} | {sol.contribution_amount} {sol.currency}/member")

            # Current / upcoming payout
            upcoming_payout = sol.payouts.filter(
                status="upcoming", expected_date__gte=today
            ).order_by("expected_date").first()

            if upcoming_payout is None:
                upcoming_payout = sol.payouts.filter(
                    status="upcoming"
                ).order_by("expected_date").last()

            if upcoming_payout:
                lines.append(f"    Current payout: {upcoming_payout.payout_id} | recipient={upcoming_payout.recipient.name} | due={upcoming_payout.expected_date} | amount={upcoming_payout.expected_amount} {sol.currency}")
                paid = upcoming_payout.contributions.filter(status="paid")
                pending = upcoming_payout.contributions.exclude(status="paid")
                paid_names = ", ".join(c.member.name for c in paid) or "none"
                pending_names = ", ".join(c.member.name for c in pending) or "none"
                lines.append(f"    Contributions paid ({paid.count()}): {paid_names}")
                lines.append(f"    Contributions pending ({pending.count()}): {pending_names}")
            else:
                lines.append("    No upcoming payouts scheduled.")
    else:
        lines.append("\nSol Groups Managed: None")

    # --- Sol member view ---
    memberships = SolMember.objects.filter(
        bonup_user=user, is_active=True
    ).select_related("sol").order_by("sol__sol_id")

    if memberships.exists():
        lines.append(f"\nSol Memberships ({memberships.count()}):")
        for membership in memberships:
            sol = membership.sol
            lines.append(f"  Sol: {sol.name} ({sol.sol_id}) | hand #{membership.hand_number} | {sol.contribution_amount} {sol.currency}/{sol.frequency}")

            # Upcoming payout for this member as recipient
            own_payout = sol.payouts.filter(
                recipient=membership, status="upcoming", expected_date__gte=today
            ).order_by("expected_date").first()
            if own_payout:
                lines.append(f"    My payout: {own_payout.payout_id} | expected={own_payout.expected_date} | amount={own_payout.expected_amount} {sol.currency}")
            else:
                lines.append("    My payout: not yet scheduled")

            # Own contribution status for the current open payout period
            open_payout = sol.payouts.filter(
                status="upcoming"
            ).order_by("expected_date").first()
            if open_payout:
                try:
                    contrib = SolContribution.objects.get(payout=open_payout, member=membership)
                    lines.append(f"    My contribution this period: {contrib.status} | due={contrib.due_date}")
                except SolContribution.DoesNotExist:
                    lines.append("    My contribution this period: not recorded")
    else:
        lines.append("\nSol Memberships: None")

    return "\n".join(lines)
