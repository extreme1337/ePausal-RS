from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse, HttpResponse, FileResponse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.utils.translation import activate, get_language
from django.core.files.base import ContentFile
from decimal import Decimal
from .models import *
from .utils import (
    generate_invoice_doc, generate_payment_slip_png, generate_bilans_csv,
    generate_income_predictions, get_chart_data_prihodi, 
    send_payment_reminder, check_rate_limit, log_audit,
    process_uploaded_pdf, generate_godisnji_izvjestaj_pdf,
    create_payment_deadline_events, convert_currency, update_exchange_rates
)
import json

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_client_ip(request):
    """Dobij IP adresu klijenta"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================
# PUBLIC VIEWS
# ============================================

def landing(request):
    """Landing page sa pricing"""
    plans = [
        {'name': 'Starter', 'price': 15, 'features': ['Osnovna evidencija', 'Do 50 prihoda/mj', 'Fakture', 'Email podrška']},
        {'name': 'Professional', 'price': 29, 'features': ['Email inbox AI', 'Neograničeno', 'Uplatnice', 'Prioritet']},
        {'name': 'Business', 'price': 49, 'features': ['API pristup', 'Bilans', 'Custom izvještaji', 'Multi korisnici']},
        {'name': 'Enterprise', 'price': 99, 'features': ['Dedicated podrška', 'Integracije', 'SLA', 'White label']}
    ]
    
    promo_codes = {
        'EARLYBIRD100': {'discount': 1.0, 'description': '6 mjeseci BESPLATNO'},
        'REFERRAL20': {'discount': 0.2, 'description': '20% OFF zauvijek'},
        'FRIEND50': {'discount': 0.5, 'description': '50% OFF 3 mjeseca'},
        'LAUNCH2026': {'discount': 0.3, 'description': '30% OFF 6 mjeseci'}
    }
    
    return render(request, 'core/landing.html', {'plans': plans, 'promo_codes': promo_codes})


def user_login(request):
    """Login stranica"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        
        user = authenticate(request, username=email, password=password)
        
        if user:
            auth_login(request, user)
            
            SystemLog.objects.create(
                user=user,
                action='LOGIN',
                status='success',
                ip_address=get_client_ip(request)
            )
            
            if user.is_staff:
                return redirect('admin_panel')
            return redirect('dashboard')
        else:
            return render(request, 'core/login.html', {'error': 'Pogrešan email ili lozinka'})
    
    return render(request, 'core/login.html')


def user_logout(request):
    """Logout"""
    auth_logout(request)
    return redirect('landing')


# ============================================
# LANGUAGE & PREFERENCES
# ============================================

@login_required
def change_language(request, lang_code):
    """Promijeni jezik aplikacije"""
    if lang_code in ['sr', 'en']:
        activate(lang_code)
        request.session['django_language'] = lang_code
        
        prefs, created = UserPreferences.objects.get_or_create(korisnik=request.user.korisnik)
        prefs.language = lang_code
        prefs.save()
    
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def preferences_view(request):
    """Korisničke preferencije"""
    prefs, created = UserPreferences.objects.get_or_create(korisnik=request.user.korisnik)
    
    if request.method == 'POST':
        prefs.language = request.POST.get('language', 'sr')
        prefs.theme = request.POST.get('theme', 'light')
        prefs.email_notifications = request.POST.get('email_notifications') == 'on'
        prefs.payment_reminders = request.POST.get('payment_reminders') == 'on'
        prefs.save()
        
        return JsonResponse({'success': True})


# ============================================
# REGISTRATION FLOW
# ============================================

def features_page(request):
    """Features page"""
    return render(request, 'core/features.html')


def register_choose_plan(request):
    """Step 1: Odabir plana"""
    plans = [
        {'name': 'Starter', 'price': 15, 'features': ['Osnovna evidencija', 'Fakture', 'Email podrška']},
        {'name': 'Professional', 'price': 29, 'features': ['Email inbox AI', 'Uplatnice', 'Prioritet']},
        {'name': 'Business', 'price': 49, 'features': ['API pristup', 'Bilans', 'Custom izvještaji']},
        {'name': 'Enterprise', 'price': 99, 'features': ['Dedicated podrška', 'Integracije', 'SLA']}
    ]
    return render(request, 'core/register_choose_plan.html', {'plans': plans})


