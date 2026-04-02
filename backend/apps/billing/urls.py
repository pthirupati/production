from django.urls import path
from .views import (
    CreateCheckoutSessionView,
    StripeWebhookView,
    BillingStatusView,
    TechnologySubscribeView,
    UserTechSubscriptionsView,
    SubscriptionLogsView,
    CancelTechSubscriptionView,
    CreateRazorpayOrderView,
    VerifyRazorpayPaymentView,
    ConfirmPaymentView,
    CurrencyRateView,
)

urlpatterns = [
    path("checkout/", CreateCheckoutSessionView.as_view(), name="checkout"),
    path("webhook/", StripeWebhookView.as_view(), name="stripe_webhook"),
    path("status/", BillingStatusView.as_view(), name="billing_status"),
    path("subscribe/technology/", TechnologySubscribeView.as_view(), name="tech_subscribe"),
    path("subscribe/cancel/", CancelTechSubscriptionView.as_view(), name="cancel_subscription"),
    path("subscriptions/", UserTechSubscriptionsView.as_view(), name="user_subscriptions"),
    path("subscription-logs/", SubscriptionLogsView.as_view(), name="subscription_logs"),
    # Razorpay payment endpoints
    path("razorpay/order/", CreateRazorpayOrderView.as_view(), name="razorpay_create_order"),
    path("razorpay/verify/", VerifyRazorpayPaymentView.as_view(), name="razorpay_verify"),
    # Payment confirmation (demo/gateway mode)
    path("confirm-payment/", ConfirmPaymentView.as_view(), name="confirm_payment"),
    # Currency rate
    path("currency-rate/", CurrencyRateView.as_view(), name="currency_rate"),
]
