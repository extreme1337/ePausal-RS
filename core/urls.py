from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path("", views.landing, name="landing"),
    path("features/", views.features_page, name="features"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    # Registration Flow
    path(
        "register/choose-plan/", views.register_choose_plan, name="register_choose_plan"
    ),
    path("register/", views.register, name="register"),
    path("register/payment/", views.payment, name="payment"),
    path("register/success/", views.registration_success, name="registration_success"),
    path("cancel-subscription/", views.cancel_subscription, name="cancel_subscription"),
    # Language
    path(
        "change-language/<str:lang_code>/",
        views.change_language,
        name="change_language",
    ),
    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    path("change-plan/", views.change_plan, name="change_plan"),
    path("payment/process/", views.process_payment, name="process_payment"),
    path(
        "payment/upgrade/",
        views.process_upgrade_payment,
        name="process_upgrade_payment",
    ),
    # Prihodi
    path("prihodi/", views.prihodi_view, name="prihodi"),
    # Email Inbox
    path("inbox/", views.inbox_view, name="inbox"),
    path("inbox/webhook/", views.email_webhook, name="email_webhook"),
    path("inbox/confirm/", views.inbox_confirm, name="inbox_confirm"),
    path("inbox/confirm-all/", views.inbox_confirm_all, name="inbox_confirm_all"),
    path("inbox/<int:inbox_id>/delete/", views.inbox_delete, name="inbox_delete"),
    # Izvodi
    path("izvodi/upload/", views.izvodi_upload, name="izvodi_upload"),
    path("izvodi/", views.izvodi_pregled, name="izvodi_pregled"),
    path("izvodi/<int:izvod_id>/delete/", views.izvod_delete, name="izvod_delete"),
    # Fakture
    path("fakture/", views.fakture_view, name="fakture"),
    path("fakture/dodaj/", views.faktura_dodaj, name="faktura_dodaj"),
    path(
        "fakture/download/<int:faktura_id>/",
        views.download_invoice,
        name="download_invoice",
    ),
    path(
        "fakture/<int:faktura_id>/status/",
        views.update_invoice_status,
        name="update_invoice_status",
    ),
    # Uplatnice
    path("uplatnice/", views.uplatnice_view, name="uplatnice"),
    path(
        "uplatnice/download/<int:uplatnica_id>/",
        views.download_payment,
        name="download_payment",
    ),
    # Bilans
    path("bilans/", views.bilans_view, name="bilans"),
    path(
        "bilans/download/<int:bilans_id>/",
        views.download_bilans,
        name="download_bilans",
    ),
    path(
        "bilans/godisnji/<int:godina>/",
        views.godisnji_izvjestaj_view,
        name="godisnji_izvjestaj",
    ),
    # User Preferences
    path("preferences/", views.preferences_view, name="preferences"),
    path("export-data/", views.export_all_data, name="export_data"),
    # Admin Panel
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path(
        "admin-panel/login-as/<int:user_id>/",
        views.admin_login_as,
        name="admin_login_as",
    ),
    path(
        "admin-panel/retry/<int:request_id>/",
        views.retry_failed_request,
        name="retry_request",
    ),
    path(
        "admin-panel/skip/<int:request_id>/",
        views.skip_failed_request,
        name="skip_request",
    ),
    path("admin-panel/banka/save/", views.admin_banka_save, name="admin_banka_save"),
    path(
        "admin-panel/banka/<int:banka_id>/",
        views.admin_banka_get,
        name="admin_banka_get",
    ),
    path(
        "admin-panel/banka/<int:banka_id>/toggle/",
        views.admin_banka_toggle,
        name="admin_banka_toggle",
    ),
    path(
        "admin-panel/banka/<int:banka_id>/delete/",
        views.admin_banka_delete,
        name="admin_banka_delete",
    ),
    path(
        "admin-panel/parametri/update/",
        views.admin_parametri_update,
        name="admin_parametri_update",
    ),
    path(
        "admin-panel/extend-trial/<int:user_id>/",
        views.admin_extend_trial,
        name="admin_extend_trial",
    ),
]