def register(request):
    """Step 2: Registracija"""
    selected_plan = request.GET.get('plan', 'Professional')
    plan_prices = {'Starter': 15, 'Professional': 29, 'Business': 49, 'Enterprise': 99}
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if password != password_confirm:
            return render(request, 'core/register.html', {
                'error': 'Lozinke se ne poklapaju',
                'selected_plan': selected_plan
            })
        
        if User.objects.filter(username=email).exists():
            return render(request, 'core/register.html', {
                'error': 'Email već postoji',
                'selected_plan': selected_plan
            })
        
        request.session['registration_data'] = {
            'ime': request.POST.get('ime'),
            'email': email,
            'password': password,
            'jib': request.POST.get('jib'),
            'racun': request.POST.get('racun'),
            'plan': request.POST.get('plan')
        }
        
        return redirect('payment')
    
    return render(request, 'core/register.html', {
        'selected_plan': selected_plan,
        'plan_price': plan_prices.get(selected_plan, 29)
    })


def payment(request):
    """Step 3: Plaćanje"""
    reg_data = request.session.get('registration_data')
    if not reg_data:
        return redirect('register_choose_plan')
    
    plan_prices = {'Starter': 15, 'Professional': 29, 'Business': 49, 'Enterprise': 99}
    plan_name = reg_data.get('plan', 'Professional')
    plan_price = plan_prices.get(plan_name, 29)
    
    if request.method == 'POST':
        user = User.objects.create_user(
            username=reg_data['email'],
            email=reg_data['email'],
            password=reg_data['password']
        )
        
        korisnik = Korisnik.objects.create(
            user=user,
            ime=reg_data['ime'],
            plan=plan_name,
            jib=reg_data['jib'],
            racun=reg_data['racun']
        )
        
        UserPreferences.objects.create(
            korisnik=korisnik,
            email_notifications=True,
            payment_reminders=True
        )
        
        trial_end_date = timezone.now() + timedelta(days=14)
        EmailNotification.objects.create(
            korisnik=korisnik,
            notification_type='payment_reminder',
            scheduled_date=trial_end_date - timedelta(days=2),
            email_subject='Trial period ističe za 2 dana',
            email_body=f'Prvi charge: {plan_price} KM'
        )
        
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        del request.session['registration_data']
        
        request.session['registration_success'] = {
            'plan_name': plan_name,
            'plan_price': plan_price,
            'user_email': user.email
        }
        
        return redirect('registration_success')
    
    return render(request, 'core/payment.html', {
        'plan_name': plan_name,
        'plan_price': plan_price
    })


def registration_success(request):
    """Success page"""
    success_data = request.session.get('registration_success')
    if not success_data:
        return redirect('landing')
    
    context = success_data
    del request.session['registration_success']
    
    return render(request, 'core/registration_success.html', context)


def cancel_subscription(request):
    """Otkaži pretplatu"""
    if request.method == 'POST' and request.user.is_authenticated:
        SystemLog.objects.create(
            user=request.user,
            action='CANCEL_SUBSCRIPTION',
            status='success'
        )
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    return render(request, 'core/preferences.html', {'prefs': prefs})


# ============================================
# DASHBOARD
# ============================================

@login_required
def dashboard(request):
    """Enhanced dashboard sa Chart.js i AI predikcijama"""
    korisnik = request.user.korisnik
    
    # Statistike
    prihodi = korisnik.prihodi.all()
    ukupan_prihod = sum([p.iznos for p in prihodi])
    porez = ukupan_prihod * Decimal(str(settings.STOPA_POREZA))
    doprinosi = Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal(str(settings.STOPA_DOPRINOSA)) * len(prihodi)
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
        'korisnik': korisnik,
        'stats': {
            'ukupno': ukupan_prihod,
            'porez': porez,
            'doprinosi': doprinosi,
            'neto': neto
        },
        'chart_data': json.dumps(chart_data),
        'predictions': predictions,
        'pred_labels': json.dumps(pred_labels),
        'pred_values': json.dumps(pred_values),
        'pred_confidence': json.dumps(pred_confidence),
        'inbox_count': korisnik.inbox.filter(potvrdjeno=False).count(),
        'fakture_count': korisnik.fakture.count(),
        'uplatnice_count': korisnik.uplatnice.count()
    }
    
    return render(request, 'core/dashboard.html', context)


