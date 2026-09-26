# Enforce the canonical Bon ID format at the model and database boundaries.

import django.core.validators
from django.db import migrations, models


BON_ID_PATTERN = r"^[0-9]{13}$"


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_backfill_businessentity_entity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assignedbonid",
            name="bon_id",
            field=models.CharField(
                db_index=True,
                editable=False,
                help_text="The 13-digit bonID. Immutable once written.",
                max_length=13,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        code="invalid_bon_id",
                        message="Bon ID must be exactly 13 ASCII decimal digits.",
                        regex=BON_ID_PATTERN,
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="bonuserprofile",
            name="bon_id",
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=13,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        code="invalid_bon_id",
                        message="Bon ID must be exactly 13 ASCII decimal digits.",
                        regex=BON_ID_PATTERN,
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="reservedbonid",
            name="bon_id",
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=13,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        code="invalid_bon_id",
                        message="Bon ID must be exactly 13 ASCII decimal digits.",
                        regex=BON_ID_PATTERN,
                    ),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="assignedbonid",
            constraint=models.CheckConstraint(
                condition=models.Q(bon_id__regex=BON_ID_PATTERN),
                name="assigned_bon_id_format",
            ),
        ),
        migrations.AddConstraint(
            model_name="bonuserprofile",
            constraint=models.CheckConstraint(
                condition=models.Q(bon_id__regex=BON_ID_PATTERN),
                name="bon_user_profile_bon_id_format",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservedbonid",
            constraint=models.CheckConstraint(
                condition=models.Q(bon_id__regex=BON_ID_PATTERN),
                name="reserved_bon_id_format",
            ),
        ),
    ]
