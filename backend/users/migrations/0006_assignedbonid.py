# Generated migration — adds AssignedBonId permanent historical ledger.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_contact'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssignedBonId',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bon_id', models.CharField(
                    db_index=True,
                    editable=False,
                    max_length=13,
                    unique=True,
                    help_text='The 13-digit bonID. Immutable once written.',
                )),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('retired', 'Retired')],
                    default='active',
                    max_length=10,
                )),
                ('user_id_at_assignment', models.BigIntegerField(
                    blank=True,
                    null=True,
                    help_text=(
                        'Django User PK at assignment time. Nullable because the user '
                        'may be hard-deleted later; this record must outlive them.'
                    ),
                )),
                ('email_snapshot', models.EmailField(
                    blank=True,
                    null=True,
                    help_text='Email at assignment. Primary anchor for account restoration.',
                )),
                ('first_name_snapshot', models.CharField(blank=True, max_length=150, null=True)),
                ('last_name_snapshot', models.CharField(blank=True, max_length=150, null=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('retired_at', models.DateTimeField(blank=True, null=True)),
                ('retirement_reason', models.CharField(blank=True, max_length=30, null=True)),
            ],
            options={
                'verbose_name': 'Assigned bonID',
                'verbose_name_plural': 'Assigned bonIDs',
                'ordering': ['bon_id'],
            },
        ),
    ]