# ============================================
# PRIHODI I RASHODI
# ============================================

@login_required
def prihodi_view(request):
    """Prikaz prihoda i rashoda"""
    korisnik = request.user.korisnik
    prihodi = korisnik.prihodi.all()
    
    mjesecni_podaci = []
    ukupan_prihod = Decimal('0')
    ukupan_porez = Decimal('0')
    ukupni_doprinosi = Decimal('0')
    
    for prihod in prihodi:
        porez = prihod.iznos * Decimal(str(settings.STOPA_POREZA))
        doprinosi = Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal(str(settings.STOPA_DOPRINOSA))
        ukupni_rashodi = porez + doprinosi
        neto = prihod.iznos - ukupni_rashodi
        
        mjesecni_podaci.append({
            'mjesec': prihod.mjesec,
            'prihod': prihod.iznos,
            'porez': porez,
            'doprinosi': doprinosi,
            'rashodi': ukupni_rashodi,
            'neto': neto
        })
        
        ukupan_prihod += prihod.iznos
        ukupan_porez += porez
        ukupni_doprinosi += doprinosi
    
    context = {
        'mjesecni_podaci': mjesecni_podaci,
        'totali': {
            'prihod': ukupan_prihod,
            'porez': ukupan_porez,
            'doprinosi': ukupni_doprinosi,
            'rashodi': ukupan_porez + ukupni_doprinosi,
            'neto': ukupan_prihod - ukupan_porez - ukupni_doprinosi
        }
    }
    
    return render(request, 'core/prihodi.html', context)


# ============================================
# EMAIL INBOX
# ============================================

@login_required
def inbox_view(request):
    """Email inbox - AI parsing"""
    korisnik = request.user.korisnik
    
    if korisnik.plan not in ['Professional', 'Business', 'Enterprise']:
        return redirect('dashboard')
    
    if request.method == 'POST' and 'confirm_all' in request.POST:
        inbox_items = korisnik.inbox.filter(potvrdjeno=False)
        count = inbox_items.count()
        
        for item in inbox_items:
            item.potvrdjeno = True
            item.save()
        
        SystemLog.objects.create(
            user=request.user,
            action='EMAIL_IMPORT',
            status='success',
            ip_address=get_client_ip(request),
            details=f'Uvezeno {count} transakcija'
        )
        
        return JsonResponse({'success': True, 'count': count})
    
    inbox = korisnik.inbox.filter(potvrdjeno=False)
    return render(request, 'core/inbox.html', {'inbox': inbox})


# ============================================
# FAKTURE
# ============================================

