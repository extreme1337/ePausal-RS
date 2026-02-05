import base64
import io
from pyexpat.errors import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse, HttpResponse, FileResponse
from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.utils.translation import activate, get_language
from django.core.files.base import ContentFile
from collections import defaultdict
from django.core.paginator import Paginator
from decimal import Decimal
from .models import *
from .utils import (
    generate_invoice_doc,
    generate_bilans_csv,
    generate_income_predictions,
    get_chart_data_prihodi,
    generate_payment_slip_png,
    check_rate_limit,
    log_audit,
    generate_godisnji_izvjestaj_pdf,
    parse_bank_statement_pdf,
    get_client_ip,
)
import json

from django.contrib import messages
from django.db import transaction
from .models import Faktura, StavkaFakture
from datetime import date, datetime
import re

# ============================================
# HELPER FUNCTIONS
# ============================================


def get_client_ip(request):
    """Dobij IP adresu klijenta"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# ============================================
# PUBLIC VIEWS
# ============================================


def landing(request):
    """Landing page sa pricing"""
    plans = [
        {
            "name": "Starter",
            "price": 15,
            "features": [
                "Osnovna evidencija",
                "Do 50 prihoda/mj",
                "Fakture",
                "Email podrška",
            ],
        },
        {
            "name": "Professional",
            "price": 29,
            "features": ["Email inbox AI", "Neograničeno", "Uplatnice", "Prioritet"],
        },
        {
            "name": "Business",
            "price": 49,
            "features": [
                "API pristup",
                "Bilans",
                "Custom izvještaji",
                "Multi korisnici",
            ],
        },
        {
            "name": "Enterprise",
            "price": 99,
            "features": ["Dedicated podrška", "Integracije", "SLA", "White label"],
        },
    ]

    promo_codes = {
        "EARLYBIRD100": {"discount": 1.0, "description": "6 mjeseci BESPLATNO"},
        "REFERRAL20": {"discount": 0.2, "description": "20% OFF zauvijek"},
        "FRIEND50": {"discount": 0.5, "description": "50% OFF 3 mjeseca"},
        "LAUNCH2026": {"discount": 0.3, "description": "30% OFF 6 mjeseci"},
    }

    return render(
        request, "core/landing.html", {"plans": plans, "promo_codes": promo_codes}
    )


def user_login(request):
    """Login stranica"""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=email, password=password)

        if user:
            auth_login(request, user)

            SystemLog.objects.create(
                user=user,
                action="LOGIN",
                status="success",
                ip_address=get_client_ip(request),
            )

            if user.is_staff:
                return redirect("admin_panel")
            return redirect("dashboard")
        else:
            return render(
                request, "core/login.html", {"error": "Pogrešan email ili lozinka"}
            )

    return render(request, "core/login.html")


def user_logout(request):
    """Logout"""
    auth_logout(request)
    return redirect("landing")


# ============================================
# LANGUAGE & PREFERENCES
# ============================================


@login_required
def change_language(request, lang_code):
    """Promijeni jezik aplikacije"""
    if lang_code in ["sr", "en"]:
        activate(lang_code)
        request.session["django_language"] = lang_code

        prefs, created = UserPreferences.objects.get_or_create(
            korisnik=request.user.korisnik
        )
        prefs.language = lang_code
        prefs.save()

    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def preferences_view(request):
    """Korisničke preferencije"""
    prefs, created = UserPreferences.objects.get_or_create(
        korisnik=request.user.korisnik
    )

    if request.method == "POST":
        prefs.language = request.POST.get("language", "sr")
        prefs.theme = request.POST.get("theme", "light")
        prefs.email_notifications = request.POST.get("email_notifications") == "on"
        prefs.payment_reminders = request.POST.get("payment_reminders") == "on"
        prefs.save()

        return JsonResponse({"success": True})


# ============================================
# REGISTRATION FLOW
# ============================================


def features_page(request):
    """Features page"""
    return render(request, "core/features.html")


def register_choose_plan(request):
    """Step 1: Odabir plana"""
    plans = [
        {
            "name": "Starter",
            "price": 15,
            "features": ["Osnovna evidencija", "Fakture", "Email podrška"],
        },
        {
            "name": "Professional",
            "price": 29,
            "features": ["Email inbox AI", "Uplatnice", "Prioritet"],
        },
        {
            "name": "Business",
            "price": 49,
            "features": ["API pristup", "Bilans", "Custom izvještaji"],
        },
        {
            "name": "Enterprise",
            "price": 99,
            "features": ["Dedicated podrška", "Integracije", "SLA"],
        },
    ]
    return render(request, "core/register_choose_plan.html", {"plans": plans})


def register(request):
    """Step 2: Registracija"""
    selected_plan = request.GET.get("plan", "Professional")
    plan_prices = {"Starter": 15, "Professional": 29, "Business": 49, "Enterprise": 99}

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")

        if password != password_confirm:
            return render(
                request,
                "core/register.html",
                {"error": "Lozinke se ne poklapaju", "selected_plan": selected_plan},
            )

        if User.objects.filter(username=email).exists():
            return render(
                request,
                "core/register.html",
                {"error": "Email već postoji", "selected_plan": selected_plan},
            )

        request.session["registration_data"] = {
            "ime": request.POST.get("ime"),
            "email": email,
            "password": password,
            "jib": request.POST.get("jib"),
            "racun": request.POST.get("racun"),
            "plan": request.POST.get("plan"),
        }

        return redirect("payment")

    return render(
        request,
        "core/register.html",
        {
            "selected_plan": selected_plan,
            "plan_price": plan_prices.get(selected_plan, 29),
        },
    )


def payment(request):
    """Step 3: Plaćanje"""
    reg_data = request.session.get("registration_data")
    if not reg_data:
        return redirect("register_choose_plan")

    plan_prices = {"Starter": 15, "Professional": 29, "Business": 49, "Enterprise": 99}
    plan_name = reg_data.get("plan", "Professional")
    plan_price = plan_prices.get(plan_name, 29)

    if request.method == "POST":
        user = User.objects.create_user(
            username=reg_data["email"],
            email=reg_data["email"],
            password=reg_data["password"],
        )

        korisnik = Korisnik.objects.create(
            user=user,
            ime=reg_data["ime"],
            plan=plan_name,
            jib=reg_data["jib"],
            racun=reg_data["racun"],
        )

        UserPreferences.objects.create(
            korisnik=korisnik, email_notifications=True, payment_reminders=True
        )

        trial_end_date = timezone.now() + timedelta(days=14)
        EmailNotification.objects.create(
            korisnik=korisnik,
            notification_type="payment_reminder",
            scheduled_date=trial_end_date - timedelta(days=2),
            email_subject="Trial period ističe za 2 dana",
            email_body=f"Prvi charge: {plan_price} KM",
        )

        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        del request.session["registration_data"]

        request.session["registration_success"] = {
            "plan_name": plan_name,
            "plan_price": plan_price,
            "user_email": user.email,
        }

        return redirect("registration_success")

    return render(
        request, "core/payment.html", {"plan_name": plan_name, "plan_price": plan_price}
    )


def registration_success(request):
    """Success page"""
    success_data = request.session.get("registration_success")
    if not success_data:
        return redirect("landing")

    context = success_data
    del request.session["registration_success"]

    return render(request, "core/registration_success.html", context)


def cancel_subscription(request):
    """Otkaži pretplatu"""
    if request.method == "POST" and request.user.is_authenticated:
        SystemLog.objects.create(
            user=request.user, action="CANCEL_SUBSCRIPTION", status="success"
        )
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Unauthorized"}, status=403)

    return render(request, "core/preferences.html", {"prefs": prefs})


# ============================================
# DASHBOARD
# ============================================


@login_required
def dashboard(request):
    """Enhanced dashboard sa Chart.js i AI predikcijama"""
    korisnik = request.user.korisnik

    # Calculate subscription days left
    if korisnik.trial_end_date:
        days_left = (korisnik.trial_end_date - timezone.now().date()).days
        subscription_days_left = max(0, days_left)
    else:
        # Auto-set trial_end_date if missing
        korisnik.trial_end_date = korisnik.registrovan + timedelta(days=30)
        korisnik.save()
        subscription_days_left = (korisnik.trial_end_date - timezone.now().date()).days

    # Plan prices
    plan_prices = {"Starter": 15, "Professional": 29, "Business": 49, "Enterprise": 99}
    current_plan_price = plan_prices.get(korisnik.plan, 29)

    # Statistike
    prihodi = korisnik.prihodi.all()
    ukupan_prihod = sum([p.iznos for p in prihodi])
    porez = ukupan_prihod * Decimal(str(settings.STOPA_POREZA))
    doprinosi = (
        Decimal(str(settings.PROSJECNA_BRUTO_PLATA))
        * Decimal(str(settings.STOPA_DOPRINOSA))
        * len(prihodi)
    )
    neto = ukupan_prihod - porez - doprinosi

    # Chart data
    chart_data = get_chart_data_prihodi(korisnik)

    # AI Predictions
    predictions = generate_income_predictions(korisnik)

    if predictions:
        pred_labels = [p.mjesec for p in predictions]
        pred_values = [float(p.predicted_income) for p in predictions]
        pred_confidence = [float(p.confidence) for p in predictions]
    else:
        pred_labels = []
        pred_values = []
        pred_confidence = []

    context = {
        "korisnik": korisnik,
        "subscription_days_left": subscription_days_left,
        "current_plan_price": current_plan_price,
        "stats": {
            "ukupno": ukupan_prihod,
            "porez": porez,
            "doprinosi": doprinosi,
            "neto": neto,
        },
        "chart_data": json.dumps(chart_data),
        "predictions": predictions,
        "pred_labels": json.dumps(pred_labels),
        "pred_values": json.dumps(pred_values),
        "pred_confidence": json.dumps(pred_confidence),
        # "inbox_count": korisnik.inbox.filter(potvrdjeno=False).count(),
        "fakture_count": request.user.fakture.count(),
        "uplatnice_count": korisnik.uplatnice.count(),
    }

    return render(request, "core/dashboard.html", context)


@login_required
@require_http_methods(["POST"])
def inbox_confirm(request):
    """Odobri izvod i uvezi u Prihode/Rashode"""
    inbox_id = request.POST.get("inbox_id")

    if not inbox_id:
        messages.error(request, "❌ Nedostaje inbox_id")
        return redirect("inbox")

    try:
        inbox = get_object_or_404(
            EmailInbox, id=inbox_id, korisnik=request.user.korisnik, procesuirano=False
        )

        if not inbox.transakcije_json:
            messages.error(request, "❌ Nema parsovanih transakcija")
            return redirect("inbox")

        # Uvezi sve transakcije
        with transaction.atomic():
            imported_count = 0

            for trans in inbox.transakcije_json:
                # Konvertuj datum iz stringa
                datum = datetime.strptime(trans["datum"], "%Y-%m-%d").date()
                iznos = Decimal(str(abs(trans["iznos"])))
                vrsta = trans["tip"]

                # Provjeri duplikat u Prihod tabeli
                duplikat = Prihod.objects.filter(
                    korisnik=inbox.korisnik,
                    datum=datum,
                    iznos=iznos,
                    vrsta=vrsta,
                    opis=trans["opis"],
                ).exists()

                if duplikat:
                    print(f"⏭️ SKIP duplikat: {trans['opis']}")
                    continue

                # Kreiraj Prihod/Rashod
                Prihod.objects.create(
                    korisnik=inbox.korisnik,
                    datum=datum,
                    mjesec=datum.strftime("%Y-%m"),
                    iznos=iznos,
                    vrsta=vrsta,
                    opis=trans["opis"],
                    izvod_fajl=inbox.pdf_fajl,
                )

                imported_count += 1

            # Označi kao obrađeno
            inbox.procesuirano = True
            inbox.datum_odobravanja = timezone.now()
            inbox.save()

            # Log
            SystemLog.objects.create(
                user=request.user,
                action="INBOX_CONFIRM",
                status="success",
                ip_address=get_client_ip(request),
                details=f"Imported {imported_count} transactions from inbox {inbox.id}",
            )

        messages.success(request, f"✅ Uvezeno {imported_count} transakcija!")

    except Exception as e:
        messages.error(request, f"❌ Greška: {str(e)}")
        import traceback

        traceback.print_exc()

    return redirect("inbox")


@login_required
@require_http_methods(["POST"])
def inbox_confirm_all(request):
    """Odobri SVE izvode odjednom"""
    korisnik = request.user.korisnik

    inbox_items = korisnik.inbox_poruke.filter(procesuirano=False)

    if not inbox_items.exists():
        return JsonResponse({"success": False, "error": "Nema izvoda za odobrenje"})

    try:
        total_imported = 0

        with transaction.atomic():
            for inbox in inbox_items:
                if not inbox.transakcije_json:
                    continue

                for trans in inbox.transakcije_json:
                    datum = datetime.strptime(trans["datum"], "%Y-%m-%d").date()
                    iznos = Decimal(str(abs(trans["iznos"])))
                    vrsta = trans["tip"]

                    # Skip duplikata
                    if Prihod.objects.filter(
                        korisnik=korisnik,
                        datum=datum,
                        iznos=iznos,
                        vrsta=vrsta,
                        opis=trans["opis"],
                    ).exists():
                        continue

                    Prihod.objects.create(
                        korisnik=korisnik,
                        datum=datum,
                        mjesec=datum.strftime("%Y-%m"),
                        iznos=iznos,
                        vrsta=vrsta,
                        opis=trans["opis"],
                        izvod_fajl=inbox.pdf_fajl,
                    )

                    total_imported += 1

                inbox.procesuirano = True
                inbox.datum_odobravanja = timezone.now()
                inbox.save()

        return JsonResponse({"success": True, "count": total_imported})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def inbox_delete(request, inbox_id):
    """Obriši izvod iz inboxa"""
    try:
        inbox = get_object_or_404(
            EmailInbox, id=inbox_id, korisnik=request.user.korisnik
        )

        inbox.delete()
        messages.success(request, "🗑️ Izvod obrisan")

    except Exception as e:
        messages.error(request, f"❌ Greška: {str(e)}")

    return redirect("inbox")


@login_required
@require_http_methods(["POST"])
def change_plan(request):
    """Promjena plana sa upgrade/downgrade logikom i prorated billing"""
    try:
        korisnik = request.user.korisnik
        data = json.loads(request.body)

        new_plan = data.get("new_plan")
        timing = data.get("timing", "next_month")

        plan_prices = {
            "Starter": 15,
            "Professional": 29,
            "Business": 49,
            "Enterprise": 99,
        }

        plan_order = {"Starter": 1, "Professional": 2, "Business": 3, "Enterprise": 4}

        current_price = plan_prices[korisnik.plan]
        new_price = plan_prices[new_plan]

        # Determine upgrade or downgrade
        is_upgrade = plan_order[new_plan] > plan_order[korisnik.plan]

        if is_upgrade:
            if timing == "immediate":
                # UPGRADE - Immediate with prorated billing
                trial_end = korisnik.trial_end_date or (
                    korisnik.registrovan + timedelta(days=30)
                )
                today = timezone.now().date()
                days_left = max(0, (trial_end - today).days)

                # Calculate prorated amount
                price_difference = new_price - current_price
                prorated_amount = round((price_difference * days_left / 30), 2)

                # DON'T update plan yet - wait for payment

                SystemLog.objects.create(
                    user=request.user,
                    action="PLAN_UPGRADE_INITIATED",
                    status="pending",
                    ip_address=get_client_ip(request),
                    details=f"Initiated upgrade from {korisnik.plan} to {new_plan}. Prorated: {prorated_amount} KM for {days_left} days. Awaiting payment.",
                )

                return JsonResponse(
                    {
                        "success": True,
                        "requires_payment": True,
                        "amount_to_charge": f"{prorated_amount:.2f}",
                        "prorated_details": f"Razlika {price_difference} KM × {days_left} dana / 30 = {prorated_amount:.2f} KM",
                        "effective_date": "odmah",
                        "new_plan": new_plan,
                        "days_left": days_left,
                    }
                )
            else:
                # UPGRADE - Next month (no payment needed yet)
                trial_end = korisnik.trial_end_date or (
                    korisnik.registrovan + timedelta(days=30)
                )
                next_period_start = trial_end + timedelta(days=1)

                # TODO: Save scheduled plan change in database (create ScheduledPlanChange model)

                SystemLog.objects.create(
                    user=request.user,
                    action="PLAN_UPGRADE_SCHEDULED",
                    status="success",
                    ip_address=get_client_ip(request),
                    details=f"Scheduled upgrade from {korisnik.plan} to {new_plan} on {next_period_start}",
                )

                return JsonResponse(
                    {
                        "success": True,
                        "requires_payment": False,
                        "effective_date": next_period_start.strftime("%d.%m.%Y"),
                        "new_plan": new_plan,
                    }
                )
        else:
            # DOWNGRADE - Always next month
            trial_end = korisnik.trial_end_date or (
                korisnik.registrovan + timedelta(days=30)
            )
            next_period_start = trial_end + timedelta(days=1)

            # TODO: Save scheduled plan change

            SystemLog.objects.create(
                user=request.user,
                action="PLAN_DOWNGRADE_SCHEDULED",
                status="success",
                ip_address=get_client_ip(request),
                details=f"Scheduled downgrade from {korisnik.plan} to {new_plan} on {next_period_start}",
            )

            return JsonResponse(
                {
                    "success": True,
                    "requires_payment": False,
                    "effective_date": next_period_start.strftime("%d.%m.%Y"),
                    "new_plan": new_plan,
                }
            )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def process_upgrade_payment(request):
    """Procesira prorated payment za upgrade plana"""
    if request.method == "POST":
        try:
            korisnik = request.user.korisnik

            # Payment details
            card_number = request.POST.get("card_number", "").replace(" ", "")
            expiry = request.POST.get("expiry")
            cvv = request.POST.get("cvv")

            # Plan change details
            new_plan = request.POST.get("new_plan")
            prorated_amount = Decimal(request.POST.get("prorated_amount", "0"))

            # Validacija
            if len(card_number) != 16:
                messages.error(
                    request, "❌ Neispravan broj kartice (mora biti 16 cifara)"
                )
                return redirect("dashboard")

            if len(cvv) != 3:
                messages.error(request, "❌ Neispravan CVV (mora biti 3 cifre)")
                return redirect("dashboard")

            # Validacija expiry
            if not expiry or "/" not in expiry:
                messages.error(request, "❌ Neispravan datum isteka kartice")
                return redirect("dashboard")

            # OVDJE BI ŠAO PRAVI PAYMENT GATEWAY (Stripe, PayPal, etc.)
            # Za sada simuliramo uspješno plaćanje

            # Simulacija payment processing
            import time

            time.sleep(0.5)  # Simulacija API call-a

            # Payment successful - update plan
            old_plan = korisnik.plan
            korisnik.plan = new_plan
            korisnik.save()

            # Log successful payment
            SystemLog.objects.create(
                user=request.user,
                action="PRORATED_PAYMENT_SUCCESS",
                status="success",
                ip_address=get_client_ip(request),
                details=f"Prorated upgrade payment: {prorated_amount} KM. Plan changed from {old_plan} to {new_plan}. Card: ****{card_number[-4:]}",
            )

            messages.success(
                request,
                f"✅ Plaćanje uspješno! Plan promijenjen sa {old_plan} na {new_plan}. Naplaćeno: {prorated_amount} KM",
            )

            return redirect("dashboard")

        except Exception as e:
            SystemLog.objects.create(
                user=request.user,
                action="PRORATED_PAYMENT_FAILED",
                status="error",
                ip_address=get_client_ip(request),
                details=f"Payment failed: {str(e)}",
            )

            messages.error(request, f"❌ Greška pri plaćanju: {str(e)}")
            return redirect("dashboard")

    return redirect("dashboard")


# ============================================
# PRIHODI I RASHODI
# ============================================


@login_required
def prihodi_view(request):
    """Prikaz prihoda grupisanih po mjesecu sa novom logikom poreza"""

    # Pronađi Korisnik objekat
    try:
        korisnik = Korisnik.objects.get(user=request.user)
    except Korisnik.DoesNotExist:
        korisnik = None

    if not korisnik:
        return render(request, "core/prihodi.html", {"error": "Korisnik nije pronađen"})

    # Preuzmi sistemske parametre
    parametri = SistemskiParametri.get_parametri()

    # Preuzmi prihode
    prihodi = Prihod.objects.filter(korisnik=korisnik)

    # Filter po mjesecu
    mjesec_param = request.GET.get("mjesec", "")
    if mjesec_param:
        prihodi = prihodi.filter(mjesec__endswith=f"-{int(mjesec_param):02d}")

    # Filter po godini
    godina_param = request.GET.get("godina", "")
    godina_za_porez = int(godina_param) if godina_param else datetime.now().year

    if godina_param:
        prihodi = prihodi.filter(mjesec__startswith=godina_param)

    # Pretraga
    search = request.GET.get("search", "")
    if search:
        prihodi = prihodi.filter(Q(iznos__icontains=search) | Q(opis__icontains=search))

    # Izračunaj godišnji prihod (samo za prikaz)
    godisnji_prihod_sve = Prihod.objects.filter(
        korisnik=korisnik, mjesec__startswith=str(godina_za_porez), vrsta="prihod"
    ).aggregate(total=Sum("iznos"))["total"] or Decimal("0")

    # Koristi TIP koji je korisnik RUČNO odabrao
    tip_preduzetnika = korisnik.tip_preduzetnika

    # Odredi poresku stopu na osnovu tipa
    if tip_preduzetnika == "veliki":
        porez_stopa = parametri.porez_veliki_preduzetnik / Decimal("100")  # 10% -> 0.10
    else:
        porez_stopa = parametri.porez_mali_preduzetnik / Decimal("100")  # 2% -> 0.02

    # Grupisanje po mjesecu
    mjesecni_podaci_dict = defaultdict(lambda: Decimal("0"))

    for prihod in prihodi:
        if prihod.vrsta == "prihod":  # Samo prihodi, ne rashodi
            mjesecni_podaci_dict[prihod.mjesec] += prihod.iznos

    # Konvertuj u listu i izračunaj
    mjesecni_podaci_lista = []
    ukupan_prihod = Decimal("0")
    ukupan_porez = Decimal("0")
    ukupni_doprinosi = Decimal("0")

    for mjesec_key, ukupan_prihod_mjeseca in sorted(
        mjesecni_podaci_dict.items(), reverse=True
    ):
        # Doprinosi - fiksno mjesečno
        doprinosi = parametri.mjesecni_doprinosi

        # Porez se računa drugačije za male i velike preduzetnike
        if tip_preduzetnika == "mali":
            # Mali: 2% mjesečno
            porez = ukupan_prihod_mjeseca * porez_stopa
        else:
            # Veliki: 10% godišnje, plaća se u martu
            mjesec_broj = int(mjesec_key.split("-")[1])
            if mjesec_broj == parametri.mjesec_placanja_poreza:  # Mart (3)
                # U martu se plaća cijeli godišnji porez
                porez = godisnji_prihod_sve * porez_stopa
            else:
                porez = Decimal("0")  # Ostali mjeseci 0

        ukupni_rashodi = porez + doprinosi
        neto = ukupan_prihod_mjeseca - ukupni_rashodi

        mjesecni_podaci_lista.append(
            {
                "mjesec": mjesec_key,
                "prihod": ukupan_prihod_mjeseca,
                "porez": porez,
                "doprinosi": doprinosi,
                "ukupni_rashodi": ukupni_rashodi,
                "neto": neto,
            }
        )

        ukupan_prihod += ukupan_prihod_mjeseca
        ukupan_porez += porez
        ukupni_doprinosi += doprinosi

    # Paginacija
    paginator = Paginator(mjesecni_podaci_lista, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Liste za dropdown
    mjeseci = [
        (1, "Januar"),
        (2, "Februar"),
        (3, "Mart"),
        (4, "April"),
        (5, "Maj"),
        (6, "Jun"),
        (7, "Jul"),
        (8, "Avgust"),
        (9, "Septembar"),
        (10, "Oktobar"),
        (11, "Novembar"),
        (12, "Decembar"),
    ]

    trenutna_godina = datetime.now().year
    godine = range(trenutna_godina, 2020, -1)

    # Naziv mjeseca
    naziv_mjeseca = ""
    if mjesec_param:
        mjesec_dict = dict(mjeseci)
        naziv_mjeseca = mjesec_dict.get(int(mjesec_param), "")

    # Totali
    ukupni_rashodi_total = ukupan_porez + ukupni_doprinosi
    neto_total = ukupan_prihod - ukupni_rashodi_total

    context = {
        "page_obj": page_obj,
        "mjeseci": mjeseci,
        "godine": godine,
        "selektovani_mjesec": int(mjesec_param) if mjesec_param else None,
        "selektovana_godina": godina_za_porez,
        "search": search,
        "totali": {
            "prihod": ukupan_prihod,
            "porez": ukupan_porez,
            "doprinosi": ukupni_doprinosi,
            "rashodi": ukupni_rashodi_total,
            "neto": neto_total,
        },
        "total_count": len(mjesecni_podaci_lista),
        "naziv_mjeseca": naziv_mjeseca,
        "tip_preduzetnika": tip_preduzetnika,
        "godisnji_prihod": godisnji_prihod_sve,
        "parametri": parametri,
    }

    return render(request, "core/prihodi.html", context)


# ============================================
# EMAIL INBOX
# ============================================


@login_required
def inbox_view(request):
    """Email inbox - SAMO prikazivanje"""
    korisnik = request.user.korisnik

    # Provjera plana
    if korisnik.plan not in ["Professional", "Business", "Enterprise"]:
        messages.warning(request, "Vaš plan ne podržava automatski uvoz.")
        return redirect("dashboard")

    # Inbox poruke koje NISU odobrene
    inbox_poruke = korisnik.inbox_poruke.filter(procesuirano=False).order_by(
        "-datum_prijema"
    )

    # Dodaj dodatne info za svaki inbox item
    for poruka in inbox_poruke:
        poruka.ukupno_prihodi = poruka.get_ukupno_prihodi()
        poruka.ukupno_rashodi = poruka.get_ukupno_rashodi()
        poruka.neto = poruka.get_neto()
        poruka.broj_transakcija = (
            len(poruka.transakcije_json) if poruka.transakcije_json else 0
        )

    context = {"inbox_poruke": inbox_poruke, "total_count": inbox_poruke.count()}

    return render(request, "core/inbox.html", context)

    # 3. Logika za GET (Prikaz stranice)
    # ISPRAVLJENO: korisnik.inbox_poruke.all()
    inbox_poruke = korisnik.inbox_poruke.all()

    return render(request, "core/inbox.html", {"inbox_poruke": inbox_poruke})


from django.views.decorators.csrf import csrf_exempt


@login_required
def inbox_confirm(request):
    if request.method == "POST":
        inbox_id = request.POST.get("inbox_id")
        stavka = get_object_or_404(EmailInbox, id=inbox_id, korisnik__user=request.user)

        if not stavka.pdf_fajl:
            messages.error(request, "Nema PDF fajla za ovaj unos.")
            return redirect("inbox")

        # POZIV TVOG PARSERA IZ UTILS.PY
        transakcije = parse_bank_statement_pdf(stavka.pdf_fajl)

        if transakcije:
            with transaction.atomic():
                for t in transakcije:
                    iznos = Decimal(str(t["iznos"]))
                    # Tvoj parser vraća negativne iznose za rashode
                    vrsta = "prihod" if iznos > 0 else "rashod"

                    Prihod.objects.create(
                        korisnik=stavka.korisnik,
                        datum=t["datum"],
                        mjesec=t["datum"].strftime("%Y-%m"),
                        iznos=abs(iznos),
                        vrsta=vrsta,
                        opis=t["opis"],
                        izvod_fajl=stavka.pdf_fajl,  # Link ka originalu
                    )

                stavka.procesuirano = True
                stavka.save()
            messages.success(request, f"Uvezeno {len(transakcije)} transakcija!")
        else:
            messages.error(request, "Parser nije prepoznao podatke u PDF-u.")

    return redirect("inbox")


from django.core.files.base import ContentFile


@csrf_exempt
def email_webhook(request):
    """
    CloudMailin webhook - podržava JSON i Multipart format

    Test mode: test+JIB@cloudmailin.net
    Production: JIB u Subject liniji
    """

    # GET request - CloudMailin verifikacija
    if request.method == "GET":
        print("✅ CloudMailin verifikacija - GET request")
        return HttpResponse("Webhook is ready", status=200)

    # POST request - obrada emaila
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    print("\n" + "=" * 70)
    print("📧 EMAIL WEBHOOK AKTIVIRAN")
    print("=" * 70)

    try:
        # ============================================
        # PARSUJ REQUEST - JSON ili Multipart
        # ============================================
        content_type = request.META.get("CONTENT_TYPE", "")
        print(f"Content-Type: {content_type}")

        if "application/json" in content_type:
            # JSON format
            data = json.loads(request.body)
            envelope = data.get("envelope", {})
            headers = data.get("headers", {})
            attachments = data.get("attachments", [])

        elif (
            "multipart/form-data" in content_type
            or "application/x-www-form-urlencoded" in content_type
        ):
            # Multipart format (CloudMailin default)
            print("📦 Multipart format detected")

            # Envelope podaci
            to_address = request.POST.get("envelope[to]", "")
            from_address = request.POST.get("envelope[from]", "")
            subject = request.POST.get(
                "headers[Subject]", request.POST.get("subject", "")
            )

            envelope = {"to": to_address, "from": from_address}
            headers = {"Subject": subject}

            # Attachments iz FILES
            attachments = []

            for key in request.FILES:
                file = request.FILES[key]

                # Čitaj file content
                file_content = file.read()

                # Enkoduj u base64 (kao što bi JSON radio)
                content_base64 = base64.b64encode(file_content).decode("utf-8")

                attachments.append(
                    {
                        "file_name": file.name,
                        "content_type": file.content_type,
                        "content": content_base64,
                    }
                )

                print(
                    f"📎 Attachment: {file.name} ({file.content_type}, {len(file_content)} bytes)"
                )

        else:
            print(f"❌ Unsupported content type: {content_type}")
            return HttpResponse("Unsupported content type", status=400)

        to_address = envelope.get("to", "")
        from_address = envelope.get("from", "")
        subject = headers.get("Subject", "")

        print(f"FROM: {from_address}")
        print(f"TO: {to_address}")
        print(f"SUBJECT: {subject}")

        jib = None
        extraction_method = None

        # ============================================
        # METODA 1: EKSTRAKTUJ JIB IZ TO ADRESE (+ ALIAS)
        # ============================================
        if "cloudmailin.net" in to_address.lower():
            print("\n🧪 TEST MODE: Detekcija + alias...")

            if "+" in to_address:
                match = re.search(r"\+(\d{13})@", to_address)

                if match:
                    jib = match.group(1)
                    extraction_method = "TO adresa (+ alias)"
                    print(f"✅ JIB ekstraktovan iz TO adrese: {jib}")
                else:
                    match = re.search(r"\+(\d+)@", to_address)
                    if match:
                        potential_jib = match.group(1)
                        if len(potential_jib) == 13:
                            jib = potential_jib
                            extraction_method = "TO adresa (+ alias)"
                            print(f"✅ JIB ekstraktovan iz TO adrese: {jib}")
                        else:
                            print(
                                f"⚠️ Broj nakon + nije 13 cifara: {potential_jib} (dužina: {len(potential_jib)})"
                            )

        # ============================================
        # METODA 2: EKSTRAKTUJ JIB IZ SUBJECT-a
        # ============================================
        if not jib:
            print("\n🔍 Tražim JIB u Subject liniji...")

            jib_match = re.search(r"JIB[:\s]*(\d{13})", subject, re.IGNORECASE)

            if not jib_match:
                jib_match = re.search(r"\b(\d{13})\b", subject)

            if jib_match:
                jib = jib_match.group(1)
                extraction_method = "Subject linija"
                print(f"✅ JIB ekstraktovan iz Subject-a: {jib}")

        # ============================================
        # VALIDACIJA: JIB MORA BITI PRONAĐEN
        # ============================================
        if not jib:
            print("\n❌ JIB nije pronađen!")
            print("   Pokušaj:")
            print("   1. Test: test+4512358270004@54223ab7518b75af4c91.cloudmailin.net")
            print("   2. Prod: Subject sa 'JIB:4512358270004'")
            return HttpResponse(
                "JIB not found. Use: test+JIB@cloudmailin.net or add JIB in subject",
                status=400,
            )

        print(f"\n✅ JIB: {jib} (metoda: {extraction_method})")

        # ============================================
        # PRONAĐI KORISNIKA
        # ============================================
        try:
            korisnik = Korisnik.objects.get(jib=jib)
            print(f"✅ Korisnik: {korisnik.ime} (Plan: {korisnik.plan})")

        except Korisnik.DoesNotExist:
            print(f"❌ Korisnik sa JIB {jib} ne postoji")

            all_jibs = Korisnik.objects.values_list("jib", "ime")
            print(f"\n📋 Dostupni JIB-ovi:")
            for db_jib, ime in all_jibs:
                print(f"   - {db_jib} ({ime})")

            return HttpResponse(f"User with JIB {jib} not found", status=404)

        # ============================================
        # PROVJERI PLAN
        # ============================================
        if korisnik.plan not in ["Professional", "Business", "Enterprise"]:
            print(f"⚠️ Plan '{korisnik.plan}' ne podržava inbox")
            return HttpResponse(
                f"Plan '{korisnik.plan}' does not support inbox. Upgrade required.",
                status=403,
            )

        # ============================================
        # OBRADI PDF ATTACHMENTE
        # ============================================
        pdf_count = 0

        if not attachments:
            print("⚠️ Nema attachmenta")
            return HttpResponse("No attachments found", status=400)

        for attachment in attachments:
            content_type = attachment.get("content_type", "")
            filename = attachment.get("file_name", "izvod.pdf")

            # Samo PDF-ovi
            if content_type != "application/pdf" and not filename.lower().endswith(
                ".pdf"
            ):
                print(f"⏭️ SKIP non-PDF: {filename}")
                continue

            print(f"\n📄 PDF: {filename}")

            content_base64 = attachment.get("content")

            if not content_base64:
                print("⚠️ PDF content prazan")
                continue

            try:
                pdf_bytes = base64.b64decode(content_base64)
                print(f"📦 Size: {len(pdf_bytes)} bytes")
            except Exception as e:
                print(f"❌ Base64 decode error: {str(e)}")
                continue

            # DUPLIKAT PROVJERA
            pdf_file = io.BytesIO(pdf_bytes)
            is_duplicate, pdf_hash = EmailInbox.check_duplicate(pdf_file, korisnik)

            if is_duplicate:
                print(f"⏭️ SKIP - Duplikat (hash: {pdf_hash[:16]}...)")
                continue

            # Detektuj banku
            banka = detect_bank_from_text(from_address, subject, filename)
            print(f"🏦 Banka: {banka}")

            # PARSUJ PDF
            pdf_file = io.BytesIO(pdf_bytes)
            from .utils import parse_bank_statement_pdf

            transakcije = parse_bank_statement_pdf(pdf_file)

            if not transakcije:
                print("⚠️ Parser nije pronašao transakcije")
                inbox = EmailInbox.objects.create(
                    korisnik=korisnik,
                    from_email=from_address,
                    subject=subject,
                    banka_naziv=banka,
                    pdf_fajl=ContentFile(pdf_bytes, name=filename),
                    pdf_hash=pdf_hash,
                    transakcije_json=[],
                    confidence=0,
                    procesuirano=False,
                )
                print(f"⚠️ Inbox ID={inbox.id} (bez transakcija)")
                pdf_count += 1
                continue

            print(f"✅ Parsirano {len(transakcije)} transakcija:")

            transakcije_json = []
            ukupno_prihodi = 0
            ukupno_rashodi = 0

            for idx, trans in enumerate(transakcije, 1):
                tip = "prihod" if trans["iznos"] > 0 else "rashod"
                transakcije_json.append(
                    {
                        "datum": trans["datum"].strftime("%Y-%m-%d"),
                        "opis": trans["opis"],
                        "iznos": float(trans["iznos"]),
                        "tip": tip,
                    }
                )

                if trans["iznos"] > 0:
                    ukupno_prihodi += trans["iznos"]
                else:
                    ukupno_rashodi += abs(trans["iznos"])

                print(
                    f"  [{idx}] {tip.upper()}: {trans['iznos']:>10.2f} KM - {trans['opis'][:50]}"
                )

            neto = ukupno_prihodi - ukupno_rashodi
            print(f"\n💰 UKUPNO:")
            print(f"   Prihodi:  +{ukupno_prihodi:>10.2f} KM")
            print(f"   Rashodi:  -{ukupno_rashodi:>10.2f} KM")
            print(f"   {'='*30}")
            print(f"   Neto:      {neto:>10.2f} KM")

            inbox = EmailInbox.objects.create(
                korisnik=korisnik,
                from_email=from_address,
                subject=subject,
                banka_naziv=banka,
                pdf_fajl=ContentFile(pdf_bytes, name=filename),
                pdf_hash=pdf_hash,
                transakcije_json=transakcije_json,
                confidence=95,
                procesuirano=False,
            )

            print(f"\n✅ Inbox ID={inbox.id} za {korisnik.ime}")
            pdf_count += 1

        if pdf_count == 0:
            print("\n⚠️ Nijedan PDF nije obrađen")
            return HttpResponse("No valid PDFs processed", status=400)

        print(f"\n🎉 Ukupno: {pdf_count} PDF fajlova")
        print("=" * 70 + "\n")

        return HttpResponse("OK", status=200)

    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return HttpResponse("Server error", status=500)


def detect_bank_from_text(from_email, subject, filename=""):
    """Detektuj banku iz email podataka"""
    text = (from_email + " " + subject + " " + filename).lower()

    banks = {
        "nlb": "NLB Banka",
        "atos": "Atos Banka",
        "unicredit": "UniCredit",
        "sparkasse": "Sparkasse",
        "raiffeisen": "Raiffeisen",
        "komercijalna": "Komercijalna Banka",
        "intesa": "Intesa Sanpaolo",
        "hypo": "Hypo Alpe Adria",
    }

    for keyword, name in banks.items():
        if keyword in text:
            return name

    return "Nepoznata banka"


# ============================================
# FAKTURE
# ============================================
@login_required
@transaction.atomic
def faktura_dodaj(request):
    if request.method == "POST":
        try:
            # 1. Preuzmi podatke iz POST-a
            # odabrana_valuta = request.POST.get("valuta")
            broj = request.POST.get("broj_fakture")

            # Provjera jedinstvenosti (UNIQUE constraint)
            if Faktura.objects.filter(user=request.user, broj_fakture=broj).exists():
                messages.error(request, f"Faktura {broj} već postoji.")
                return render(
                    request,
                    "core/faktura_dodaj.html",
                    {"today": date.today().strftime("%Y-%m-%d")},
                )

            odabrana_valuta = request.POST.get("valuta")

            # --- ISPIS U KONZOLU ZA PROVJERU ---
            print("\n" + "=" * 50)
            print(f"DEBUG: PRIMLJENA VALUTA IZ FORME: >>> {odabrana_valuta} <<<")
            print("=" * 50 + "\n")
            # -----------------------------------

            # Kreiranje fakture
            faktura = Faktura.objects.create(
                user=request.user,
                broj_fakture=request.POST.get("broj_fakture"),
                datum_izdavanja=request.POST.get("datum_izdavanja"),
                mjesto_izdavanja=request.POST.get("mjesto_izdavanja"),
                valuta=odabrana_valuta,  # Upisujemo varijablu koju smo gore izvukli
                izdavalac_naziv=request.POST.get("izdavalac_naziv"),
                izdavalac_adresa=request.POST.get("izdavalac_adresa"),
                izdavalac_mjesto=request.POST.get("izdavalac_mjesto"),
                izdavalac_jib=request.POST.get("izdavalac_jib"),
                izdavalac_racun=request.POST.get("izdavalac_racun"),
                primalac_naziv=request.POST.get("primalac_naziv"),
                primalac_adresa=request.POST.get("primalac_adresa"),
                primalac_mjesto=request.POST.get("primalac_mjesto"),
                primalac_jib=request.POST.get("primalac_jib"),
                napomena=request.POST.get("napomena"),
            )

            # 3. Dodavanje stavki
            i = 0
            while f"stavke[{i}][opis]" in request.POST:
                opis = request.POST.get(f"stavke[{i}][opis]")
                if opis and opis.strip():
                    # Čišćenje brojeva (zarez u tačku)
                    kol = request.POST.get(f"stavke[{i}][kolicina]", "1").replace(
                        ",", "."
                    )
                    cij = request.POST.get(f"stavke[{i}][cijena]", "0").replace(
                        ",", "."
                    )

                    StavkaFakture.objects.create(
                        faktura=faktura,
                        redni_broj=i + 1,
                        opis=opis,
                        jedinica_mjere=request.POST.get(
                            f"stavke[{i}][jedinica]", "unit"
                        ),
                        kolicina=Decimal(kol),
                        cijena_po_jedinici=Decimal(cij),
                        pdv_stopa=0,
                    )
                i += 1

            # 4. FINALNI KORAK - Forsiramo valutu još jednom prije kalkulacije
            faktura.valuta = odabrana_valuta
            faktura.izracunaj_ukupno()  # Ova metoda radi self.save()

            messages.success(
                request,
                f"Faktura {faktura.broj_fakture} je sačuvana ({faktura.valuta})",
            )
            return redirect("faktura_detalji", faktura_id=faktura.id)

        except Exception as e:
            messages.error(request, f"Greška: {str(e)}")

    return render(
        request, "core/faktura_dodaj.html", {"today": date.today().strftime("%Y-%m-%d")}
    )


@login_required
@require_http_methods(["POST"])
def update_invoice_status(request, faktura_id):
    try:
        # 1. Izvlačenje podataka iz request body-ja
        data = json.loads(request.body)
        novi_status = data.get("status")

        # 2. Pronalazak fakture (provjera da pripada korisniku)
        # Napomena: U modelu ti je polje 'user', ne 'korisnik'
        faktura = get_object_or_404(Faktura, id=faktura_id, user=request.user)

        # 3. Validacija statusa prema STATUS_CHOICES u modelu
        validni_statusi = [choice[0] for choice in Faktura.STATUS_CHOICES]

        if novi_status in validni_statusi:
            faktura.status = novi_status
            faktura.save()
            return JsonResponse({"success": True})
        else:
            return JsonResponse(
                {"success": False, "error": "Nevalidan status"}, status=400
            )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def fakture_view(request):
    """Lista faktura + kreiranje nove + search + paginacija"""

    # POST - Kreiranje nove fakture
    if request.method == "POST":
        try:
            # Osnovni podaci
            faktura = Faktura.objects.create(
                user=request.user,
                broj_fakture=request.POST.get("broj_fakture"),
                datum_izdavanja=request.POST.get("datum_izdavanja"),
                mjesto_izdavanja=request.POST.get("mjesto_izdavanja", ""),
                # Izdavalac
                izdavalac_naziv=request.POST.get("izdavalac_naziv"),
                izdavalac_adresa=request.POST.get("izdavalac_adresa"),
                izdavalac_mjesto=request.POST.get("izdavalac_mjesto"),
                izdavalac_jib=request.POST.get("izdavalac_jib", ""),
                izdavalac_iban=request.POST.get("izdavalac_iban", ""),
                izdavalac_racun=request.POST.get("izdavalac_racun", ""),
                # Primalac
                primalac_naziv=request.POST.get("primalac_naziv"),
                primalac_adresa=request.POST.get("primalac_adresa"),
                primalac_mjesto=request.POST.get("primalac_mjesto"),
                primalac_jib=request.POST.get("primalac_jib", ""),
                valuta=request.POST.get("valuta"),
                status="draft",
            )

            # Dodaj stavke
            i = 0
            while f"stavke[{i}][opis]" in request.POST:
                opis = request.POST.get(f"stavke[{i}][opis]")
                jedinica = request.POST.get(f"stavke[{i}][jedinica]", "unit")
                kolicina_str = request.POST.get(f"stavke[{i}][kolicina]")
                cijena_str = request.POST.get(f"stavke[{i}][cijena]")

                if not kolicina_str or not cijena_str:
                    i += 1
                    continue

                StavkaFakture.objects.create(
                    faktura=faktura,
                    redni_broj=i + 1,
                    opis=opis,
                    jedinica_mjere=jedinica,
                    kolicina=Decimal(kolicina_str),
                    cijena_po_jedinici=Decimal(cijena_str),
                    pdv_stopa=0,
                )
                i += 1

            faktura.izracunaj_ukupno()

            messages.success(
                request, f"Faktura {faktura.broj_fakture} je uspješno kreirana!"
            )

            return redirect("download_invoice", faktura_id=faktura.id)

        except Exception as e:
            messages.error(request, f"Greška: {str(e)}")
            return redirect("fakture")

    # GET - Prikaz liste sa search, filter i paginacijom
    fakture = Faktura.objects.filter(user=request.user).order_by("-datum_izdavanja")

    # SEARCH LOGIKA
    search_query = request.GET.get("search", "").strip()

    if search_query:
        fakture = fakture.filter(
            Q(broj_fakture__icontains=search_query)
            | Q(primalac_naziv__icontains=search_query)
        )

    # FILTER PO STATUSU
    status_filter = request.GET.get("status", "")
    if status_filter:
        fakture = fakture.filter(status=status_filter)

    # FILTER PO VALUTI
    valuta_filter = request.GET.get("valuta", "")
    if valuta_filter:
        fakture = fakture.filter(valuta=valuta_filter)

    # STATISTIKA (prije paginacije - ukupno sve)
    ukupno = fakture.count()
    ukupan_iznos = fakture.aggregate(total=Sum("ukupno_sa_pdv"))["total"] or Decimal(
        "0"
    )

    # PAGINACIJA
    per_page = request.GET.get("per_page", "20")  # Default 20

    # Ako korisnik odabere "Sve"
    if per_page == "all":
        paginator = None
        page_obj = None
        fakture_page = fakture
    else:
        try:
            per_page_int = int(per_page)
            # Ograniči na 20, 40, 100
            if per_page_int not in [20, 40, 100]:
                per_page_int = 20
        except:
            per_page_int = 20

        paginator = Paginator(fakture, per_page_int)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        fakture_page = page_obj

    context = {
        "fakture": fakture_page,
        "page_obj": page_obj,
        "paginator": paginator,
        "search_query": search_query,
        "status_filter": status_filter,
        "valuta_filter": valuta_filter,
        "per_page": per_page,
        "ukupno": ukupno,
        "ukupan_iznos": ukupan_iznos,
        "status_choices": Faktura.STATUS_CHOICES,
        "valuta_choices": Faktura.VALUTA_CHOICES,
    }

    return render(request, "core/fakture.html", context)


@login_required
def download_invoice(request, faktura_id):
    """Preuzmi fakturu kao Word (HTML) dokument"""
    faktura = get_object_or_404(Faktura, id=faktura_id, user=request.user)

    # Generiši Word dokument
    from .utils import generate_invoice_doc

    html_content = generate_invoice_doc(faktura)

    # Vrati kao HTML fajl (može se otvoriti u Word-u)
    response = HttpResponse(html_content, content_type="application/msword")
    filename = f'faktura_{faktura.broj_fakture.replace("/", "-")}.doc'
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


# ============================================
# UPLATNICE
# ============================================


@login_required
def uplatnice_view(request):
    """Prikaz i kreiranje uplatnica"""
    korisnik = request.user.korisnik

    if request.method == "POST":
        uplatnica = Uplatnica.objects.create(
            korisnik=korisnik,
            datum=timezone.now().date(),
            primalac=request.POST.get("primalac"),
            iznos=Decimal(request.POST.get("iznos")),
            svrha=request.POST.get("svrha", "Porez na dohodak"),
            poziv_na_broj=request.POST.get("poziv", ""),
        )

        # Generiši PNG uplatnicu
        png_file = generate_payment_slip_png(uplatnica, korisnik)
        uplatnica.fajl = png_file
        uplatnica.save()

        log_audit(
            user=request.user,
            model_name="Uplatnica",
            object_id=uplatnica.id,
            action="CREATE",
            new_value={"primalac": uplatnica.primalac, "iznos": str(uplatnica.iznos)},
            request=request,
        )

        SystemLog.objects.create(
            user=request.user,
            action="GENERATE_PAYMENT",
            status="success",
            ip_address=get_client_ip(request),
        )

        return JsonResponse({"success": True, "file_url": uplatnica.fajl.url})

    uplatnice = korisnik.uplatnice.all()
    return render(request, "core/uplatnice.html", {"uplatnice": uplatnice})


@login_required
def download_payment(request, uplatnica_id):
    """Preuzmi postojeću uplatnicu"""
    uplatnica = get_object_or_404(
        Uplatnica, id=uplatnica_id, korisnik=request.user.korisnik
    )

    if uplatnica.fajl:
        return FileResponse(uplatnica.fajl.open("rb"), as_attachment=True)
    else:
        png_file = generate_payment_slip_png(uplatnica, request.user.korisnik)
        uplatnica.fajl = png_file
        uplatnica.save()
        return FileResponse(uplatnica.fajl.open("rb"), as_attachment=True)


@login_required
def process_payment(request):
    """Procesira plaćanje i produžava pretplatu za 30 dana"""
    if request.method == "POST":
        try:
            korisnik = request.user.korisnik

            card_number = request.POST.get("card_number", "").replace(" ", "")
            expiry = request.POST.get("expiry")
            cvv = request.POST.get("cvv")

            # Validacija
            if len(card_number) != 16 or len(cvv) != 3:
                messages.error(request, "❌ Neispravni podaci kartice")
                return redirect("dashboard")

            # Izračunaj novi datum isteka
            if (
                korisnik.trial_end_date
                and korisnik.trial_end_date > timezone.now().date()
            ):
                new_end_date = korisnik.trial_end_date + timedelta(days=30)
            else:
                new_end_date = timezone.now().date() + timedelta(days=30)

            korisnik.trial_end_date = new_end_date
            korisnik.save()

            # Log
            SystemLog.objects.create(
                user=request.user,
                action="PAYMENT_SUCCESS",
                status="success",
                ip_address=get_client_ip(request),
                details=f"Renewed subscription until {new_end_date}",
            )

            messages.success(
                request,
                f'✅ Plaćanje uspješno! Pretplata aktivna do {new_end_date.strftime("%d.%m.%Y")}',
            )

            return redirect("dashboard")

        except Exception as e:
            SystemLog.objects.create(
                user=request.user,
                action="PAYMENT_FAILED",
                status="error",
                ip_address=get_client_ip(request),
                details=str(e),
            )

            messages.error(request, f"❌ Greška pri plaćanju: {str(e)}")
            return redirect("dashboard")

    return redirect("dashboard")


# ============================================
# BILANS
# ============================================
@login_required
def izvodi_upload(request):
    """Bulk upload PDF izvoda - do 30 fajlova"""
    if request.method == "POST":
        files = request.FILES.getlist("izvodi")

        if len(files) > 30:
            messages.error(request, "Možete upload-ovati maksimalno 30 fajlova!")
            return redirect("izvodi_upload")

        ukupno_prihodi = Decimal("0")
        ukupno_rashodi = Decimal("0")
        processed_count = 0
        error_count = 0

        for pdf_file in files:
            try:
                # Sačuvaj sadržaj fajla za kasnije (mora prije parsiranja)
                file_content = pdf_file.read()
                pdf_file.seek(0)

                # Parsuj PDF - vraća listu transakcija
                transakcije = parse_bank_statement_pdf(pdf_file)

                print(
                    f"\n📄 {pdf_file.name}: Dobio {len(transakcije)} transakcija od parsera"
                )

                # Kreiraj Prihod entry za SVAKU transakciju
                for trans in transakcije:
                    print(f"  Procesiranje: {trans['opis']} | iznos={trans['iznos']}")

                    # Odredi vrstu na osnovu znaka iznosa
                    if trans["iznos"] > 0:
                        # PRIHOD
                        vrsta = "prihod"
                        iznos_za_bazu = trans["iznos"]  # Pozitivan broj
                        ukupno_prihodi += trans["iznos"]
                    else:
                        # RASHOD
                        vrsta = "rashod"
                        iznos_za_bazu = abs(
                            trans["iznos"]
                        )  # Pozitivan broj (u bazi čuvamo apsolutnu)
                        ukupno_rashodi += abs(trans["iznos"])

                    # Kreiraj u bazi
                    prihod_obj = Prihod.objects.create(
                        korisnik=request.user.korisnik,
                        mjesec=trans["datum"].strftime("%Y-%m"),
                        datum=trans["datum"],
                        iznos=iznos_za_bazu,  # SVE POZITIVNO
                        vrsta=vrsta,
                        opis=trans["opis"],
                        izvod_fajl=ContentFile(file_content, name=pdf_file.name),
                    )

                    print(
                        f"    ✅ Sačuvano u bazi: ID={prihod_obj.id}, vrsta={vrsta}, iznos={iznos_za_bazu}"
                    )

                processed_count += 1

            except Exception as e:
                error_count += 1
                print(f"❌ Greška u {pdf_file.name}: {str(e)}")
                import traceback

                traceback.print_exc()
                messages.warning(request, f"Greška u {pdf_file.name}: {str(e)}")

        # Poruka korisniku
        if processed_count > 0:
            neto = ukupno_prihodi - ukupno_rashodi
            messages.success(
                request,
                f"✅ Obrađeno {processed_count} izvoda! "
                f"💰 Prihodi: +{ukupno_prihodi:.2f} KM | "
                f"💸 Rashodi: -{ukupno_rashodi:.2f} KM | "
                f"📊 Neto: {neto:.2f} KM",
            )

        if error_count > 0:
            messages.warning(request, f"⚠️ {error_count} fajlova nije obrađeno")

        return redirect("izvodi_pregled")

    return render(request, "core/izvodi_upload.html")


@login_required
def izvod_delete(request, izvod_id):
    """Obriši pojedinačnu transakciju"""
    if request.method == "POST":
        izvod = get_object_or_404(Prihod, id=izvod_id, korisnik=request.user.korisnik)
        opis = izvod.opis[:50]
        iznos = izvod.iznos

        izvod.delete()

        messages.success(request, f"🗑️ Obrisano: {opis} - {iznos} KM")

        return redirect("izvodi_pregled")

    return redirect("izvodi_pregled")


@login_required
def izvodi_pregled(request):
    """Pregled svih transakcija sa paginacijom"""
    od_datum = request.GET.get("od")
    do_datum = request.GET.get("do")

    transakcije = (
        Prihod.objects.filter(korisnik=request.user.korisnik)
        .exclude(datum=None)
        .order_by("-datum")
    )

    if od_datum:
        transakcije = transakcije.filter(datum__gte=od_datum)
    if do_datum:
        transakcije = transakcije.filter(datum__lte=do_datum)

    from django.db.models import Sum

    # STATISTIKA (prije paginacije - sve transakcije)
    ukupno_prihodi = (
        transakcije.filter(vrsta="prihod").aggregate(total=Sum("iznos"))["total"] or 0
    )
    ukupno_rashodi = (
        transakcije.filter(vrsta="rashod").aggregate(total=Sum("iznos"))["total"] or 0
    )

    # Bilans = prihodi - rashodi
    bilans = ukupno_prihodi - ukupno_rashodi

    # Ukupan broj transakcija
    ukupno_transakcija = transakcije.count()

    # PAGINACIJA
    per_page = request.GET.get("per_page", "20")

    if per_page == "all":
        paginator = None
        page_obj = None
        transakcije_page = transakcije
    else:
        try:
            per_page_int = int(per_page)
            if per_page_int not in [20, 40, 100]:
                per_page_int = 20
        except:
            per_page_int = 20

        paginator = Paginator(transakcije, per_page_int)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        transakcije_page = page_obj

    return render(
        request,
        "core/izvodi_pregled.html",
        {
            "transakcije": transakcije_page,
            "page_obj": page_obj,
            "paginator": paginator,
            "per_page": per_page,
            "ukupno_prihodi": ukupno_prihodi,
            "ukupno_rashodi": ukupno_rashodi,
            "bilans": bilans,
            "ukupno_transakcija": ukupno_transakcija,
            "od_datum": od_datum,
            "do_datum": do_datum,
        },
    )


@login_required
def bilans_view(request):
    """Bilans uspjeha"""
    korisnik = request.user.korisnik

    if korisnik.plan not in ["Business", "Enterprise"]:
        return redirect("dashboard")

    if request.method == "POST":
        od = request.POST.get("od")
        do = request.POST.get("do")

        # Kalkulacije
        prihodi = korisnik.prihodi.filter(mjesec__gte=od, mjesec__lte=do)
        ukupan_prihod = sum([p.iznos for p in prihodi])
        porez = ukupan_prihod * Decimal(str(settings.STOPA_POREZA))
        doprinosi = (
            Decimal(str(settings.PROSJECNA_BRUTO_PLATA))
            * Decimal(str(settings.STOPA_DOPRINOSA))
            * prihodi.count()
        )
        neto = ukupan_prihod - porez - doprinosi

        bilans = Bilans.objects.create(
            korisnik=korisnik,
            od_mjesec=od,
            do_mjesec=do,
            ukupan_prihod=ukupan_prihod,
            porez=porez,
            doprinosi=doprinosi,
            neto=neto,
        )

        csv_file = generate_bilans_csv(bilans, korisnik, prihodi)
        bilans.fajl = csv_file
        bilans.save()

        SystemLog.objects.create(
            user=request.user,
            action="EXPORT_BILANS_CSV",
            status="success",
            ip_address=get_client_ip(request),
        )

        return JsonResponse({"success": True, "file_url": bilans.fajl.url})

    bilansi = korisnik.bilansi.filter(datum_isteka__gt=timezone.now())

    return render(
        request,
        "core/bilans.html",
        {"bilansi": bilansi, "retention_days": korisnik.get_retention_days()},
    )


@login_required
def download_bilans(request, bilans_id):
    """Preuzmi sačuvani bilans"""
    bilans = get_object_or_404(Bilans, id=bilans_id, korisnik=request.user.korisnik)

    if bilans.is_expired():
        return JsonResponse({"error": "Bilans je istekao"}, status=410)

    return FileResponse(bilans.fajl.open("rb"), as_attachment=True)


@login_required
def godisnji_izvjestaj_view(request, godina=None):
    """Generiši godišnji izvještaj za PURS (PDF)"""
    korisnik = request.user.korisnik

    if not godina:
        godina = timezone.now().year - 1

    izvjestaj = korisnik.godisnji_izvjestaji.filter(godina=godina).first()

    if not izvjestaj:
        prihodi = korisnik.prihodi.filter(mjesec__startswith=str(godina))
        ukupan_prihod = sum([p.iznos for p in prihodi])
        porez = ukupan_prihod * Decimal("0.02")
        doprinosi = (
            Decimal(str(settings.PROSJECNA_BRUTO_PLATA))
            * Decimal("0.70")
            * prihodi.count()
        )
        neto = ukupan_prihod - porez - doprinosi

        fakture = request.user.fakture.filter(datum__year=godina)
        klijenti = fakture.values_list("klijent", flat=True).distinct().count()

        izvjestaj = GodisnjiIzvjestaj.objects.create(
            korisnik=korisnik,
            godina=godina,
            ukupan_prihod=ukupan_prihod,
            ukupan_porez=porez,
            ukupni_doprinosi=doprinosi,
            neto_dohodak=neto,
            broj_faktura=fakture.count(),
            broj_klijenata=klijenti,
        )

        pdf_buffer = generate_godisnji_izvjestaj_pdf(korisnik, godina)
        izvjestaj.fajl_pdf.save(
            f"godisnji-izvjestaj-{godina}.pdf", ContentFile(pdf_buffer.read())
        )

    return FileResponse(izvjestaj.fajl_pdf.open("rb"), as_attachment=True)


# ============================================
# EXPORT DATA
# ============================================


@login_required
def export_all_data(request):
    """Export svih podataka korisnika (GDPR compliance)"""
    korisnik = request.user.korisnik

    data = {
        "korisnik": {
            "ime": korisnik.ime,
            "email": korisnik.user.email,
            "plan": korisnik.plan,
            "jib": korisnik.jib,
            "racun": korisnik.racun,
            "registrovan": korisnik.registrovan.isoformat(),
        },
        "prihodi": list(korisnik.prihodi.values()),
        "fakture": list(
            request.user.fakture.values(
                "broj", "datum", "klijent", "iznos", "status", "opis"
            )
        ),
        "uplatnice": list(korisnik.uplatnice.values()),
        "bilansi": list(korisnik.bilansi.values()),
    }

    json_data = json.dumps(data, indent=2, default=str, ensure_ascii=False)

    response = HttpResponse(json_data, content_type="application/json")
    response["Content-Disposition"] = (
        f'attachment; filename="epausa-export-{korisnik.ime}.json"'
    )

    return response


# ============================================
# ADMIN PANEL
# ============================================


@login_required
def admin_panel(request):
    """Admin panel sa support ticketima"""
    if not request.user.is_staff:
        return redirect("dashboard")

    tab = request.GET.get("tab", "users")
    search_query = request.GET.get("search", "").strip()
    log_search = request.GET.get("log_search", "").strip()

    # Support filters
    support_status = request.GET.get("support_status", "")
    support_prioritet = request.GET.get("support_prioritet", "")

    # Korisnici
    korisnici = Korisnik.objects.all().select_related("user")

    if search_query:
        from django.db.models import Q

        korisnici = korisnici.filter(
            Q(ime__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(jib__icontains=search_query)
        )

    # Trial/Paid logika
    today = timezone.now().date()
    for k in korisnici:
        if not k.trial_end_date:
            k.trial_end_date = k.registrovan + timedelta(days=30)
            k.save()
        if today <= k.trial_end_date:
            k.je_trial = True
            k.status_label = "Trial"
            preostalo = (k.trial_end_date - today).days
            k.dani_info = f"Još {preostalo} dana"
        else:
            k.je_trial = False
            k.status_label = "Paid"
            k.dani_info = "Aktivna licenca"

    # Logs
    logs = SystemLog.objects.all()
    if log_search:
        from django.db.models import Q

        logs = logs.filter(
            Q(user__email__icontains=log_search)
            | Q(user__username__icontains=log_search)
            | Q(action__icontains=log_search)
            | Q(ip_address__icontains=log_search)
            | Q(details__icontains=log_search)
        )
    logs = logs[:100]

    # Failed requests
    failed = FailedRequest.objects.all()

    # Parametri
    parametri = SistemskiParametri.get_parametri()

    # Banke
    banke = Banka.objects.all().order_by("-aktivna", "naziv")

    # SUPPORT PITANJA
    support_pitanja = (
        SupportPitanje.objects.all()
        .select_related("korisnik", "obradjuje")
        .prefetch_related("slike", "odgovori")
    )

    if support_status:
        support_pitanja = support_pitanja.filter(status=support_status)

    if support_prioritet:
        support_pitanja = support_pitanja.filter(prioritet=support_prioritet)

    # Statistika support
    support_stats = {
        "novo": SupportPitanje.objects.filter(status="novo").count(),
        "u_obradi": SupportPitanje.objects.filter(status="u_obradi").count(),
        "rijeseno": SupportPitanje.objects.filter(status="rijeseno").count(),
        "hitan": SupportPitanje.objects.filter(prioritet="hitan").count(),
    }

    context = {
        "korisnici": korisnici,
        "logs": logs,
        "failed_requests": failed,
        "active_tab": tab,
        "search_query": search_query,
        "log_search": log_search,
        "parametri": parametri,
        "banke": banke,
        "support_pitanja": support_pitanja,
        "support_stats": support_stats,
        "support_status": support_status,
        "support_prioritet": support_prioritet,
        "status_choices": SupportPitanje.STATUS_CHOICES,
        "prioritet_choices": SupportPitanje.PRIORITET_CHOICES,
    }

    return render(request, "core/admin_panel.html", context)


@login_required
def admin_support_update(request, pitanje_id):
    """Admin ažurira support pitanje (status, prioritet, assignee)"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        pitanje = get_object_or_404(SupportPitanje, id=pitanje_id)

        # Ažuriraj polja
        novi_status = request.POST.get("status")
        novi_prioritet = request.POST.get("prioritet")

        if novi_status:
            pitanje.status = novi_status

            # Ako je zatvoreno, postavi datum
            if novi_status == "zatvoreno":
                pitanje.datum_zatvaranja = timezone.now()

        if novi_prioritet:
            pitanje.prioritet = novi_prioritet

        # Assign to admin
        assign_to_me = request.POST.get("assign_to_me")
        if assign_to_me:
            pitanje.obradjuje = request.user

        pitanje.save()

        messages.success(request, f"✅ Ticket #{pitanje.id} ažuriran!")
        return redirect(f"/admin-panel/?tab=support")

    return redirect("/admin-panel/?tab=support")


