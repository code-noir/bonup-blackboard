from decimal import Decimal


def apply_payment_to_obligations(instances, payment_amount):
    """
    Applies a payment across multiple obligation instances in order.
    Oldest due first.

    Returns remaining unapplied amount.
    """

    remaining = Decimal(str(payment_amount))

    # Sort by due date (oldest first)
    instances = sorted(instances, key=lambda x: x.due_date)

    for instance in instances:
        if remaining <= 0:
            break

        if instance.is_fully_paid():
            continue

        balance = instance.remaining_balance()

        if remaining >= balance:
            instance.apply_payment(balance)
            remaining -= balance
        else:
            instance.apply_payment(remaining)
            remaining = Decimal("0.00")

    return remaining
