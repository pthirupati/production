from django.urls import path
from . import views
from . import payment_controller

urlpatterns = [
    path("status/", payment_controller.PaymentStatusView.as_view(), name="payment_status"),
    path("create-order/", payment_controller.CreatePaymentOrderView.as_view(), name="create_order"),
    path("verify-payment/", payment_controller.VerifyPaymentView.as_view(), name="verify_payment"),
    path("webhook/razorpay/", payment_controller.RazorpayWebhookView.as_view(), name="razorpay_webhook"),
    path("webhook/stripe/", payment_controller.StripeWebhookView.as_view(), name="stripe_webhook"),
    path("checkout/", views.CreateCheckoutSessionView.as_view(), name="checkout"),
    path("webhook/", views.StripeWebhookView.as_view(), name="stripe_webhook_legacy"),
    path("gateway-status/", views.PaymentGatewayStatusView.as_view(), name="gateway_status"),
    path("razorpay/order/", views.CreateRazorpayOrderView.as_view(), name="razorpay_create_order"),
    path("razorpay/verify/", views.VerifyRazorpayPaymentView.as_view(), name="razorpay_verify"),
    path("confirm-payment/", views.ConfirmPaymentView.as_view(), name="confirm_payment"),
    path("subscribe/technology/", views.TechnologySubscribeView.as_view(), name="tech_subscribe"),
    path("subscribe/cancel/", views.CancelTechSubscriptionView.as_view(), name="cancel_subscription"),
    path("subscriptions/", views.UserTechSubscriptionsView.as_view(), name="user_subscriptions"),
    path("subscription-logs/", views.SubscriptionLogsView.as_view(), name="subscription_logs"),
    path("currency-rate/", views.CurrencyRateView.as_view(), name="currency_rate"),
    path("invoices/", views.UserInvoicesView.as_view(), name="user_invoices"),
    path("invoices/<uuid:invoice_id>/download/", views.InvoiceDownloadView.as_view(), name="invoice_download"),
]
