from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create a Profile when a new User is created.
    Uses get_or_create to avoid duplicate creation if RegisterSerializer
    already created the profile.
    """
    if created:
        Profile.objects.get_or_create(user=instance)