@login_required
def admin_support_reply(request, pitanje_id):
    """Admin odgovara na support pitanje"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        pitanje = get_object_or_404(SupportPitanje, id=pitanje_id)
        odgovor_text = request.POST.get("odgovor")

        if not odgovor_text:
            messages.error(request, "❌ Odgovor ne može biti prazan")
            return redirect(f"/admin-panel/?tab=support")

        # Kreiraj odgovor
        SupportOdgovor.objects.create(
            pitanje=pitanje, admin=request.user, odgovor=odgovor_text
        )

        # Automatski promijeni status u "u_obradi" ako je bio "novo"
        if pitanje.status == "novo":
            pitanje.status = "u_obradi"

        # Assign to admin ako nije
        if not pitanje.obradjuje:
            pitanje.obradjuje = request.user

        pitanje.save()

        # Log
        SystemLog.objects.create(
            user=request.user,
            action="SUPPORT_REPLY",
            status="success",
            ip_address=get_client_ip(request),
            details=f"Reply to ticket #{pitanje.id}",
        )

        messages.success(request, f"✅ Odgovor poslat za Ticket #{pitanje.id}")
        return redirect(f"/admin-panel/?tab=support")

    return redirect("/admin-panel/?tab=support")


@login_required
def admin_support_detail(request, pitanje_id):
    """Detaljan pregled support ticketa u admin panelu"""
    if not request.user.is_staff:
        return redirect("dashboard")

    pitanje = get_object_or_404(SupportPitanje, id=pitanje_id)

    context = {
        "pitanje": pitanje,
        "all_admins": User.objects.filter(is_staff=True),
    }

    return render(request, "core/admin_support_detail.html", context)


@login_required
def admin_parametri_update(request):
    """Ažuriranje sistemskih parametara (samo za admin)"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        parametri = SistemskiParametri.get_parametri()

        # Ažuriraj vrijednosti
        parametri.mjesecni_doprinosi = Decimal(
            request.POST.get("mjesecni_doprinosi", "466.00")
        )
        parametri.prag_mali_preduzetnik = Decimal(
            request.POST.get("prag_mali_preduzetnik", "100000.00")
        )
        parametri.porez_mali_preduzetnik = Decimal(
            request.POST.get("porez_mali_preduzetnik", "2.00")
        )
        parametri.porez_veliki_preduzetnik = Decimal(
            request.POST.get("porez_veliki_preduzetnik", "10.00")
        )
        parametri.mjesec_placanja_poreza = int(
            request.POST.get("mjesec_placanja_poreza", "3")
        )
        parametri.azurirao = request.user
        parametri.save()

        messages.success(request, "✅ Sistemski parametri uspješno ažurirani!")
        return redirect("/admin-panel/?tab=parametri")

    return redirect("/admin-panel/")


