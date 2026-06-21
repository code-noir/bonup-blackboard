# Generated for Agreement Timeline notifications

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("contract_created", "Contract Created"),
                    ("contract_updated", "Contract Updated"),
                    ("agreement_exchange", "Agreement Exchange"),
                    ("agreement_timeline", "Agreement Timeline"),
                    ("version_created", "Version Created"),
                    ("version_signed", "Version Signed"),
                    ("version_rejected", "Version Rejected"),
                    ("role_switch_requested", "Role Switch Requested"),
                    ("role_switch_confirmed", "Role Switch Confirmed"),
                    ("obligation_resolved", "Obligation Resolved"),
                    ("payment_obligation_resolved", "Payment Obligation Resolved"),
                    ("payment_created", "Payment Created"),
                    ("payment_confirmed", "Payment Confirmed"),
                    ("payment_failed", "Payment Failed"),
                    ("payment_cancelled", "Payment Cancelled"),
                    ("payment_refunded", "Payment Refunded"),
                    ("payment_reversed", "Payment Reversed"),
                    ("approval_requested", "Approval Requested"),
                    ("approval_granted", "Approval Granted"),
                    ("approval_rejected", "Approval Rejected"),
                    ("session_held", "Session Held"),
                ],
                max_length=50,
            ),
        ),
    ]
