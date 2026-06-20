"""
Billing admin — Plan, Subscription, TechnologySubscription, PaymentTransaction,
SubscriptionInvoice, CouponCode, UserCertificate.
"""
import csv
from decimal import Decimal

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CouponCode,
    PaymentTransaction,
    Plan,
    SalesInquiry,
    Subscription,
    SubscriptionInvoice,
    TechnologySubscription,
    UserCertificate,
)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class PaymentStatusFilter(admin.SimpleListFilter):
    title = "payment status"
    parameter_name = "pay_status"

    def lookups(self, request, model_admin):
        return PaymentTransaction.PAYMENT_STATUS

    def queryset(self, qs, value):
        if value:
            return qs.filter(status=value)
        return qs


class ExpiredCouponFilter(admin.SimpleListFilter):
    title = "coupon validity"
    parameter_name = "coupon_valid"

    def lookups(self, request, model_admin):
        return [("valid", "Currently valid"), ("expired", "Expired / used up")]

    def queryset(self, qs, value):
        now = timezone.now()
        if value == "valid":
            return qs.filter(is_active=True).filter(
                models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=now)
            )
        if value == "expired":
            return qs.filter(
                models.Q(is_active=False) | models.Q(valid_until__lt=now)
            )
        return qs


class ExpiredCertFilter(admin.SimpleListFilter):
    title = "certificate status"
    parameter_name = "cert_status"

    def lookups(self, request, model_admin):
        return [("valid", "Valid"), ("expired", "Expired")]

    def queryset(self, qs, value):
        now = timezone.now()
        if value == "valid":
            return qs.filter(expires_at__gt=now)
        if value == "expired":
            return qs.filter(expires_at__lte=now)
        return qs


# ---------------------------------------------------------------------------
# Plan admin
# ---------------------------------------------------------------------------

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price", "max_labs_per_day", "max_lab_duration_minutes", "is_active")
    list_filter = ("is_active", "code")
    search_fields = ("name", "code")
    readonly_fields = ("code",)


# ---------------------------------------------------------------------------
# Subscription admin (global plan subscriptions)
# ---------------------------------------------------------------------------

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "is_active", "started_at", "expires_at")
    list_filter = ("is_active", "plan")
    search_fields = ("user__username", "user__email", "stripe_subscription_id")
    readonly_fields = ("started_at",)
    list_select_related = ("user", "plan")
    date_hierarchy = "started_at"
    actions = ["action_deactivate", "action_activate"]

    @admin.action(description="Deactivate selected subscriptions")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Subscriptions deactivated.", messages.WARNING)

    @admin.action(description="Activate selected subscriptions")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Subscriptions activated.", messages.SUCCESS)


# ---------------------------------------------------------------------------
# Technology Subscription admin
# ---------------------------------------------------------------------------

class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    fields = ("amount", "currency", "payment_method", "status", "created_at")
    readonly_fields = ("amount", "currency", "payment_method", "status", "created_at")
    extra = 0
    can_delete = False
    ordering = ("-created_at",)


@admin.register(TechnologySubscription)
class TechnologySubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "subscription_id",
        "user",
        "technology",
        "amount_display",
        "payment_method",
        "is_active",
        "payment_verified",
        "created_at",
        "expires_at",
    )
    list_filter = (
        "is_active",
        "payment_verified",
        "payment_method",
        ("created_at", admin.DateFieldListFilter),
        ("expires_at", admin.DateFieldListFilter),
    )
    search_fields = ("subscription_id", "user__username", "user__email", "technology__name")
    readonly_fields = ("id", "subscription_id", "created_at")
    list_select_related = ("user", "technology")
    date_hierarchy = "created_at"
    inlines = [PaymentTransactionInline]
    actions = ["action_deactivate", "action_activate", "action_export_csv"]

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return f"₹{obj.amount}"

    @admin.action(description="Deactivate selected subscriptions")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Technology subscriptions deactivated.", messages.WARNING)

    @admin.action(description="Activate selected subscriptions")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Technology subscriptions activated.", messages.SUCCESS)

    @admin.action(description="Export selected subscriptions to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="tech_subscriptions.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "subscription_id", "user", "email", "technology",
            "amount", "payment_method", "is_active", "payment_verified",
            "created_at", "expires_at",
        ])
        for s in queryset.select_related("user", "technology"):
            writer.writerow([
                s.subscription_id, s.user.username, s.user.email,
                s.technology.name, s.amount, s.payment_method,
                s.is_active, s.payment_verified,
                s.created_at.isoformat() if s.created_at else "",
                s.expires_at.isoformat() if s.expires_at else "",
            ])
        return response