@login_required
def admin_login_as(request, user_id):
    """Admin login kao drugi korisnik"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    target_user = get_object_or_404(User, id=user_id)

    auth_logout(request)
    auth_login(
        request, target_user, backend="django.contrib.auth.backends.ModelBackend"
    )

    return redirect("dashboard")


@login_required
@require_http_methods(["POST"])
def retry_failed_request(request, request_id):
    """Retry failed request"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    failed_req = get_object_or_404(FailedRequest, id=request_id)

    import random

    if random.random() > 0.5:
        SystemLog.objects.create(
            user=failed_req.user,
            action=f"{failed_req.action}_RETRY",
            status="success",
            ip_address=get_client_ip(request),
        )
        failed_req.delete()
        return JsonResponse({"success": True})
    else:
        return JsonResponse({"success": False, "error": "Retry neuspješan"})


@login_required
@require_http_methods(["POST"])
def skip_failed_request(request, request_id):
    """Skip failed request"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    failed_req = get_object_or_404(FailedRequest, id=request_id)
    failed_req.delete()

    return JsonResponse({"success": True})


# ============================================
# BANKE - CRUD (SAMO ZA ADMIN)
# ============================================


@login_required
def admin_banka_save(request):
    """Kreiranje ili izmjena banke"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        banka_id = request.POST.get("banka_id", "")

        if banka_id:
            banka = get_object_or_404(Banka, pk=banka_id)
        else:
            banka = Banka()

        # Popuni podatke (bez model polja)
        banka.naziv = request.POST.get("naziv")
        banka.skraceni_naziv = request.POST.get("skraceni_naziv")
        banka.racun_doprinosi = request.POST.get("racun_doprinosi")
        banka.racun_porez = request.POST.get("racun_porez")
        banka.primalac_doprinosi = request.POST.get("primalac_doprinosi")
        banka.primalac_porez = request.POST.get("primalac_porez")
        banka.poziv_doprinosi = request.POST.get("poziv_doprinosi", "")
        banka.poziv_porez = request.POST.get("poziv_porez", "")
        banka.svrha_doprinosi_template = request.POST.get("svrha_doprinosi_template")
        banka.svrha_porez_template = request.POST.get("svrha_porez_template")
        banka.aktivna = request.POST.get("aktivna") == "on"

        banka.save()

        action = "izmijenjene" if banka_id else "dodane"
        messages.success(request, f'✅ Banka "{banka.naziv}" uspješno {action}!')
        return redirect("/admin-panel/?tab=banke")

    return redirect("/admin-panel/?tab=banke")


