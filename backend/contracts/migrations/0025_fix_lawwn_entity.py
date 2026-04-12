from django.db import migrations


def fix_lawwn_entity(apps, schema_editor):
    """
    'lawwn ca mrley' was created as entity_type='personal' but belongs to
    A&C Lawn Care (5f982747-6db8-4a7a-8732-75c090d73210).
    Correct it so all three A&C Lawn Care contracts are consistently typed.
    """
    Contract = apps.get_model('contracts', 'Contract')
    BusinessEntity = apps.get_model('users', 'BusinessEntity')

    ANC_ID = '5f982747-6db8-4a7a-8732-75c090d73210'

    try:
        anc = BusinessEntity.objects.get(pk=ANC_ID)
    except BusinessEntity.DoesNotExist:
        return  # nothing to fix in this environment

    Contract.objects.filter(
        title='lawwn ca mrley',
        entity_type='personal',
        entity_id__isnull=True,
    ).update(entity_type='business', entity=anc)


def reverse_fix(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.filter(
        title='lawwn ca mrley',
        entity_type='business',
    ).update(entity_type='personal', entity=None)


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0024_contract_counterparty_name_rename_value'),
    ]

    operations = [
        migrations.RunPython(fix_lawwn_entity, reverse_code=reverse_fix),
    ]
