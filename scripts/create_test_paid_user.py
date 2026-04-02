"""
Create a test paid user with an active technology subscription.
Run inside the Django container:
  docker compose exec backend python manage.py shell < scripts/create_test_paid_user.py
"""
import os, sys, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from apps.billing.models import TechnologySubscription, Plan, Subscription
from apps.question_bank.models import Technology
from django.utils import timezone

User = get_user_model()

# Create or get the test paid user
email = "paiduser@fixitlab.test"
username = "paiduser"
password = "PaidUser@123"

user, created = User.objects.get_or_create(
    email=email,
    defaults={
        "username": username,
        "first_name": "Paid",
        "last_name": "TestUser",
        "is_active": True,
    },
)
if created:
    user.set_password(password)
    user.save()
    print(f"[+] Created user: {username} / {email} / {password}")
else:
    print(f"[=] User already exists: {username} / {email}")

# Ensure they have a free plan subscription
free_plan, _ = Plan.objects.get_or_create(
    code="free",
    defaults={"name": "Free", "price": 0, "max_labs_per_day": 5, "max_lab_duration_minutes": 30},
)
sub, _ = Subscription.objects.get_or_create(
    user=user,
    defaults={"plan": free_plan},
)

# Subscribe to ALL active technologies
techs = Technology.objects.filter(is_active=True)
for tech in techs:
    ts, ts_created = TechnologySubscription.objects.get_or_create(
        user=user,
        technology=tech,
        defaults={
            "amount": 399,
            "is_active": True,
            "payment_verified": True,
        },
    )
    if ts_created:
        print(f"  [+] Subscribed to: {tech.name} (ID: {ts.subscription_id})")
    else:
        # Make sure it's active
        if not ts.is_active:
            ts.is_active = True
            ts.payment_verified = True
            ts.save()
            print(f"  [~] Re-activated subscription: {tech.name}")
        else:
            print(f"  [=] Already subscribed: {tech.name}")

print(f"\n{'='*50}")
print(f"Test Paid User Credentials:")
print(f"  Email:    {email}")
print(f"  Username: {username}")
print(f"  Password: {password}")
print(f"  Subscribed technologies: {', '.join(t.name for t in techs)}")
print(f"{'='*50}")