@login_required
def admin_banka_get(request, banka_id):
    """Preuzmi podatke o banci (za edit modal)"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    banka = get_object_or_404(Banka, pk=banka_id)

    data = {
        "id": banka.id,
        "naziv": banka.naziv,
        "skraceni_naziv": banka.skraceni_naziv,
        "racun_doprinosi": banka.racun_doprinosi,
        "racun_porez": banka.racun_porez,
        "primalac_doprinosi": banka.primalac_doprinosi,
        "primalac_porez": banka.primalac_porez,
        "poziv_doprinosi": banka.poziv_doprinosi,
        "poziv_porez": banka.poziv_porez,
        "svrha_doprinosi_template": banka.svrha_doprinosi_template,
        "svrha_porez_template": banka.svrha_porez_template,
        "aktivna": banka.aktivna,
    }

    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def admin_banka_toggle(request, banka_id):
    """Aktiviraj/Deaktiviraj banku"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    banka = get_object_or_404(Banka, pk=banka_id)
    banka.aktivna = not banka.aktivna
    banka.save()

    status = "aktivirana" if banka.aktivna else "deaktivirana"
    messages.success(request, f'✅ Banka "{banka.naziv}" {status}!')

    return JsonResponse({"success": True, "aktivna": banka.aktivna})


