"""
Accounts admin — User, Profile, Organization, ContactMessage, and supporting models.
"""
import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    AccountLifecycleEvent,
    ContactMessage,
    EmailVerificationOTP,
    Organization,
    OrganizationMember,
    OrganizationTechnologyGrant,
    PendingOrgInvite,
    Profile,
)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class ComplimentaryAccessFilter(admin.SimpleListFilter):
    title = "complimentary access"
    parameter_name = "comp_access"

    def lookups(self, request, model_admin):
        return [("yes", "Has complimentary access"), ("no", "Standard access")]

    def queryset(self, qs, value):
        if value == "yes":
            return qs.filter(profile__complimentary_access=True)
        if value == "no":
            return qs.filter(profile__complimentary_access=False)
        return qs


class InactiveDaysFilter(admin.SimpleListFilter):
    title = "inactivity"
    parameter_name = "inactive"

    def lookups(self, request, model_admin):
        return [
            ("30", "Inactive 30+ days"),
            ("60", "Inactive 60+ days"),
            ("90", "Inactive 90+ days"),
        ]

    def queryset(self, qs, value):
        if value:
            cutoff = timezone.now() - timedelta(days=int(value))
            return qs.filter(last_login__lt=cutoff)
        return qs


class CurrencyFilter(admin.SimpleListFilter):
    title = "currency preference"
    parameter_name = "currency"

    def lookups(self, request, model_admin):
        return [("INR", "INR"), ("USD", "USD")]

    def queryset(self, qs, value):
        if value:
            return qs.filter(profile__currency_preference=value)
        return qs


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = (
        "phone_number",
        "country",
        "currency_preference",
        "complimentary_access",
        "support_bot_enabled",
    )


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMember
    fields = ("organization", "role", "joined_at")
    readonly_fields = ("organization", "joined_at")
    extra = 0
    can_delete = False
    verbose_name_plural = "Organization memberships"


# ---------------------------------------------------------------------------
# Custom User Admin
# ---------------------------------------------------------------------------

admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline, OrganizationMembershipInline)
    list_display = (
        "username",
        "email",
        "full_name",
        "is_staff",
        "is_active",
        "complimentary_badge",
        "country_display",
        "date_joined",
        "last_login",
        "lab_count",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        ComplimentaryAccessFilter,
        CurrencyFilter,
        InactiveDaysFilter,
        ("date_joined", admin.DateFieldListFilter),
        ("last_login", admin.DateFieldListFilter),
    )
    search_fields = ("username", "email", "first_name", "last_name", "profile__phone_number")
    list_select_related = ("profile",)
    date_hierarchy = "date_joined"
    list_per_page = 50
    actions = [
        "action_grant_complimentary",
        "action_revoke_complimentary",
        "action_deactivate",
        "action_activate",
        "action_make_staff",
        "action_remove_staff",
        "action_export_csv",
    ]

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Comp. access", boolean=True)
    def complimentary_badge(self, obj):
        return getattr(getattr(obj, "profile", None), "complimentary_access", False)

    @admin.display(description="Country")
    def country_display(self, obj):
        return getattr(getattr(obj, "profile", None), "country", "") or "—"

    @admin.display(description="Labs")
    def lab_count(self, obj):
        return obj.lab_sessions.count()

    # ---- actions ----

    @admin.action(description="Grant complimentary access to selected users")
    def action_grant_complimentary(self, request, queryset):
        count = Profile.objects.filter(user__in=queryset).update(complimentary_access=True)
        self.message_user(request, f"Granted complimentary access to {count} user(s).", messages.SUCCESS)

    @admin.action(description="Revoke complimentary access from selected users")
    def action_revoke_complimentary(self, request, queryset):
        count = Profile.objects.filter(user__in=queryset).update(complimentary_access=False)
        self.message_user(request, f"Revoked complimentary access from {count} user(s).", messages.WARNING)

    @admin.action(description="Deactivate selected users")
    def action_deactivate(self, request, queryset):
        protected = queryset.filter(is_superuser=True)
        if protected.exists():
            self.message_user(request, "Superusers cannot be deactivated.", messages.ERROR)
            return
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} user(s).", messages.WARNING)

    @admin.action(description="Activate selected users")
    def action_activate(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} user(s).", messages.SUCCESS)

    @admin.action(description="Grant staff status to selected users")
    def action_make_staff(self, request, queryset):
        count = queryset.update(is_staff=True)
        self.message_user(request, f"Granted staff to {count} user(s).", messages.SUCCESS)

    @admin.action(description="Remove staff status from selected users")
    def action_remove_staff(self, request, queryset):
        count = queryset.exclude(is_superuser=True).update(is_staff=False)
        self.message_user(request, f"Removed staff from {count} user(s).", messages.WARNING)

    @admin.action(description="Export selected users to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="users.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "id", "username", "email", "first_name", "last_name",
            "is_active", "is_staff", "date_joined", "last_login",
            "country", "currency", "complimentary_access",
        ])
        for u in queryset.select_related("profile"):
            p = getattr(u, "profile", None)
            writer.writerow([
                u.id, u.username, u.email, u.first_name, u.last_name,
                u.is_active, u.is_staff,
                u.date_joined.isoformat() if u.date_joined else "",
                u.last_login.isoformat() if u.last_login else "",
                getattr(p, "country", ""),
                getattr(p, "currency_preference", ""),
                getattr(p, "complimentary_access", False),
            ])
        return response