# ---------------------------------------------------------------------------
# Payment transaction admin
# ---------------------------------------------------------------------------

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount_display",
        "currency",
        "payment_method",
        "status_badge",
        "gateway_payment_id_short",
        "created_at",
        "verified_at",
    )
    list_filter = (
        PaymentStatusFilter,
        "payment_method",
        "currency",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__email",
        "gateway_order_id",
        "gateway_payment_id",
        "idempotency_key",
    )
    readonly_fields = (
        "id", "user", "amount", "currency", "payment_method",
        "status", "idempotency_key",
        "gateway_order_id", "gateway_payment_id", "gateway_response",
        "tech_subscription", "plan",
        "created_at", "updated_at", "verified_at", "error_message",
    )
    list_select_related = ("user",)
    date_hierarchy = "created_at"
    list_per_page = 50
    actions = ["action_export_csv"]

    @admin.display(description="Amount")
    def amount_display(self, obj):
        symbol = "₹" if obj.currency == "INR" else "$"
        return f"{symbol}{obj.amount}"

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "success": "green",
            "failed": "red",
            "pending": "orange",
            "processing": "blue",
            "cancelled": "grey",
            "refunded": "purple",
        }
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colors.get(obj.status, "black"),
            obj.status,
        )

    @admin.display(description="Gateway Payment ID")
    def gateway_payment_id_short(self, obj):
        if obj.gateway_payment_id:
            return obj.gateway_payment_id[:20] + "..."
        return "—"

    @admin.action(description="Export selected transactions to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="transactions.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "id", "user", "email", "amount", "currency", "payment_method",
            "status", "gateway_order_id", "gateway_payment_id", "created_at",
        ])
        for t in queryset.select_related("user"):
            writer.writerow([
                str(t.id), t.user.username, t.user.email,
                t.amount, t.currency, t.payment_method, t.status,
                t.gateway_order_id, t.gateway_payment_id,
                t.created_at.isoformat() if t.created_at else "",
            ])
        return response


# ---------------------------------------------------------------------------
# Invoice admin
# ---------------------------------------------------------------------------

@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "user",
        "technology_name",
        "amount_display",
        "currency",
        "payment_method",
        "created_at",
    )
    list_filter = (
        "currency",
        "payment_method",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("invoice_number", "user__username", "user__email", "technology_name", "gateway_payment_id")
    readonly_fields = (
        "id", "invoice_number", "user", "payment_transaction",
        "tech_subscription", "technology_name", "subscription_id",
        "amount", "currency", "payment_method", "gateway_payment_id",
        "period_start", "period_end", "created_at",
    )
    list_select_related = ("user",)
    date_hierarchy = "created_at"

    @admin.display(description="Amount")
    def amount_display(self, obj):
        symbol = "₹" if obj.currency == "INR" else "$"
        return f"{symbol}{obj.amount}"


# ---------------------------------------------------------------------------
# Coupon admin
# ---------------------------------------------------------------------------

@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "is_active",
        "validity_display",
        "usage_display",
        "created_at",
    )
    list_filter = (
        "is_active",
        "discount_type",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("code", "description")
    readonly_fields = ("created_at", "updated_at", "used_count")
    actions = ["action_activate", "action_deactivate"]

    @admin.display(description="Validity")
    def validity_display(self, obj):
        now = timezone.now()
        if not obj.is_active:
            return format_html('<span style="color:grey">Inactive</span>')
        if obj.valid_until and now > obj.valid_until:
            return format_html('<span style="color:red">Expired</span>')
        if obj.valid_from and now < obj.valid_from:
            return format_html('<span style="color:orange">Not yet active</span>')
        return format_html('<span style="color:green">Valid</span>')

    @admin.display(description="Usage")
    def usage_display(self, obj):
        if obj.max_uses is None:
            return f"{obj.used_count} / ∞"
        pct = int(obj.used_count / obj.max_uses * 100) if obj.max_uses else 0
        color = "red" if pct >= 90 else "orange" if pct >= 50 else "green"
        return format_html(
            '<span style="color:{}">{} / {}</span>',
            color, obj.used_count, obj.max_uses,
        )

    @admin.action(description="Activate selected coupons")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Coupons activated.", messages.SUCCESS)

    @admin.action(description="Deactivate selected coupons")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Coupons deactivated.", messages.WARNING)


# ---------------------------------------------------------------------------
# Certificate admin
# ---------------------------------------------------------------------------

@admin.register(UserCertificate)
class UserCertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_id",
        "user",
        "technology",
        "status_badge",
        "issued_at",
        "expires_at",
    )
    list_filter = (
        ExpiredCertFilter,
        ("issued_at", admin.DateFieldListFilter),
        ("expires_at", admin.DateFieldListFilter),
    )
    search_fields = ("certificate_id", "user__username", "user__email", "technology__name")
    readonly_fields = ("certificate_id", "user", "technology", "issued_at", "expires_at", "created_at")
    list_select_related = ("user", "technology")
    date_hierarchy = "issued_at"

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_expired:
            return format_html('<span style="color:red;font-weight:bold;">Expired</span>')
        return format_html('<span style="color:green;font-weight:bold;">Valid</span>')


# ---------------------------------------------------------------------------
# Sales inquiry admin (Teams/Org Contact Sales)
# ---------------------------------------------------------------------------

@admin.register(SalesInquiry)
class SalesInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "full_name",
        "work_email",
        "team_size",
        "status",
        "quote_display",
        "handled_by",
        "created_at",
    )
    list_filter = (
        "status",
        "custom_quote_currency",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("organization", "full_name", "work_email", "company", "phone")
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("handled_by",)
    date_hierarchy = "created_at"
    fieldsets = (
        ("Submitter", {
            "fields": ("full_name", "organization", "work_email", "company", "phone", "team_size", "message"),
        }),
        ("Triage", {
            "fields": ("status", "handled_by"),
        }),
        ("Custom quote", {
            "fields": (
                "custom_quote_amount", "custom_quote_currency",
                "custom_quote_notes", "custom_quote_valid_until",
            ),
        }),
        ("Meta", {
            "fields": ("id", "created_at", "updated_at"),
        }),
    )

    @admin.display(description="Quote")
    def quote_display(self, obj):
        if obj.custom_quote_amount is None:
            return "—"
        return f"{obj.custom_quote_currency} {obj.custom_quote_amount}"


# Fix missing import for ExpiredCouponFilter
from django.db import models
