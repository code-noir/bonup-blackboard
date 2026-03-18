#backend/users/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from backend.users.models import BonUserProfile


User = get_user_model()


@receiver(post_save, sender=User)
def create_bon_user_profile(sender, instance, created, **kwargs):
    if created:
        BonUserProfile.objects.get_or_create(user=instance)

