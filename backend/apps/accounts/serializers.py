from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Profile


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=17)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=30)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=30)
    # Optional. A wrong or expired code must never block a signup — see create().
    referral_code = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "This email is already registered. "
                "Please sign in or use forgot password to recover your account."
            )
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        phone_number = validated_data.get("phone_number", "")
        first_name = validated_data.get("first_name", "")
        last_name = validated_data.get("last_name", "")

        user = User.objects.create_user(
            username=email,   # internally required by Django
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        # Create profile with phone number, and record which legal text this
        # account agreed to (audit Z4-8). Signing up IS the acceptance — the
        # register form states it — so the version is stamped here rather than
        # behind a separate checkbox that would be one more thing to forget.
        # Read from settings, not from the request: the client is not the
        # authority on which version it was shown.
        from django.conf import settings
        from django.utils import timezone

        # Referral attribution (audit Z6-16). The schema existed and was dead:
        # `referral_code` was generated for every user but `referred_by` was never
        # set by anything, so there was no attribution to reward even if a reward
        # scheme were added later.
        #
        # Attribution is the half that CANNOT be done retroactively — if the
        # referrer is not recorded at signup, that link is gone permanently. The
        # reward policy is a product decision and is deliberately not implemented
        # here; capturing the data is what keeps that decision available.
        referrer = None
        supplied = (validated_data.get("referral_code") or "").strip().upper()
        if supplied:
            referrer = Profile.objects.filter(referral_code=supplied).first()
            if referrer is None:
                # Logged, not raised. Rejecting a signup because someone mistyped a
                # friend's code would cost a customer to protect a statistic.
                import logging

                logging.getLogger(__name__).info(
                    "Signup used an unknown referral code: %s", supplied
                )

        Profile.objects.update_or_create(
            user=user,
            defaults={
                "referred_by": referrer,
                "phone_number": phone_number or None,
                "terms_accepted_at": timezone.now(),
                "terms_version": getattr(settings, "LEGAL_TERMS_VERSION", ""),
                "privacy_version": getattr(settings, "LEGAL_PRIVACY_VERSION", ""),
            },
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

