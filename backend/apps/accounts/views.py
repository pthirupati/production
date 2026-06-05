import logging
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import (
    RegisterSerializer, LoginSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
)
from .models import Profile, PasswordResetToken, EmailVerificationOTP, SocialAccount
from apps.notifications.tasks import send_notification_email, create_in_app_notification
from common.security import SessionTracker, TokenHelper
from common.logging_utils import get_structured_logger

User = get_user_model()
logger = logging.getLogger(__name__)
structured_logger = get_structured_logger(__name__)



class AuthRateThrottle(AnonRateThrottle):
    """Strict rate limiting for auth endpoints to prevent brute-force."""
    rate = '20/minute'


class SendOTPView(APIView):
    """Send a 6-digit OTP to an email for verification during registration."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

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
            return Response({"error": "Email already registered."}, status=400)

        try:
            otp_obj, code, session_token = EmailVerificationOTP.generate(email, minutes=10)

            send_notification_email.delay(
                subject="FixitLab - Verify Your Email",
                to_email=email,
                template="emails/otp_verification.html",
                context={
                    "otp_code": code,
                    "expires_minutes": 10,
                },
            )
            logger.info(f"OTP sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send OTP to {email}: {e}")
            return Response(
                {"error": "Failed to send verification code. Please try again."},
                status=500,
            )

        return Response({
            "message": "Verification code sent to your email.",
            "session_token": session_token,
        })


class VerifyOTPView(APIView):
    """Verify the 6-digit OTP code."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        session_token = request.data.get("session_token", "")
        code = request.data.get("code", "").strip()

        if not session_token or not code:
            return Response({"error": "Session token and code are required."}, status=400)

        otp_obj, error = EmailVerificationOTP.verify(session_token, code)
        if error:
            return Response({"error": error}, status=400)

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

        # Check OTP hasn't expired (allow register within 30 min of verification)
        if otp_obj.is_expired:
            return Response(
                {"error": "Verification has expired. Please verify your email again."},
                status=400,
            )

        # Force the email from the verified OTP
        data = request.data.copy()
        data["email"] = otp_obj.email

        serializer = RegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

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

        # Return tokens immediately so user is logged in
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "User registered successfully",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
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


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        # Look up user by email, then authenticate by username
        user_obj = User.objects.filter(email=email).first()
        if not user_obj:
            structured_logger.warning(
                "Login attempt with non-existent email",
                email=email,
                ip=request.client_ip if hasattr(request, 'client_ip') else '',
                tags=["auth", "security"]
            )
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
        
        return Response({
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
        })


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = Profile.objects.filter(user=user).first()
        return Response({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": profile.phone_number if profile else None,
            "country": profile.country if profile else "",
            "is_staff": user.is_staff,
            "date_joined": user.date_joined.isoformat(),
        })

    def put(self, request):
        user = request.user
        username = request.data.get("username", user.username)
        phone_number = request.data.get("phone_number")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")

        # Validate username uniqueness
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

        # Update profile fields
        profile, _ = Profile.objects.get_or_create(user=user)
        if phone_number is not None:
            profile.phone_number = phone_number or None
        country = request.data.get("country")
        if country is not None:
            profile.country = country
        profile.save()

        return Response({
            "message": "Profile updated",
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": profile.phone_number,
            "country": profile.country,
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

        if len(new_password) < 8:
            return Response({"error": "Password must be at least 8 characters"}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully"})


class LogoutView(APIView):
    """Blacklist the refresh token so it can no longer be used."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token required"}, status=400)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass  # Token already blacklisted or invalid — still log user out
        return Response({"message": "Logged out successfully"})


class ForgotPasswordView(APIView):
    """Send a password reset email with a one-time token."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Always return 200 to prevent email enumeration.
        # Only actually send the email if the account exists and is active.
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                # Invalidate any existing tokens for this user
                PasswordResetToken.objects.filter(user=user, used=False).update(used=True)

                # Generate new token
                token_obj, raw_token = PasswordResetToken.generate_token(user, hours=1)

                # Send reset email
                reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
                send_notification_email.delay(
                    subject="Reset your FixitLab password",
                    to_email=user.email,
                    template="emails/password_reset.html",
                    context={
                        "username": user.username,
                        "reset_url": reset_url,
                        "expires_hours": 1,
                    },
                )
                logger.info(f"Password reset email sent to {email}")
        except User.DoesNotExist:
            logger.info(f"Password reset requested for nonexistent email: {email}")
        except Exception as e:
            logger.error(f"Password reset email failed: {e}")

        return Response({
            "message": "If an account exists with this email, a password reset link has been sent.",
        })


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
        token_obj.save()

        logger.info(f"Password reset successfully for {user.email}")
        return Response({"message": "Password has been reset successfully. You can now sign in."})


# ─── Social OAuth ─────────────────────────────────────────────────

class SocialAuthConfigView(APIView):
    """Return OAuth client IDs so the frontend knows whether social login is enabled."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "github": {
                "enabled": bool(settings.GITHUB_CLIENT_ID),
                "client_id": settings.GITHUB_CLIENT_ID,
                "authorize_url": "https://github.com/login/oauth/authorize",
            },
            "google": {
                "enabled": bool(settings.GOOGLE_CLIENT_ID),
                "client_id": settings.GOOGLE_CLIENT_ID,
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            },
        })


class GitHubCallbackView(APIView):
    """Exchange GitHub OAuth code for a user session."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        code = request.data.get("code", "").strip()
        redirect_uri = request.data.get("redirect_uri", "").strip()
        if not code:
            return Response({"error": "Authorization code is required."}, status=400)

        client_id = settings.GITHUB_CLIENT_ID
        client_secret = settings.GITHUB_CLIENT_SECRET
        if not client_id or not client_secret:
            return Response({"error": "GitHub login is not configured on this server."}, status=501)

        import requests as http_requests

        if not redirect_uri:
            redirect_uri = f"{settings.FRONTEND_URL}/auth/callback/github"

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
            for em in emails:
                if em.get("primary") and em.get("verified"):
                    primary_email = em["email"]
                    break
            if not primary_email and emails:
                primary_email = emails[0].get("email")
            if not primary_email:
                return Response({"error": "Could not retrieve email from GitHub."}, status=400)
        except Exception as e:
            logger.error(f"GitHub user info error: {e}")
            return Response({"error": "Failed to get user info from GitHub."}, status=502)

        # 3. Find or create user
        user = self._get_or_create_user("github", gh_id, primary_email, gh_name)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_staff": user.is_staff,
            },
        })

    @staticmethod
    def _get_or_create_user(provider, provider_uid, email, display_name):
        """Link social account to existing user or create new one."""
        # Check if this social account already exists
        try:
            sa = SocialAccount.objects.select_related("user").get(
                provider=provider, provider_uid=provider_uid,
            )
            return sa.user
        except SocialAccount.DoesNotExist:
            pass

        # Check if a user with this email already exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Create new user
            username = email.split("@")[0]
            # Ensure username uniqueness
            base = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            user = User.objects.create_user(
                username=username, email=email,
                password=None,  # No password for social accounts
            )
            Profile.objects.get_or_create(user=user)
            # Send welcome notification
            try:
                create_in_app_notification.delay(
                    user_id=user.id,
                    notification_type="welcome",
                    title="Welcome to FixitLab!",
                    message=f"You signed in with {provider.title()}. Start with an easy challenge!",
                    metadata={"action_url": "/technologies"},
                )
            except Exception:
                pass

        # Link the social account
        SocialAccount.objects.create(
            user=user, provider=provider, provider_uid=provider_uid,
            extra_data={"display_name": display_name},
        )
        return user


