from django.apps import AppConfig


class ItsmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.itsm"
    verbose_name = "ITSM (ServiceNow-style ticketing)"
