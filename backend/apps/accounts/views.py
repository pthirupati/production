import logging
import secrets

from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework import status
from common.throttles import (
    ContactRateThrottle,
    LoginRateThrottle,
    OTPRateThrottle,
    PasswordResetRateThrottle,
    TokenRefreshThrottle,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


def set_auth_cookies(response, access_token, refresh_token=None):
    """Set httpOnly JWT cookies on a DRF Response object."""
    secure = not settings.DEBUG
    common_opts = {
        'httponly': True,
        'secure': secure,
        'samesite': 'Lax',
        'path': '/',
    }
    response.set_cookie(
        'access_token',
        access_token,
        max_age=60 * 15,  # 15 minutes — matches SIMPLE_JWT ACCESS_TOKEN_LIFETIME
        **common_opts,
    )
    if refresh_token:
        response.set_cookie(
            'refresh_token',
            refresh_token,
            max_age=60 * 60 * 24 * 7,  # 7 days — matches SIMPLE_JWT REFRESH_TOKEN_LIFETIME
            **common_opts,
        )
    return response

from .serializers import (
    RegisterSerializer, LoginSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
)
from .models import Profile, PasswordResetToken, EmailVerificationOTP, SocialAccount
from apps.notifications.email_dispatch import dispatch_notification_email
from apps.notifications.tasks import send_notification_email, create_in_app_notification
from common.security import SessionTracker, TokenHelper
from apps.auth_app.cookie_auth import LogoutJWTAuthentication
from common.logging_utils import get_structured_logger

User = get_user_model()
logger = logging.getLogger(__name__)
structured_logger = get_structured_logger(__name__)



class AuthRateThrottle(AnonRateThrottle):
    """Strict rate limiting for auth endpoints to prevent brute-force."""
    scope = 'auth'


class SendOTPView(APIView):
    """Send a 6-digit OTP to an email for verification during registration."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response({"error": "Email is required."}, status=400)

        # Validate email format
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_email(email)
        except DjangoValidationError:
            return Response({"error": "Please enter a valid email address."}, status=400)

        # Check if email already registered
        if User.objects.filter(email=email).exists():
            return Response(
                {
                    "error": (
                        "This email is already registered. "
                        "Please sign in or use forgot password to recover your account."
                    ),
                    "error_code": "email_exists",
                },
                status=400,
            )

        from apps.notifications.gmail_api import is_gmail_api_configured
        from django.conf import settings as django_settings

        email_configured = (
            is_gmail_api_configured()
            or getattr(django_settings, "SENDGRID_API_KEY", "")
            or (
                getattr(django_settings, "EMAIL_HOST_USER", "")
                and django_settings.EMAIL_HOST not in ("mailhog", "localhost", "127.0.0.1")
            )
        )
        if not email_configured:
            logger.error("OTP requested but no email delivery method is configured")
            return Response(
                {
                    "error": (
                        "Email service is temporarily unavailable. "
                        "Please try again in a few minutes."
                    ),
                    "error_code": "email_unavailable",
                },
                status=503,
            )

        otp_expiry_minutes = 2
        try:
            otp_obj, code, session_token = EmailVerificationOTP.generate(
                email, minutes=otp_expiry_minutes
            )

            dispatch_notification_email(
                subject="FixitLab - Verify Your Email",
                to_email=email,
                template="emails/otp_verification.html",
                context={
                    "otp_code": code,
                    "expires_minutes": otp_expiry_minutes,
                },
                critical=True,
            )
            logger.info(f"OTP queued for {email}")
        except Exception as e:
            logger.error(f"Failed to send OTP to {email}: {e}")
            return Response(
                {
                    "error": (
                        "Could not send verification email. "
                        "Please try again in a few minutes."
                    ),
                    "error_code": "email_send_failed",
                },
                status=503,
            )

        return Response({
            "message": "Verification code sent to your email.",
            "session_token": session_token,
            "expires_at": otp_obj.expires_at.isoformat(),
            "expires_in_seconds": otp_expiry_minutes * 60,
        })


class VerifyOTPView(APIView):
    """Verify the 6-digit OTP code."""
    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        session_token = request.data.get("session_token", "")
        code = request.data.get("code", "").strip()

        if not session_token or not code:
            return Response({"error": "Session token and code are required."}, status=400)

        otp_obj, error = EmailVerificationOTP.verify(session_token, code)
        if error:
            error_lower = error.lower()
            if "too many failed attempts" in error_lower:
                error_code = "otp_max_attempts"
            elif "expired" in error_lower:
                error_code = "otp_expired"
            else:
                error_code = "otp_invalid"
            return Response({"error": error, "error_code": error_code}, status=400)

        return Response({
            "message": "Email verified successfully.",
            "session_token": session_token,
            "email": otp_obj.email,
        })


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        # Require verified OTP session
        session_token = request.data.get("session_token", "")
        if not session_token:
            return Response(
                {"error": "Email verification is required. Please verify your email first."},
                status=400,
            )

        try:
            otp_obj = EmailVerificationOTP.objects.get(
                session_token=session_token, verified=True
            )
        except EmailVerificationOTP.DoesNotExist:
            return Response(
                {"error": "Invalid or expired verification. Please verify your email again."},
                status=400,
            )

        # The OTP's short ``expires_at`` (2 min) is the window to ENTER the code,
        # not to finish registration. Once the code is verified, give the user a
        # generous grace period to fill in the rest of the form and submit — the
        # tight code-entry window must not invalidate an already-verified email.
        # (Regression: previously this reused ``is_expired`` (2 min from send), so
        # any user who took >2 min after requesting the OTP got "Verification has
        # expired" even though they entered the code correctly.)
        REGISTRATION_GRACE_MINUTES = 30
        registration_deadline = otp_obj.created_at + timezone.timedelta(
            minutes=REGISTRATION_GRACE_MINUTES
        )
        if timezone.now() > registration_deadline:
            return Response(
                {"error": "Verification has expired. Please verify your email again."},
                status=400,
            )

        # Force the email from the verified OTP
        data = request.data.copy()
        data["email"] = otp_obj.email

        if User.objects.filter(email=otp_obj.email).exists():
            return Response(
                {
                    "error": (
                        "This email is already registered. "
                        "Please sign in or use forgot password to recover your account."
                    ),
                    "error_code": "email_exists",
                },
                status=400,
            )

        serializer = RegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Accept pending org invites for this email.
        #
        # SECURITY (audit Z2-2): this used to match on email alone and grant
        # `invite.role` verbatim — so a pending invite silently made whoever next
        # registered that address an organisation **admin**, for the full 14-day
        # window. A typo'd invite, or an address that changes hands, was enough.
        # The unique `token` existed for exactly this and was never checked.
        #
        # An email match now confers MEMBER only. The invited role is honoured just
        # when the request carries the matching token — i.e. the person demonstrably
        # received the invite email. Auto-join still works without it, so no
        # legitimate flow breaks; it simply cannot hand out privilege any more.
        from .models import PendingOrgInvite, OrganizationMember

        supplied_token = str(request.data.get("invite_token") or "").strip()
        _ELEVATED = {"admin", "owner"}
        for invite in PendingOrgInvite.objects.filter(
            email__iexact=user.email, accepted_at__isnull=True, expires_at__gt=timezone.now(),
        ).select_related("organization"):
            token_ok = bool(
                supplied_token
                and invite.token
                and secrets.compare_digest(supplied_token, invite.token)
            )
            granted_role = invite.role
            if invite.role in _ELEVATED and not token_ok:
                granted_role = "member"
                logger.warning(
                    "Org invite for %s requested role %r without a valid token — "
                    "granting 'member' instead (org=%s)",
                    user.email, invite.role, invite.organization_id,
                )
            if invite.organization.member_count < invite.organization.seat_limit:
                OrganizationMember.objects.get_or_create(
                    organization=invite.organization,
                    user=user,
                    defaults={"role": granted_role, "invited_email": user.email},
                )
            invite.accepted_at = timezone.now()
            invite.save(update_fields=["accepted_at"])
            try:
                from .webhooks import fire_org_webhook
                fire_org_webhook(invite.organization, "member.joined", {
                    "user": user.username, "email": user.email, "role": invite.role,
                })
            except Exception:
                pass

        # Send welcome email asynchronously
        try:
            send_notification_email.delay(
                subject="Welcome to FixitLab!",
                to_email=user.email,
                template="emails/welcome.html",
                context={
                    "username": user.username,
                    "email": user.email,
                    "login_url": f"{settings.FRONTEND_URL}/login",
                    "scenarios_url": f"{settings.FRONTEND_URL}/scenarios",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to queue welcome email: {e}")

        # Create in-app welcome notification
        try:
            create_in_app_notification.delay(
                user_id=user.id,
                notification_type="welcome",
                title="Welcome to FixitLab!",
                message="Start with an easy challenge to get familiar with the platform. Check the Technologies page to explore scenarios.",
                metadata={"action_url": "/technologies"},
            )
        except Exception as e:
            logger.warning(f"Failed to create welcome notification: {e}")

        # Return tokens immediately so user is logged in. Use the session-aware
        # helper so the jti is recorded in SessionTracker — otherwise the brand-new
        # user's first request is 401'd whenever JWT session enforcement is on.
        # If token minting fails (e.g. a JWT-key/cache hiccup), the account was
        # already created successfully — surface a SPECIFIC, actionable error so
        # the user is told to just sign in, not a generic "registration failed".
        try:
            _toks = TokenHelper.create_tokens_with_session(
                user,
                getattr(request, "client_ip", "") or "",
                getattr(request, "user_agent", "") or "",
            )
            access_token = _toks["access"]
            refresh_token = _toks["refresh"]
        except Exception as token_err:
            logger.error(
                "Token issuance failed after registering user %s (%s): %s",
                user.id, user.email, token_err, exc_info=True,
            )
            return Response(
                {
                    "error": (
                        "Your account was created, but we couldn't sign you in "
                        "automatically. Please go to the login page and sign in."
                    ),
                    "error_code": "token_issue_failed",
                },
                status=status.HTTP_201_CREATED,
            )
        response = Response({
            "message": "User registered successfully",
            "access": access_token,
            "refresh": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_staff": user.is_staff,
                "date_joined": user.date_joined.isoformat(),
            },
        }, status=201)
        set_auth_cookies(response, access_token, refresh_token)
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        client_ip = getattr(request, "client_ip", None) or request.META.get("REMOTE_ADDR", "")
        try:
            from apps.adminpanel.security_helpers import is_ip_blocked
            if is_ip_blocked(client_ip):
                return Response({"error": "Access denied from this network."}, status=403)
        except Exception:
            # FAILS OPEN by design — an outage in the blocklist backend must not
            # lock every user out of login. But it must be LOUD: silently
            # swallowing this meant the IP blocklist could be down indefinitely
            # with no signal, so a blocked network would sail straight through.
            logger.warning(
                "IP blocklist check failed for %s — allowing login attempt "
                "(control is failing OPEN)", client_ip, exc_info=True,
            )

        def _record_login_failure():
            # Count this as a brute-force attempt against (IP + email). Only
            # failures consume the login throttle quota; successful logins do
            # not, so legitimate / concurrent sign-ins are never locked out.
            try:
                throttle = LoginRateThrottle()
                throttle.allow_request(request, self)  # primes throttle.key/now
                throttle.record_failure(request, self)
            except Exception:
                # Losing this silently is worse than it looks: the login throttle
                # counts FAILURES only, so a swallowed exception here means the
                # brute-force counter stops incrementing and the rate limit
                # effectively stops enforcing — while still appearing configured.
                logger.warning(
                    "Failed to record login failure for throttling (brute-force "
                    "counter did NOT increment)", exc_info=True,
                )

        # Look up user by email, then authenticate by username
        user_obj = User.objects.filter(email=email).first()
        if not user_obj:
            structured_logger.warning(
                "Login attempt with non-existent email",
                email=email,
                ip=request.client_ip if hasattr(request, 'client_ip') else '',
                tags=["auth", "security"]
            )
            try:
                from apps.audit.models import AuditLog
                AuditLog.objects.create(
                    action="login_failed",
                    resource=email,
                    metadata={"reason": "unknown_email"},
                    ip_address=getattr(request, "client_ip", None) or None,
                    user_agent=getattr(request, "user_agent", "") or "",
                )
            except Exception:
                pass
            _record_login_failure()
            return Response({"error": "Invalid credentials"}, status=401)

        user = authenticate(username=user_obj.username, password=password)

        if not user:
            structured_logger.warning(
                "Login attempt with incorrect password",
                user_id=user_obj.id,
                email=email,
                ip=request.client_ip if hasattr(request, 'client_ip') else '',
                tags=["auth", "security"]
            )
            try:
                from apps.audit.models import AuditLog
                AuditLog.objects.create(
                    user=user_obj,
                    action="login_failed",
                    resource=email,
                    metadata={"reason": "bad_password"},
                    ip_address=getattr(request, "client_ip", None) or None,
                    user_agent=getattr(request, "user_agent", "") or "",
                )
            except Exception:
                pass
            _record_login_failure()
            return Response({"error": "Invalid credentials"}, status=401)

        if not user.is_active:
            structured_logger.warning(
                "Login attempt on disabled account",
                user_id=user.id,
                email=email,
                ip=request.client_ip if hasattr(request, 'client_ip') else '',
                tags=["auth"]
            )
            return Response({"error": "Account is disabled"}, status=403)

        # ── Second factor (audit Z2-3) ────────────────────────────────────────
        #
        # Checked AFTER the password, so this never reveals whether an account
        # exists or has MFA — an unauthenticated caller cannot reach it.
        #
        # Staff and superusers are required to have MFA, but the ones that exist
        # today have no device. Refusing them outright would lock every
        # administrator out of the platform on deploy, so a required-but-unenrolled
        # account is sent to enrolment instead. That is the difference between
        # rolling out MFA and causing an outage.
        from .mfa_models import mfa_recommended_for, mfa_required_for
        from .mfa_views import issue_mfa_challenge

        device = getattr(user, "mfa_device", None)
        if device and device.enabled:
            structured_logger.info(
                "Login passed password, awaiting MFA", user_id=user.id,
                tags=["auth", "mfa"],
            )
            return Response(
                {
                    "mfa_required": True,
                    "mfa_token": issue_mfa_challenge(user),
                    "message": "Enter the 6-digit code from your authenticator app.",
                },
                status=status.HTTP_200_OK,
            )
        if mfa_required_for(user):
            # Staff without a confirmed device: allow the session so they can set
            # MFA up, and flag it loudly. `mfa_enrollment_required` is what the UI
            # uses to force them through setup before anything else.
            logger.warning(
                "Staff account %s signed in without MFA enrolled", user.id
            )

        # Update last_login timestamp
        from django.utils import timezone as tz
        user.last_login = tz.now()
        user.save(update_fields=["last_login"])

        # Create tokens with session tracking
        ip_address = request.client_ip if hasattr(request, 'client_ip') else ''
        user_agent = request.user_agent if hasattr(request, 'user_agent') else ''
        
        tokens = TokenHelper.create_tokens_with_session(user, ip_address, user_agent)
        
        structured_logger.info(
            "User login successful",
            user_id=user.id,
            email=email,
            ip=ip_address,
            tags=["auth", "success"]
        )
        
        response = Response({
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_staff": user.is_staff,
                "date_joined": user.date_joined.isoformat(),
            },
            "mfa_enrollment_required": bool(
                (user.is_staff or user.is_superuser)
                and not (device and device.enabled)
            ),
            # Suggested, never required (audit Z2-3). True only for accounts
            # holding resume / interview content, and snoozed for 30 days once
            # dismissed — a prompt on every login is one people click past.
            "mfa_recommended": mfa_recommended_for(user),
        })
        set_auth_cookies(response, tokens["access"], tokens["refresh"])
        return response


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .mfa_models import mfa_recommended_for

        try:
            user = request.user
            profile = Profile.objects.filter(user=user).first()
            social = list(
                SocialAccount.objects.filter(user=user).values("provider", "provider_uid", "created_at")
            )
            return Response({
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": profile.phone_number if profile else None,
                "country": profile.country if profile else "",
                "billing_state": profile.billing_state if profile else "",
                # Audit Z4-8: what this account agreed to, and whether the current
                # text has moved on since. `needs_legal_reacceptance` is what a
                # client should branch on — comparing versions in the UI would put
                # the comparison in the wrong place.
                "terms_version": profile.terms_version if profile else "",
                "privacy_version": profile.privacy_version if profile else "",
                "current_terms_version": settings.LEGAL_TERMS_VERSION,
                "current_privacy_version": settings.LEGAL_PRIVACY_VERSION,
                "mfa_enabled": bool(getattr(user, "mfa_device", None) and user.mfa_device.enabled),
                "mfa_recommended": mfa_recommended_for(user),
                "needs_legal_reacceptance": bool(
                    profile
                    and (
                        profile.terms_version != settings.LEGAL_TERMS_VERSION
                        or profile.privacy_version != settings.LEGAL_PRIVACY_VERSION
                    )
                ),
                "is_staff": user.is_staff,
                "has_usable_password": user.has_usable_password(),
                "date_joined": user.date_joined.isoformat(),
                "social_accounts": [
                    {
                        "provider": s["provider"],
                        "linked_at": s["created_at"].isoformat() if s.get("created_at") else None,
                    }
                    for s in social
                ],
                "support_bot_enabled": profile.support_bot_enabled if profile else True,
                "interview_processing_consent": (
                    profile.interview_processing_consent if profile else True
                ),
            })
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Profile fetch error: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to load profile. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request):
        try:
            user = request.user
            username = request.data.get("username", user.username)
            phone_number = request.data.get("phone_number")
            first_name = request.data.get("first_name")
            last_name = request.data.get("last_name")

            from django.contrib.auth import get_user_model
            User = get_user_model()
            if username != user.username and User.objects.filter(username=username).exists():
                return Response(
                    {"error": "Username already taken"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.username = username
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            user.save()

            profile, _ = Profile.objects.get_or_create(user=user)
            if phone_number is not None:
                profile.phone_number = phone_number or None
            country = request.data.get("country")
            if country is not None:
                profile.country = country
            # GST place of supply (audit Z1-13). Validated against the state list
            # rather than stored free-text: a typo ("Karnatka") is not merely untidy,
            # it flips the supply from intra-state to inter-state and puts the wrong
            # tax heads on the invoice. Blank is a legitimate value meaning "no
            # address on record".
            billing_state = request.data.get("billing_state")
            if billing_state is not None:
                billing_state = (billing_state or "").strip()
                if billing_state:
                    from apps.billing.gst import INDIAN_STATES

                    match = next(
                        (s for s in INDIAN_STATES if s.lower() == billing_state.lower()),
                        None,
                    )
                    if match is None:
                        return Response(
                            {"error": f"'{billing_state}' is not a recognised Indian state or union territory."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    billing_state = match
                profile.billing_state = billing_state
            if "support_bot_enabled" in request.data:
                profile.support_bot_enabled = bool(request.data.get("support_bot_enabled"))
            if "interview_processing_consent" in request.data:
                profile.interview_processing_consent = bool(
                    request.data.get("interview_processing_consent")
                )
            profile.save()

            return Response({
                "message": "Profile updated",
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": profile.phone_number,
                "country": profile.country,
                "billing_state": profile.billing_state,
                "support_bot_enabled": profile.support_bot_enabled,
                "interview_processing_consent": profile.interview_processing_consent,
            })
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Profile update error: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to update profile. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DeleteAccountView(APIView):
    """Self-service permanent account deletion (GDPR)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        confirm = (request.data.get("confirm") or "").strip()
        password = request.data.get("password") or ""

        if confirm != "DELETE MY ACCOUNT":
            return Response(
                {"error": 'Type exactly "DELETE MY ACCOUNT" to confirm permanent deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if user.is_staff or user.is_superuser:
            return Response(
                {"error": "Staff accounts cannot be deleted via self-service. Contact an administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.has_usable_password():
            if not password:
                return Response(
                    {"error": "Password is required to delete your account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not user.check_password(password):
                return Response(
                    {"error": "Incorrect password."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from apps.accounts.models import AccountLifecycleEvent

        user_id = user.id
        email = user.email
        username = user.username

        AccountLifecycleEvent.objects.create(
            user=None,
            email=email,
            event_type="deleted",
            metadata={
                "user_id": user_id,
                "username": username,
                "reason": "self_service",
            },
        )

        try:
            refresh = request.data.get("refresh")
            if refresh:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh)
                token.blacklist()
        except Exception:
            pass

        user.delete()
        logger.info("Self-service account deletion: user_id=%s email=%s", user_id, email)

        return Response({
            "message": "Your account and all associated data have been permanently deleted.",
        })


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response({"error": "Both old and new passwords required"}, status=400)

        if not user.check_password(old_password):
            return Response({"error": "Current password is incorrect"}, status=400)

        # Enforce the same password policy as registration (length + complexity)
        # instead of a weaker ad-hoc 8-char minimum.
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response({"error": " ".join(exc.messages)}, status=400)

        user.set_password(new_password)
        user.save()

        # Revoke all active JWT sessions so any token issued before the change
        # (e.g. one held by an attacker) can no longer be used. The client's own
        # next request will fail the session check and be prompted to re-login.
        try:
            SessionTracker.invalidate_all_sessions(user.id)
        except Exception:
            logger.warning("Failed to invalidate sessions after password change for user %s", user.id)

        return Response({"message": "Password changed successfully"})


class LogoutView(APIView):
    """Blacklist the refresh token and clear auth cookies."""
    # Logout is idempotent: tolerate a valid-but-tombstoned session (e.g. right
    # after a password change) so the user can always end the session + clear
    # cookies. Session-invalidation enforcement stays ON for every other endpoint.
    authentication_classes = [LogoutJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Accept refresh token from body OR from cookie
        refresh_token = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass  # Token already blacklisted or invalid — still log user out
        response = Response({"message": "Logged out successfully"})
        response.delete_cookie("access_token", path="/", samesite="Lax")
        response.delete_cookie("refresh_token", path="/", samesite="Lax")
        return response


class ForgotPasswordView(APIView):
    """Send a password reset email with a one-time token."""
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Anti-enumeration: the response is identical whether or not an account
        # exists (audit Z2-5).
        #
        # This REVERSES an earlier documented product decision that preferred a
        # precise 404 ("No active account found") for clearer UX. That trade is
        # normally arguable — it is not arguable for THIS product. A 404 here is an
        # oracle: anyone can test an address and learn whether that person has a
        # FixitLab account, which on an interview-practice platform reveals that a
        # named individual is preparing for interviews. A colleague or employer can
        # run that check, and the answer could cost someone their current job. The
        # usual enumeration risk is credential-stuffing; here the leak is the fact of
        # membership itself.
        #
        # The UX cost is kept small: the copy below still tells a user who typo'd
        # their address what to do, without confirming anything.
        # One response object shape for every outcome below, including the mail
        # failure — a distinct 5xx would restore the oracle, since only a real
        # account can reach the sending code at all.
        def generic_response():
            return Response({
                "message": (
                    "If an account exists for that address, a password reset link is "
                    "on its way. If nothing arrives in a few minutes, check the "
                    "address or sign up."
                )
            })

        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.is_active:
            logger.info("Password reset requested for unknown/inactive email: %s", email)
            return generic_response()

        PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
        token_obj, raw_token = PasswordResetToken.generate_token(user, hours=1)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        try:
            dispatch_notification_email(
                subject="Reset your FixitLab password",
                to_email=user.email,
                template="emails/password_reset.html",
                context={"username": user.username, "reset_url": reset_url, "expires_hours": 1},
                critical=True,
            )
        except Exception as mail_err:
            # Deliberately NOT surfaced to the caller: the old 502 read "Your account
            # was found, but the reset email could not be sent" — only an existing
            # account can reach this line, so the error itself confirmed membership.
            # Delivery is a daemon thread (see dispatch_notification_email), so this
            # branch means the send could not even be started; ops needs the log, the
            # caller retries.
            logger.error(f"Password reset email failed for {email}: {mail_err}")
            return generic_response()

        logger.info(f"Password reset email dispatched for {email}")
        return generic_response()


def _blacklist_all_refresh_tokens(user):
    """Blacklist every outstanding refresh token for ``user`` (DB-backed).

    Used on password reset (SECURITY_AUDIT A-02) for a hard, durable revocation
    that does not depend on the volatile session cache. Best-effort: a failure
    here is logged but never 500s the reset (the SessionTracker invalidation +
    the user's now-changed password already block credential reuse).
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
    except Exception:  # token_blacklist app not installed
        return
    try:
        outstanding = OutstandingToken.objects.filter(user=user)
        for ot in outstanding:
            BlacklistedToken.objects.get_or_create(token=ot)
    except Exception:
        logger.warning("Failed to blacklist refresh tokens for user %s", getattr(user, "id", "?"))


class ResetPasswordView(APIView):
    """Reset password using a token from the reset email."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        token_obj = PasswordResetToken.verify_token(raw_token)
        if not token_obj:
            return Response(
                {"error": "Invalid or expired reset link. Please request a new one."},
                status=400,
            )

        # Reset the password
        user = token_obj.user
        user.set_password(new_password)
        user.save()

        # Mark token as used
        token_obj.used = True
        token_obj.save(update_fields=["used"])

        # SECURITY_AUDIT A-02: a password reset is the "I may be compromised"
        # recovery action — it MUST evict any attacker who already holds a live
        # session. Mirror ChangePasswordView: drop all tracked JWT sessions so
        # any access token fails the session check on its next request, AND
        # hard-blacklist every outstanding refresh token (DB-backed) so a stolen
        # refresh token can no longer mint new access tokens.
        try:
            SessionTracker.invalidate_all_sessions(user.id)
        except Exception:
            logger.warning("Failed to invalidate sessions after password reset for user %s", user.id)
        _blacklist_all_refresh_tokens(user)

        logger.info(f"Password reset successfully for {user.email}")
        return Response({"message": "Password has been reset successfully. You can now sign in."})


def _register_refreshed_session(request, access_token):
    """Record the rotated access token's jti so session enforcement keeps it valid.

    Decodes the new access token (signature already verified by simplejwt when it
    minted it) to read user_id + jti, then registers it ADDITIVELY in
    SessionTracker. Best-effort: any failure is swallowed so a refresh never 500s
    on a cache hiccup — at worst the user falls back to re-login, never an error.
    """
    try:
        import jwt as _jwt
        jwt_settings = getattr(settings, "SIMPLE_JWT", {})
        algorithm = jwt_settings.get("ALGORITHM", "HS256")
        verify_key = jwt_settings.get("VERIFYING_KEY") or jwt_settings.get("SIGNING_KEY")
        if not verify_key:
            return
        decoded = _jwt.decode(
            access_token, verify_key, algorithms=[algorithm],
            options={"verify_exp": False},
        )
        user_id = decoded.get(jwt_settings.get("USER_ID_CLAIM", "user_id"))
        jti = decoded.get(jwt_settings.get("JTI_CLAIM", "jti"))
        if user_id and jti:
            SessionTracker.record_session(
                user_id, jti,
                ip_address=getattr(request, "client_ip", "") or "",
                user_agent=getattr(request, "user_agent", "") or "",
            )
    except Exception:
        logger.debug("Could not register refreshed session jti", exc_info=True)


class CookieTokenRefreshView(TokenRefreshView):
    """
    Extends simplejwt's TokenRefreshView to:
    1. Fall back to 'refresh_token' cookie when no refresh token in request body.
    2. Set the new access_token (and rotated refresh_token) as httpOnly cookies.
    3. Re-register the rotated jti so session enforcement keeps the token valid.
    """

    # Loose, dedicated throttle (see TokenRefreshThrottle): refresh is per-IP and
    # high-frequency; the tight default anon bucket could 429 a NAT'd group and
    # log them out. Refresh-token validity is the real gate here.
    throttle_classes = [TokenRefreshThrottle]

    def post(self, request, *args, **kwargs):
        # If no refresh token in body, inject it from the cookie
        if not request.data.get("refresh") and request.COOKIES.get("refresh_token"):
            # request.data is immutable QueryDict on DRF — copy it
            data = request.data.copy()
            data["refresh"] = request.COOKIES["refresh_token"]
            request._full_data = data

        try:
            response = super().post(request, *args, **kwargs)
        except User.DoesNotExist:
            # simplejwt's TokenRefreshSerializer resolves the user with a bare
            # `.get()` and does not catch DoesNotExist, so a refresh token for a
            # deleted account raised an unhandled exception → 500 (audit Z6-12).
            #
            # This is reachable in normal use: self-service deletion only
            # blacklists the refresh token when the client passes it in the body,
            # so a deleted user's browser 500s on its next 15-minute refresh
            # instead of logging out cleanly — and files an error report each time.
            logger.info("Refresh attempted for a deleted account")
            return Response(
                {"detail": "Token is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if response.status_code == 200:
            new_access = response.data.get("access")
            new_refresh = response.data.get("refresh")
            if new_access:
                # CRITICAL (session-enforcement fix): simplejwt mints a BRAND-NEW
                # jti for the rotated access token (jti is in no_copy_claims and
                # set_jti() runs on rotation). If we don't re-register it, the very
                # next request made with this freshly-refreshed token fails
                # SessionTracker.is_session_valid and the user is 401'd / logged
                # out — which is exactly what happened sitewide when JWT session
                # enforcement was flipped back on at the end of a deploy. Record
                # the new jti against the user so the rotated token stays valid.
                _register_refreshed_session(request, new_access)
                set_auth_cookies(response, new_access, new_refresh)

        return response


from .oauth_urls import (
    canonical_frontend_url,
    github_authorize_url,
    google_authorize_url,
    oauth_callback_url,
)
from .oauth_state import issue_oauth_state, validate_oauth_state


# ─── Social OAuth ─────────────────────────────────────────────────

class SocialAuthConfigView(APIView):
    """Return OAuth client IDs so the frontend knows whether social login is enabled."""
    permission_classes = [AllowAny]

    def get(self, request):
        base = canonical_frontend_url()
        gh_callback = oauth_callback_url("github")
        google_callback = oauth_callback_url("google")
        gh_client = settings.GITHUB_CLIENT_ID or ""
        return Response({
            "frontend_url": base,
            "oauth_setup_note": (
                f"GitHub OAuth App (client {gh_client[:8]}…): set Authorization callback URL to exactly "
                f"{gh_callback} at https://github.com/settings/developers → OAuth Apps → your app."
            ),
            "github": {
                "enabled": bool(settings.GITHUB_CLIENT_ID),
                "client_id": settings.GITHUB_CLIENT_ID,
                "authorize_url": "https://github.com/login/oauth/authorize",
                "callback_url": gh_callback,
                "login_url": "/api/auth/social/start/github/?intent=login" if settings.GITHUB_CLIENT_ID else "",
                "start_url": "/api/auth/social/start/github/",
                "app_settings_url": "https://github.com/settings/developers",
            },
            "google": {
                "enabled": bool(settings.GOOGLE_CLIENT_ID),
                "client_id": settings.GOOGLE_CLIENT_ID,
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "callback_url": google_callback,
                "login_url": "/api/auth/social/start/google/?intent=login" if settings.GOOGLE_CLIENT_ID else "",
                "start_url": "/api/auth/social/start/google/",
            },
        })


class SocialOAuthStartView(APIView):
    """Redirect browser to GitHub/Google with server-built redirect_uri."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def get(self, request, provider):
        intent = (request.GET.get("intent") or "login").strip()
        if intent not in ("login", "register", "link"):
            intent = "login"
        if provider == "github":
            if not settings.GITHUB_CLIENT_ID:
                return Response({"error": "GitHub login is not configured."}, status=501)
            state = issue_oauth_state(intent)
            return redirect(github_authorize_url(state=state))
        if provider == "google":
            if not settings.GOOGLE_CLIENT_ID:
                return Response({"error": "Google login is not configured."}, status=501)
            state = issue_oauth_state(intent)
            return redirect(google_authorize_url(state=state))
        return Response({"error": "Unknown provider."}, status=400)


class GitHubCallbackView(APIView):
    """Exchange GitHub OAuth code for a user session."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"error": "Authorization code is required."}, status=400)

        oauth_state = (request.data.get("state") or "").strip()
        valid, intent = validate_oauth_state(oauth_state)
        if not valid:
            return Response(
                {"error": "Invalid or expired OAuth state. Please try again."},
                status=400,
            )

        client_id = settings.GITHUB_CLIENT_ID
        client_secret = settings.GITHUB_CLIENT_SECRET
        if not client_id or not client_secret:
            return Response({"error": "GitHub login is not configured on this server."}, status=501)

        import requests as http_requests

        redirect_uri = oauth_callback_url("github")

        # 1. Exchange code for access token
        try:
            token_resp = http_requests.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                err = token_data.get("error_description") or token_data.get("error") or token_data
                logger.warning(f"GitHub OAuth token exchange failed: {token_data}")
                return Response(
                    {"error": f"GitHub authentication failed: {err}"},
                    status=400,
                )
        except Exception as e:
            logger.error(f"GitHub OAuth token exchange error: {e}")
            return Response({"error": "Unable to reach GitHub. Please try again."}, status=502)

        # 2. Get user info
        try:
            user_resp = http_requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=10,
            )
            gh_user = user_resp.json()
            gh_id = str(gh_user.get("id", ""))
            gh_login = gh_user.get("login", "")
            gh_name = gh_user.get("name", "") or gh_login

            # Get primary email
            email_resp = http_requests.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=10,
            )
            emails = email_resp.json()
            primary_email = None
            # SECURITY_AUDIT A-03: track whether the chosen email is verified so
            # an unverified GitHub email cannot auto-link to an existing account.
            primary_email_verified = False
            for em in emails:
                if em.get("primary") and em.get("verified"):
                    primary_email = em["email"]
                    primary_email_verified = True
                    break
            if not primary_email and emails:
                primary_email = emails[0].get("email")
                primary_email_verified = bool(emails[0].get("verified"))
            if not primary_email:
                return Response({"error": "Could not retrieve email from GitHub."}, status=400)
        except Exception as e:
            logger.error(f"GitHub user info error: {e}")
            return Response({"error": "Failed to get user info from GitHub."}, status=502)

        allow_registration = intent == "register"
        user, error = self._resolve_social_login(
            "github", gh_id, primary_email, gh_name,
            allow_registration=allow_registration,
            email_verified=primary_email_verified,
        )
        if error:
            return error

        # ── Second factor also applies to social sign-in (audit Z2-3) ────────
        #
        # This was a real bypass: MFA was enforced on the password path only, so an
        # account with TOTP enabled could be signed into by anyone who compromised
        # the linked GitHub/Google account — defeating the control the user
        # explicitly turned on.
        #
        # The "the IdP already did MFA" argument holds for *enterprise* SSO, where
        # you set the IdP policy. It does not hold for consumer OAuth: we have no
        # way to know whether GitHub or Google asked for a second factor, and a
        # user who enabled MFA here asked for MFA here.
        mfa_device = getattr(user, "mfa_device", None)
        if mfa_device and mfa_device.enabled:
            from .mfa_views import issue_mfa_challenge

            return Response({
                "mfa_required": True,
                "mfa_token": issue_mfa_challenge(user),
                "message": "Enter the 6-digit code from your authenticator app.",
            })

        # Session-aware issuance so the jti is tracked (see RegisterView).
        _toks = TokenHelper.create_tokens_with_session(
            user,
            getattr(request, "client_ip", "") or "",
            getattr(request, "user_agent", "") or "",
        )
        access_token = _toks["access"]
        refresh_token = _toks["refresh"]
        response = Response({
            "access": access_token,
            "refresh": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_staff": user.is_staff,
            },
        })
        set_auth_cookies(response, access_token, refresh_token)
        return response

    @staticmethod
    def _resolve_social_login(provider, provider_uid, email, display_name, *, allow_registration=False, email_verified=True):
        """
        Social auth:
        - Existing social link → login
        - Existing email account → link social + login (ONLY if email verified)
        - No account + allow_registration → create account + link social
        - No account + login intent → require registration first

        SECURITY_AUDIT A-03: ``email_verified`` MUST be True before we trust the
        provider-asserted email to auto-link to (or create) a local account. A
        provider can return an email the user never proved they own (some flows
        let a user set an arbitrary, unverified email); linking on that would let
        an attacker take over the existing FixitLab account that owns that email.
        Callers pass the provider's verified-email flag (GitHub already filters
        to verified primary emails; Google passes ``email_verified``).
        """
        try:
            sa = SocialAccount.objects.select_related("user").get(
                provider=provider, provider_uid=provider_uid,
            )
            return sa.user, None
        except SocialAccount.DoesNotExist:
            pass

        # Beyond this point we either LINK to an existing local account or CREATE
        # one from the provider email. Both require a provider-verified email.
        if not email_verified:
            return None, Response(
                {
                    "error": (
                        f"Your {provider.title()} email is not verified. "
                        "Verify it with the provider, then try again."
                    ),
                    "error_code": "email_not_verified",
                },
                status=403,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            if not allow_registration:
                return None, Response(
                    {
                        "error": (
                            "No FixitLab account found for this email. "
                            "Please register first, then sign in with GitHub or Google."
                        ),
                        "error_code": "registration_required",
                        "email": email,
                        "provider": provider,
                    },
                    status=403,
                )
            import secrets
            from django.utils.text import slugify

            base = slugify(email.split("@")[0])[:24] or "user"
            username = base
            n = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{n}"
                n += 1
            user = User.objects.create_user(
                username=username,
                email=email,
                password=secrets.token_urlsafe(32),
            )
            parts = (display_name or "").split(None, 1)
            user.first_name = parts[0] if parts else ""
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])
            Profile.objects.get_or_create(user=user)
            SocialAccount.objects.create(
                user=user,
                provider=provider,
                provider_uid=provider_uid,
                extra_data={"display_name": display_name},
            )
            return user, None

        SocialAccount.objects.create(
            user=user,
            provider=provider,
            provider_uid=provider_uid,
            extra_data={"display_name": display_name},
        )
        return user, None


class GoogleCallbackView(APIView):
    """Exchange Google OAuth code for a user session."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"error": "Authorization code is required."}, status=400)

        oauth_state = (request.data.get("state") or "").strip()
        valid, intent = validate_oauth_state(oauth_state)
        if not valid:
            return Response(
                {"error": "Invalid or expired OAuth state. Please try again."},
                status=400,
            )

        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        if not client_id or not client_secret:
            return Response({"error": "Google login is not configured on this server."}, status=501)

        import requests as http_requests
        redirect_uri = oauth_callback_url("google")

        # 1. Exchange code for tokens
        try:
            token_resp = http_requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=15,
            )
            token_data = token_resp.json()
            id_token_str = token_data.get("id_token")
            access_token = token_data.get("access_token")
            if not access_token:
                err = token_data.get("error_description") or token_data.get("error") or "unknown error"
                logger.warning(f"Google OAuth token exchange failed: {token_data}")
                return Response({"error": f"Google authentication failed: {err}"}, status=400)
        except Exception as e:
            logger.error(f"Google OAuth token exchange error: {e}")
            return Response({"error": "Unable to reach Google. Please try again."}, status=502)

        # 2. Get user info from id_token or userinfo endpoint
        try:
            userinfo_resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            ginfo = userinfo_resp.json()
            google_id = ginfo.get("sub", "")
            email = ginfo.get("email", "")
            name = ginfo.get("name", "")
            # SECURITY_AUDIT A-03: Google returns email_verified (bool, or "true"
            # as a string from some endpoints). Normalise both forms.
            raw_verified = ginfo.get("email_verified", False)
            email_verified = raw_verified is True or str(raw_verified).lower() == "true"
            if not email:
                return Response({"error": "Could not retrieve email from Google."}, status=400)
        except Exception as e:
            logger.error(f"Google userinfo error: {e}")
            return Response({"error": "Failed to get user info from Google."}, status=502)

        allow_registration = intent == "register"
        user, error = GitHubCallbackView._resolve_social_login(
            "google", google_id, email, name,
            allow_registration=allow_registration,
            email_verified=email_verified,
        )
        if error:
            return error

        # ── Second factor also applies to social sign-in (audit Z2-3) ────────
        #
        # This was a real bypass: MFA was enforced on the password path only, so an
        # account with TOTP enabled could be signed into by anyone who compromised
        # the linked GitHub/Google account — defeating the control the user
        # explicitly turned on.
        #
        # The "the IdP already did MFA" argument holds for *enterprise* SSO, where
        # you set the IdP policy. It does not hold for consumer OAuth: we have no
        # way to know whether GitHub or Google asked for a second factor, and a
        # user who enabled MFA here asked for MFA here.
        mfa_device = getattr(user, "mfa_device", None)
        if mfa_device and mfa_device.enabled:
            from .mfa_views import issue_mfa_challenge

            return Response({
                "mfa_required": True,
                "mfa_token": issue_mfa_challenge(user),
                "message": "Enter the 6-digit code from your authenticator app.",
            })

        # Session-aware issuance so the jti is tracked (see RegisterView).
        _toks = TokenHelper.create_tokens_with_session(
            user,
            getattr(request, "client_ip", "") or "",
            getattr(request, "user_agent", "") or "",
        )
        access_token = _toks["access"]
        refresh_token = _toks["refresh"]
        response = Response({
            "access": access_token,
            "refresh": refresh_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_staff": user.is_staff,
            },
        })
        set_auth_cookies(response, access_token, refresh_token)
        return response


def _link_social_account(user, provider: str, provider_uid: str, display_name: str = ""):
    """Link OAuth provider to an authenticated user."""
    conflict = SocialAccount.objects.filter(provider=provider, provider_uid=provider_uid).exclude(user=user).first()
    if conflict:
        return Response(
            {"error": f"This {provider.title()} account is already linked to another FixitLab user."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    existing = SocialAccount.objects.filter(user=user, provider=provider).first()
    if existing and existing.provider_uid != provider_uid:
        return Response(
            {"error": f"You already linked a different {provider.title()} account."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    SocialAccount.objects.update_or_create(
        provider=provider,
        provider_uid=provider_uid,
        defaults={"user": user, "extra_data": {"display_name": display_name}},
    )
    return None


class GitHubLinkView(APIView):
    """Link GitHub to the currently authenticated user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"error": "Authorization code is required."}, status=400)

        oauth_state = (request.data.get("state") or "").strip()
        valid, intent = validate_oauth_state(oauth_state)
        if not valid or intent != "link":
            return Response(
                {"error": "Invalid or expired OAuth state. Please try again."},
                status=400,
            )

        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            return Response({"error": "GitHub login is not configured."}, status=501)

        import requests as http_requests
        redirect_uri = oauth_callback_url("github")
        try:
            token_resp = http_requests.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return Response({"error": "GitHub authentication failed."}, status=400)
            gh_user = http_requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=10,
            ).json()
            gh_id = str(gh_user.get("id", ""))
            gh_name = gh_user.get("name", "") or gh_user.get("login", "")
        except Exception as exc:
            logger.error("GitHub link error: %s", exc)
            return Response({"error": "Unable to reach GitHub."}, status=502)

        err = _link_social_account(request.user, "github", gh_id, gh_name)
        if err:
            return err
        return Response({"linked": True, "provider": "github"})


class GoogleLinkView(APIView):
    """Link Google to the currently authenticated user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "").strip()
        if not code:
            return Response({"error": "Authorization code is required."}, status=400)

        oauth_state = (request.data.get("state") or "").strip()
        valid, intent = validate_oauth_state(oauth_state)
        if not valid or intent != "link":
            return Response(
                {"error": "Invalid or expired OAuth state. Please try again."},
                status=400,
            )

        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            return Response({"error": "Google login is not configured."}, status=501)

        import requests as http_requests
        redirect_uri = oauth_callback_url("google")
        try:
            token_resp = http_requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=15,
            )
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return Response({"error": "Google authentication failed."}, status=400)
            ginfo = http_requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            ).json()
            google_id = str(ginfo.get("sub", ""))
            name = ginfo.get("name", "")
        except Exception as exc:
            logger.error("Google link error: %s", exc)
            return Response({"error": "Unable to reach Google."}, status=502)

        err = _link_social_account(request.user, "google", google_id, name)
        if err:
            return err
        return Response({"linked": True, "provider": "google"})


class LabHistoryView(APIView):
    """Return the user's lab session history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.labs.models import LabSession
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 20)), 100)
        start = (page - 1) * page_size
        end = start + page_size

        qs = (
            LabSession.objects.filter(user=request.user)
            .select_related("scenario")
            .order_by("-started_at")
        )
        total = qs.count()
        sessions = qs[start:end]

        data = []
        for s in sessions:
            data.append({
                "id": str(s.id),
                "scenario": s.scenario.title if s.scenario else "Unknown",
                "scenario_slug": s.scenario.slug if s.scenario else "",
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "passed": s.validation_passed,
                "provider": s.provider,
                "score": s.score,
                "hints_used": s.hints_used,
            })
        return Response({
            "history": data,
            "count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        })


class SearchView(APIView):
    """Search scenarios by keyword."""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.question_bank.models import Scenario
        q = request.query_params.get("q", "").strip()
        if not q or len(q) < 2:
            return Response({"results": []})
        from django.db.models import Q
        results = Scenario.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(slug__icontains=q),
            is_active=True,
        )[:20]
        data = []
        for s in results:
            data.append({
                "id": s.id,
                "title": s.title,
                "slug": s.slug,
                "difficulty": s.difficulty,
            })
        return Response({"results": data, "query": q})


class AcceptLegalTermsView(APIView):
    """Record acceptance of the *current* terms and privacy policy (audit Z4-8).

    Without this, bumping `LEGAL_TERMS_VERSION` would set
    `needs_legal_reacceptance` for everyone with no way to clear it — the version
    field would become a permanent nag rather than a record.

    Takes no version from the caller. The client cannot be the authority on which
    text it displayed, and accepting a version string supplied by the client would
    let an account claim agreement to a document that was never shown.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.terms_accepted_at = timezone.now()
        profile.terms_version = settings.LEGAL_TERMS_VERSION
        profile.privacy_version = settings.LEGAL_PRIVACY_VERSION
        profile.save(
            update_fields=["terms_accepted_at", "terms_version", "privacy_version"]
        )
        logger.info(
            "Legal acceptance recorded for user %s (terms %s, privacy %s)",
            request.user.id, profile.terms_version, profile.privacy_version,
        )
        return Response({
            "terms_version": profile.terms_version,
            "privacy_version": profile.privacy_version,
            "accepted_at": profile.terms_accepted_at.isoformat(),
            "needs_legal_reacceptance": False,
        })


class ContactView(APIView):
    """Handle contact form submissions."""
    permission_classes = [AllowAny]
    # Unthrottled, this was a remote way to take login out (audit Z2-6). Each POST
    # writes a row AND queues mail to SUPPORT_EMAIL via send_notification_email
    # directly — bypassing the daily-quota gate in queue_user_email — so a loop burns
    # the shared ~500/day Gmail allowance including the reserve held for OTP and
    # password reset. `strict_anon` (240/min) is far too loose for something that
    # sends email; `contact` is 5/hour.
    throttle_classes = [ContactRateThrottle]

    def post(self, request):
        from .models import ContactMessage
        from django.utils.html import strip_tags
        name = strip_tags(request.data.get("name", "").strip())
        email = request.data.get("email", "").strip()
        subject = strip_tags(request.data.get("subject", "").strip())
        message = strip_tags(request.data.get("message", "").strip())

        if not all([name, email, subject, message]):
            return Response(
                {"error": "All fields are required."},
                status=400,
            )
        if len(message) > 5000:
            return Response(
                {"error": "Message too long (max 5000 characters)."},
                status=400,
            )

        ContactMessage.objects.create(
            name=name, email=email, subject=subject, message=message
        )

        # Notify admin via email
        try:
            from apps.notifications.tasks import send_notification_email
            from django.conf import settings
            send_notification_email.delay(
                subject=f"[FixitLab Contact] {subject}",
                to_email=settings.SUPPORT_EMAIL,
                template="emails/contact_notification.html",
                context={
                    "name": name,
                    "email": email,
                    "subject": subject,
                    "message": message,
                },
            )
        except Exception:
            pass  # Don't fail on notification error

        return Response({"message": "Message sent successfully. We'll get back to you within 24 hours."})



class ExportMyDataView(APIView):
    """GDPR Art.15 / DPDP §11 — download everything we hold for this account.

    The only export used to be interview transcripts (audit Z4-12), so a subject
    access request could be answered with one convenient subset while the profile,
    lab history, billing, community posts, certificates and preferences went
    unmentioned.

    Throttled with the OTP-grade limiter rather than the generic one: assembling this
    walks most of a user's rows, so it is the sort of endpoint that becomes a cheap
    self-inflicted DoS if it is free to call in a loop.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [OTPRateThrottle]

    def get(self, request):
        from apps.accounts.data_export import build_account_export

        payload = build_account_export(request.user)
        if request.query_params.get("download") == "1":
            import json

            response = HttpResponse(
                json.dumps(payload, indent=2, default=str),
                content_type="application/json",
            )
            stamp = timezone.now().strftime("%Y%m%d")
            response["Content-Disposition"] = (
                f'attachment; filename="fixitlab-my-data-{stamp}.json"'
            )
            return response
        return Response(payload)
