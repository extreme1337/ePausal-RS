# DODAJ OVE VIEWS u views.py ili kreiraj views_registration.py

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.utils import timezone
from datetime import timedelta
from .models import Korisnik, UserPreferences, EmailNotification
from decimal import Decimal

def features_page(request):
    """Features page - objašnjava sve funkcionalnosti"""
    return render(request, 'core/features.html')


def register_choose_plan(request):
    """Step 1: Odabir plana"""
    plans = [
        {'name': 'Starter', 'price': 15, 'features': ['Osnovna evidencija', 'Do 50 prihoda/mj', 'Fakture', 'Email podrška']},
        {'name': 'Professional', 'price': 29, 'features': ['Email inbox AI', 'Neograničeno', 'Uplatnice', 'Prioritet']},
        {'name': 'Business', 'price': 49, 'features': ['API pristup', 'Bilans', 'Custom izvještaji']},
        {'name': 'Enterprise', 'price': 99, 'features': ['Dedicated podrška', 'Integracije', 'SLA']}
    ]
    
    return render(request, 'core/register_choose_plan.html', {'plans': plans})


def register(request):
    """Step 2: Registracija - osnovni i poslovni podaci"""
    selected_plan = request.GET.get('plan', 'Professional')
    
    # Pricing info
    plan_prices = {
        'Starter': 15,
        'Professional': 29,
        'Business': 49,
        'Enterprise': 99
    }
    
    if request.method == 'POST':
        # Validacija
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
        
        # Sačuvaj u session za Step 3
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
    """Step 3: Plaćanje i aktivacija trial-a"""
    
    # Get data from session
    reg_data = request.session.get('registration_data')
    
    if not reg_data:
        return redirect('register_choose_plan')
    
    plan_prices = {
        'Starter': 15,
        'Professional': 29,
        'Business': 49,
        'Enterprise': 99
    }
    
    plan_name = reg_data.get('plan', 'Professional')
    plan_price = plan_prices.get(plan_name, 29)
    
    if request.method == 'POST':
        # U produkciji ovde ide Stripe payment intent
        # Za sada samo kreiramo korisnika
        
        # Create user
        user = User.objects.create_user(
            username=reg_data['email'],
            email=reg_data['email'],
            password=reg_data['password'],
            first_name=reg_data['ime'].split()[0] if reg_data['ime'] else '',
            last_name=' '.join(reg_data['ime'].split()[1:]) if len(reg_data['ime'].split()) > 1 else ''
        )
        
        # Create Korisnik profile
        korisnik = Korisnik.objects.create(
            user=user,
            ime=reg_data['ime'],
            plan=plan_name,
            jib=reg_data['jib'],
            racun=reg_data['racun']
        )
        
        # Create preferences
        UserPreferences.objects.create(
            korisnik=korisnik,
            email_notifications=True,
            payment_reminders=True
        )
        
        # Schedule first payment notification (14 dana)
        trial_end_date = timezone.now() + timedelta(days=14)
        
        EmailNotification.objects.create(
            korisnik=korisnik,
            notification_type='payment_reminder',
            scheduled_date=trial_end_date - timedelta(days=2),  # 2 dana prije
            email_subject='Trial period ističe za 2 dana',
            email_body=f'Vaš trial period ističe {trial_end_date.strftime("%d.%m.%Y")}. Prvi charge će biti {plan_price} KM.'
        )
        
        # Auto login
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Clear session
        del request.session['registration_data']
        
        # Redirect to success
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
    """Success page nakon registracije"""
    success_data = request.session.get('registration_success')
    
    if not success_data:
        return redirect('landing')
    
    context = success_data
    
    # Clear session
    del request.session['registration_success']
    
    return render(request, 'core/registration_success.html', context)


def cancel_subscription(request):
    """Otkaži pretplatu"""
    if request.method == 'POST' and request.user.is_authenticated:
        korisnik = request.user.korisnik
        
        # U produkciji ovde ide Stripe subscription cancel
        # stripe.Subscription.delete(korisnik.stripe_subscription_id)
        
        # Za sada samo log
        from .models import SystemLog
        SystemLog.objects.create(
            user=request.user,
            action='CANCEL_SUBSCRIPTION',
            status='success',
            details=f'Plan: {korisnik.plan}'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Pretplata otkazana. Zadnji dan pristupa: ' + (timezone.now() + timedelta(days=14)).strftime('%d.%m.%Y')
        })
    
    return JsonResponse({'error': 'Unauthorized'}, status=403)