import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0021_contract_currency_contractobligation_currency'),
        ('users', '0004_business_entity'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='entity_type',
            field=models.CharField(
                choices=[('personal', 'Personal'), ('business', 'Business')],
                default='personal',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='contract',
            name='entity',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contracts',
                to='users.businessentity',
            ),
        ),
    ]