# ---------------------------------------------------------------------------
# Organization admin
# ---------------------------------------------------------------------------

class OrganizationMemberInline(admin.TabularInline):
    model = OrganizationMember
    fields = ("user", "role", "invited_email", "joined_at")
    readonly_fields = ("joined_at",)
    extra = 1
    autocomplete_fields = ("user",)


class OrganizationTechnologyGrantInline(admin.TabularInline):
    model = OrganizationTechnologyGrant
    fields = ("technology", "is_active", "expires_at", "created_at")
    readonly_fields = ("created_at",)
    extra = 1


class PendingOrgInviteInline(admin.TabularInline):
    model = PendingOrgInvite
    fields = ("email", "role", "invited_by", "expires_at", "accepted_at")
    readonly_fields = ("token", "expires_at", "accepted_at")
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "owner",
        "seat_limit",
        "member_count",
        "tech_grant_count",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "slug", "owner__username", "billing_email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [OrganizationMemberInline, OrganizationTechnologyGrantInline, PendingOrgInviteInline]
    list_select_related = ("owner",)
    actions = ["action_deactivate", "action_activate"]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()

    @admin.display(description="Tech grants")
    def tech_grant_count(self, obj):
        return obj.technology_grants.filter(is_active=True).count()

    @admin.action(description="Deactivate selected organizations")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Organizations deactivated.", messages.WARNING)

    @admin.action(description="Activate selected organizations")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Organizations activated.", messages.SUCCESS)


# ---------------------------------------------------------------------------
# Contact messages
# ---------------------------------------------------------------------------

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "is_read", "created_at")
    list_filter = ("is_read", ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("id", "name", "email", "subject", "message", "created_at")
    date_hierarchy = "created_at"
    actions = ["mark_read", "mark_unread"]

    @admin.action(description="Mark as read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark as unread")
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

@admin.register(EmailVerificationOTP)
class EmailVerificationOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "verified", "attempts", "created_at", "expires_at")
    list_filter = ("verified",)
    search_fields = ("email",)
    readonly_fields = ("id", "email", "code", "session_token", "created_at", "expires_at", "attempts", "verified")
    date_hierarchy = "created_at"


@admin.register(AccountLifecycleEvent)
class AccountLifecycleEventAdmin(admin.ModelAdmin):
    list_display = ("email", "event_type", "user", "created_at")
    list_filter = ("event_type", ("created_at", admin.DateFieldListFilter))
    search_fields = ("email", "user__username")
    readonly_fields = ("user", "email", "event_type", "metadata", "created_at")
    date_hierarchy = "created_at"