class GoogleCallbackView(APIView):
    """Exchange Google OAuth code for a user session."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        code = request.data.get("code", "").strip()
        redirect_uri = request.data.get("redirect_uri", "").strip()
        if not code:
            return Response({"error": "Authorization code is required."}, status=400)

        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        if not client_id or not client_secret:
            return Response({"error": "Google login is not configured on this server."}, status=501)

        import requests as http_requests

        # 1. Exchange code for tokens
        try:
            token_resp = http_requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri or f"{settings.FRONTEND_URL}/auth/callback/google",
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
            if not email:
                return Response({"error": "Could not retrieve email from Google."}, status=400)
        except Exception as e:
            logger.error(f"Google userinfo error: {e}")
            return Response({"error": "Failed to get user info from Google."}, status=502)

        # 3. Find or create user (reuse GitHub helper)
        user = GitHubCallbackView._get_or_create_user("google", google_id, email, name)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_staff": user.is_staff,
            },
        })


class LabHistoryView(APIView):
    """Return the user's lab session history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.labs.models import LabSession
        sessions = (
            LabSession.objects.filter(user=request.user)
            .select_related("scenario")
            .order_by("-started_at")[:50]
        )
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
        return Response({"history": data})


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


class ContactView(APIView):
    """Handle contact form submissions."""
    permission_classes = [AllowAny]

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