@login_required
@require_http_methods(["POST"])
def admin_banka_delete(request, banka_id):
    """Obriši banku"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    banka = get_object_or_404(Banka, pk=banka_id)
    naziv = banka.naziv
    banka.delete()

    messages.success(request, f'🗑️ Banka "{naziv}" obrisana!')

    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def admin_extend_trial(request, user_id):
    """Produži trial period za korisnika (samo admin)"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        korisnik = get_object_or_404(Korisnik, user__id=user_id)
        days = int(request.POST.get("days", 30))

        # Izračunaj novi datum
        if korisnik.trial_end_date and korisnik.trial_end_date > timezone.now().date():
            # Ako trail još traje, produžavamo od postojećeg datuma
            new_date = korisnik.trial_end_date + timedelta(days=days)
        else:
            # Ako je istekao, počinjemo od danas
            new_date = timezone.now().date() + timedelta(days=days)

        korisnik.trial_end_date = new_date
        korisnik.is_trial_extended = True
        korisnik.save()

        # Logovanje
        SystemLog.objects.create(
            user=request.user,
            action=f"TRIAL_EXTENDED",
            status="success",
            ip_address=get_client_ip(request),
            details=f"Extended trial for {korisnik.ime} by {days} days. New end date: {new_date}",
        )

        messages.success(
            request,
            f'✅ Trial period produžen za {days} dana! Novi datum isteka: {new_date.strftime("%d.%m.%Y")}',
        )

        return JsonResponse(
            {
                "success": True,
                "new_date": new_date.strftime("%d.%m.%Y"),
                "days_added": days,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


#####################################################
########### SUPPORT ##################################
#######################################################
@login_required
def support_view(request):
    """Support pitanja - lista i kreiranje"""
    korisnik = request.user.korisnik

    if request.method == "POST":
        naslov = request.POST.get("naslov")
        poruka = request.POST.get("poruka")

        if not naslov or not poruka:
            messages.error(request, "❌ Naslov i poruka su obavezni")
            return redirect("support")

        # Kreiraj pitanje
        pitanje = SupportPitanje.objects.create(
            korisnik=korisnik, naslov=naslov, poruka=poruka, status="novo"
        )

        # Obradi slike (maksimalno 5)
        slike = request.FILES.getlist("slike")

        if len(slike) > 5:
            messages.warning(request, "⚠️ Maksimalno 5 slika. Samo prvih 5 je sačuvano.")
            slike = slike[:5]

        for slika in slike:
            # Validacija tipa fajla
            if not slika.content_type.startswith("image/"):
                messages.warning(request, f"⚠️ {slika.name} nije slika. Preskočeno.")
                continue

            # Validacija veličine (max 5MB)
            if slika.size > 5 * 1024 * 1024:
                messages.warning(
                    request, f"⚠️ {slika.name} je prevelika (max 5MB). Preskočeno."
                )
                continue

            SupportSlika.objects.create(pitanje=pitanje, slika=slika)

        # Log
        SystemLog.objects.create(
            user=request.user,
            action="SUPPORT_TICKET_CREATED",
            status="success",
            ip_address=get_client_ip(request),
            details=f"Ticket #{pitanje.id}: {naslov}",
        )

        messages.success(request, f"✅ Pitanje poslato! Ticket #{pitanje.id}")
        return redirect("support")

    # GET - prikaz liste
    pitanja = korisnik.support_pitanja.all()

    context = {"pitanja": pitanja}

    return render(request, "core/support.html", context)


@login_required
def support_detail(request, pitanje_id):
    """Detalji support pitanja sa odgovorima"""
    pitanje = get_object_or_404(
        SupportPitanje, id=pitanje_id, korisnik=request.user.korisnik
    )

    context = {"pitanje": pitanje}

    return render(request, "core/support_detail.html", context)


@login_required
def support_delete(request, pitanje_id):
    """Obriši support pitanje"""
    if request.method == "POST":
        pitanje = get_object_or_404(
            SupportPitanje, id=pitanje_id, korisnik=request.user.korisnik
        )

        pitanje.delete()
        messages.success(request, "🗑️ Pitanje obrisano")

    return redirect("support")