@login_required
def fakture_view(request):
    """Prikaz i kreiranje faktura"""
    korisnik = request.user.korisnik
    
    if request.method == 'POST':
        # Rate limiting check
        allowed, error = check_rate_limit(request.user, 'GENERATE_INVOICE', limit=10, period_minutes=60)
        if not allowed:
            return JsonResponse({'error': error}, status=429)
        
        faktura = Faktura.objects.create(
            korisnik=korisnik,
            broj=request.POST.get('broj'),
            datum=request.POST.get('datum'),
            klijent=request.POST.get('klijent'),
            iznos=Decimal(request.POST.get('iznos')),
            opis=request.POST.get('opis', '')
        )
        
        # Generiši Word dokument
        doc_file = generate_invoice_doc(faktura, korisnik)
        faktura.fajl = doc_file
        faktura.save()
        
        # Audit log
        log_audit(
            user=request.user,
            model_name='Faktura',
            object_id=faktura.id,
            action='CREATE',
            new_value={'broj': faktura.broj, 'klijent': faktura.klijent, 'iznos': str(faktura.iznos)},
            request=request
        )
        
        SystemLog.objects.create(
            user=request.user,
            action='GENERATE_INVOICE',
            status='success',
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({'success': True, 'file_url': faktura.fajl.url})
    
    fakture = korisnik.fakture.all()
    return render(request, 'core/fakture.html', {'fakture': fakture})


@login_required
def download_invoice(request, faktura_id):
    """Preuzmi postojeću fakturu"""
    faktura = get_object_or_404(Faktura, id=faktura_id, korisnik=request.user.korisnik)
    
    if faktura.fajl:
        return FileResponse(faktura.fajl.open('rb'), as_attachment=True)
    else:
        doc_file = generate_invoice_doc(faktura, request.user.korisnik)
        faktura.fajl = doc_file
        faktura.save()
        return FileResponse(faktura.fajl.open('rb'), as_attachment=True)


# ============================================
# UPLATNICE
# ============================================

@login_required
def uplatnice_view(request):
    """Prikaz i kreiranje uplatnica"""
    korisnik = request.user.korisnik
    
    if request.method == 'POST':
        uplatnica = Uplatnica.objects.create(
            korisnik=korisnik,
            datum=timezone.now().date(),
            primalac=request.POST.get('primalac'),
            iznos=Decimal(request.POST.get('iznos')),
            svrha=request.POST.get('svrha', 'Porez na dohodak'),
            poziv_na_broj=request.POST.get('poziv', '')
        )
        
        # Generiši PNG uplatnicu
        png_file = generate_payment_slip_png(uplatnica, korisnik)
        uplatnica.fajl = png_file
        uplatnica.save()
        
        log_audit(
            user=request.user,
            model_name='Uplatnica',
            object_id=uplatnica.id,
            action='CREATE',
            new_value={'primalac': uplatnica.primalac, 'iznos': str(uplatnica.iznos)},
            request=request
        )
        
        SystemLog.objects.create(
            user=request.user,
            action='GENERATE_PAYMENT',
            status='success',
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({'success': True, 'file_url': uplatnica.fajl.url})
    
    uplatnice = korisnik.uplatnice.all()
    return render(request, 'core/uplatnice.html', {'uplatnice': uplatnice})


@login_required
def download_payment(request, uplatnica_id):
    """Preuzmi postojeću uplatnicu"""
    uplatnica = get_object_or_404(Uplatnica, id=uplatnica_id, korisnik=request.user.korisnik)
    
    if uplatnica.fajl:
        return FileResponse(uplatnica.fajl.open('rb'), as_attachment=True)
    else:
        png_file = generate_payment_slip_png(uplatnica, request.user.korisnik)
        uplatnica.fajl = png_file
        uplatnica.save()
        return FileResponse(uplatnica.fajl.open('rb'), as_attachment=True)


# ============================================
# BILANS
# ============================================

@login_required
def bilans_view(request):
    """Bilans uspjeha"""
    korisnik = request.user.korisnik
    
    if korisnik.plan not in ['Business', 'Enterprise']:
        return redirect('dashboard')
    
    if request.method == 'POST':
        od = request.POST.get('od')
        do = request.POST.get('do')
        
        # Kalkulacije
        prihodi = korisnik.prihodi.filter(mjesec__gte=od, mjesec__lte=do)
        ukupan_prihod = sum([p.iznos for p in prihodi])
        porez = ukupan_prihod * Decimal(str(settings.STOPA_POREZA))
        doprinosi = Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal(str(settings.STOPA_DOPRINOSA)) * prihodi.count()
        neto = ukupan_prihod - porez - doprinosi
        
        bilans = Bilans.objects.create(
            korisnik=korisnik,
            od_mjesec=od,
            do_mjesec=do,
            ukupan_prihod=ukupan_prihod,
            porez=porez,
            doprinosi=doprinosi,
            neto=neto
        )
        
        csv_file = generate_bilans_csv(bilans, korisnik, prihodi)
        bilans.fajl = csv_file
        bilans.save()
        
        SystemLog.objects.create(
            user=request.user,
            action='EXPORT_BILANS_CSV',
            status='success',
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({'success': True, 'file_url': bilans.fajl.url})
    
    bilansi = korisnik.bilansi.filter(datum_isteka__gt=timezone.now())
    
    return render(request, 'core/bilans.html', {
        'bilansi': bilansi,
        'retention_days': korisnik.get_retention_days()
    })


@login_required
def download_bilans(request, bilans_id):
    """Preuzmi sačuvani bilans"""
    bilans = get_object_or_404(Bilans, id=bilans_id, korisnik=request.user.korisnik)
    
    if bilans.is_expired():
        return JsonResponse({'error': 'Bilans je istekao'}, status=410)
    
    return FileResponse(bilans.fajl.open('rb'), as_attachment=True)


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
        porez = ukupan_prihod * Decimal('0.02')
        doprinosi = Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal('0.70') * prihodi.count()
        neto = ukupan_prihod - porez - doprinosi
        
        fakture = korisnik.fakture.filter(datum__year=godina)
        klijenti = fakture.values_list('klijent', flat=True).distinct().count()
        
        izvjestaj = GodisnjiIzvjestaj.objects.create(
            korisnik=korisnik,
            godina=godina,
            ukupan_prihod=ukupan_prihod,
            ukupan_porez=porez,
            ukupni_doprinosi=doprinosi,
            neto_dohodak=neto,
            broj_faktura=fakture.count(),
            broj_klijenata=klijenti
        )
        
        pdf_buffer = generate_godisnji_izvjestaj_pdf(korisnik, godina)
        izvjestaj.fajl_pdf.save(
            f'godisnji-izvjestaj-{godina}.pdf',
            ContentFile(pdf_buffer.read())
        )
    
    return FileResponse(izvjestaj.fajl_pdf.open('rb'), as_attachment=True)


# ============================================
# BULK UPLOAD
# ============================================

@login_required
@require_http_methods(["POST"])
def bulk_upload_documents(request):
    """Bulk upload PDF faktura sa OCR parsing"""
    allowed, error = check_rate_limit(request.user, 'BULK_UPLOAD', limit=5, period_minutes=60)
    if not allowed:
        return JsonResponse({'error': error}, status=429)
    
    files = request.FILES.getlist('documents')
    korisnik = request.user.korisnik
    
    results = []
    
    for file in files:
        doc = UploadedDocument.objects.create(
            korisnik=korisnik,
            document_type='invoice',
            file=file,
            original_filename=file.name
        )
        
        extracted = process_uploaded_pdf(doc)
        
        results.append({
            'filename': file.name,
            'extracted': extracted,
            'doc_id': doc.id
        })
        
        log_audit(
            user=request.user,
            model_name='UploadedDocument',
            object_id=doc.id,
            action='CREATE',
            new_value={'filename': file.name},
            request=request
        )
    
    SystemLog.objects.create(
        user=request.user,
        action='BULK_UPLOAD',
        status='success',
        ip_address=get_client_ip(request),
        details=f'Uploaded {len(files)} documents'
    )
    
    return JsonResponse({'success': True, 'results': results})


# ============================================
# CALENDAR
# ============================================

@login_required
def calendar_view(request):
    """Kalendar view sa svim događajima"""
    korisnik = request.user.korisnik
    
    current_year = timezone.now().year
    create_payment_deadline_events(korisnik, current_year)
    
    events = korisnik.calendar_events.all()
    
    calendar_events = []
    for event in events:
        calendar_events.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_date.isoformat(),
            'end': event.end_date.isoformat() if event.end_date else event.start_date.isoformat(),
            'allDay': event.all_day,
            'description': event.description,
            'color': '#3b82f6' if event.event_type == 'payment_deadline' else '#8b5cf6'
        })
    
    return render(request, 'core/calendar.html', {'events': json.dumps(calendar_events)})


# ============================================
# ANALYTICS
# ============================================

@login_required
def analytics_view(request):
    """Napredna analitika"""
    korisnik = request.user.korisnik
    
    from django.db.models import Sum, Count
    
    top_klijenti = korisnik.fakture.values('klijent').annotate(
        total=Sum('iznos'),
        count=Count('id')
    ).order_by('-total')[:5]
    
    from django.db.models.functions import ExtractMonth
    mjesecna_statistika = korisnik.prihodi.annotate(
        month=ExtractMonth('mjesec')
    ).values('month').annotate(
        avg_income=models.Avg('iznos')
    ).order_by('month')
    
    ukupno_ponuda = 100
    placene_fakture = korisnik.fakture.filter(status='Plaćena').count()
    conversion_rate = (placene_fakture / ukupno_ponuda * 100) if ukupno_ponuda > 0 else 0
    
    context = {
        'top_klijenti': top_klijenti,
        'mjesecna_statistika': list(mjesecna_statistika),
        'conversion_rate': conversion_rate,
        'predictions': korisnik.predictions.all()[:3]
    }
    
    return render(request, 'core/analytics.html', context)


# ============================================
# CURRENCY CONVERTER
# ============================================

@login_required
def currency_converter_view(request):
    """Konverter valuta"""
    currencies = Currency.objects.all()
    
    result = None
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        from_curr = request.POST.get('from_currency')
        to_curr = request.POST.get('to_currency')
        
        result = convert_currency(amount, from_curr, to_curr)
    
    return render(request, 'core/currency_converter.html', {
        'currencies': currencies,
        'result': result
    })


# ============================================
# EXPORT DATA
# ============================================

@login_required
def export_all_data(request):
    """Export svih podataka korisnika (GDPR compliance)"""
    korisnik = request.user.korisnik
    
    data = {
        'korisnik': {
            'ime': korisnik.ime,
            'email': korisnik.user.email,
            'plan': korisnik.plan,
            'jib': korisnik.jib,
            'racun': korisnik.racun,
            'registrovan': korisnik.registrovan.isoformat()
        },
        'prihodi': list(korisnik.prihodi.values()),
        'fakture': list(korisnik.fakture.values('broj', 'datum', 'klijent', 'iznos', 'status', 'opis')),
        'uplatnice': list(korisnik.uplatnice.values()),
        'bilansi': list(korisnik.bilansi.values()),
    }
    
    json_data = json.dumps(data, indent=2, default=str, ensure_ascii=False)
    
    response = HttpResponse(json_data, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="epausa-export-{korisnik.ime}.json"'
    
    return response


# ============================================
# ADMIN PANEL
# ============================================

@login_required
def admin_panel(request):
    """Admin panel"""
    if not request.user.is_staff:
        return redirect('dashboard')
    
    tab = request.GET.get('tab', 'users')
    
    korisnici = Korisnik.objects.all()
    logs = SystemLog.objects.all()[:100]
    failed = FailedRequest.objects.all()
    
    context = {
        'korisnici': korisnici,
        'logs': logs,
        'failed_requests': failed,
        'active_tab': tab
    }
    
    return render(request, 'core/admin_panel.html', context)


@login_required
def admin_login_as(request, user_id):
    """Admin login kao drugi korisnik"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    target_user = get_object_or_404(User, id=user_id)
    
    auth_logout(request)
    auth_login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
    
    return redirect('dashboard')


@login_required
@require_http_methods(["POST"])
def retry_failed_request(request, request_id):
    """Retry failed request"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    failed_req = get_object_or_404(FailedRequest, id=request_id)
    
    import random
    if random.random() > 0.5:
        SystemLog.objects.create(
            user=failed_req.user,
            action=f"{failed_req.action}_RETRY",
            status='success',
            ip_address=get_client_ip(request)
        )
        failed_req.delete()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'Retry neuspješan'})


@login_required
@require_http_methods(["POST"])
def skip_failed_request(request, request_id):
    """Skip failed request"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    failed_req = get_object_or_404(FailedRequest, id=request_id)
    failed_req.delete()
    
    return JsonResponse({'success': True})