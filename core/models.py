from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

# ============================================
# OSNOVNI MODELI
# ============================================

class Korisnik(models.Model):
    PLAN_CHOICES = [
        ('Starter', 'Starter'),
        ('Professional', 'Professional'),
        ('Business', 'Business'),
        ('Enterprise', 'Enterprise'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ime = models.CharField(max_length=200)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='Starter')
    jib = models.CharField(max_length=13)
    racun = models.CharField(max_length=20)
    registrovan = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.ime} ({self.plan})"
    
    def get_retention_days(self):
        retention = {
            'Starter': 30,
            'Professional': 90,
            'Business': 180,
            'Enterprise': 365
        }
        return retention.get(self.plan, 30)
    
    class Meta:
        verbose_name_plural = "Korisnici"


class Prihod(models.Model):
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='prihodi')
    mjesec = models.CharField(max_length=7)  # Format: 2025-01
    iznos = models.DecimalField(max_digits=10, decimal_places=2)
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.mjesec}: {self.iznos} KM"
    
    class Meta:
        ordering = ['mjesec']
        verbose_name_plural = "Prihodi"


class Faktura(models.Model):
    STATUS_CHOICES = [
        ('Na čekanju', 'Na čekanju'),
        ('Plaćena', 'Plaćena'),
    ]
    
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='fakture')
    broj = models.CharField(max_length=20)
    datum = models.DateField()
    klijent = models.CharField(max_length=200)
    iznos = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Na čekanju')
    opis = models.TextField(blank=True)
    fajl = models.FileField(upload_to='invoices/', blank=True, null=True)
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.broj} - {self.klijent}"
    
    class Meta:
        ordering = ['-datum']
        verbose_name_plural = "Fakture"


class Uplatnica(models.Model):
    PRIMALAC_CHOICES = [
        ('PURS', 'Poreska uprava RS'),
        ('FZO RS', 'Fond zdravstva RS'),
    ]
    
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='uplatnice')
    datum = models.DateField()
    primalac = models.CharField(max_length=20, choices=PRIMALAC_CHOICES)
    iznos = models.DecimalField(max_digits=10, decimal_places=2)
    svrha = models.CharField(max_length=200)
    poziv_na_broj = models.CharField(max_length=50, blank=True)
    fajl = models.FileField(upload_to='payments/', blank=True, null=True)
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.datum} - {self.primalac} - {self.iznos} KM"
    
    class Meta:
        ordering = ['-datum']
        verbose_name_plural = "Uplatnice"


class Bilans(models.Model):
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='bilansi')
    od_mjesec = models.CharField(max_length=7)
    do_mjesec = models.CharField(max_length=7)
    ukupan_prihod = models.DecimalField(max_digits=10, decimal_places=2)
    porez = models.DecimalField(max_digits=10, decimal_places=2)
    doprinosi = models.DecimalField(max_digits=10, decimal_places=2)
    neto = models.DecimalField(max_digits=10, decimal_places=2)
    fajl = models.FileField(upload_to='bilans/')
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    datum_isteka = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.datum_isteka:
            retention = self.korisnik.get_retention_days()
            self.datum_isteka = timezone.now() + timedelta(days=retention)
        super().save(*args, **kwargs)
    
    def days_until_expiry(self):
        return (self.datum_isteka - timezone.now()).days
    
    def is_expired(self):
        return timezone.now() > self.datum_isteka
    
    def __str__(self):
        return f"{self.od_mjesec} - {self.do_mjesec}"
    
    class Meta:
        ordering = ['-datum_kreiranja']
        verbose_name_plural = "Bilansi"


class EmailInbox(models.Model):
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='inbox')
    from_email = models.EmailField()
    klijent = models.CharField(max_length=200)
    iznos = models.DecimalField(max_digits=10, decimal_places=2)
    svrha = models.CharField(max_length=200)
    datum_transakcije = models.DateField()
    confidence = models.IntegerField(default=95)  # AI confidence %
    potvrdjeno = models.BooleanField(default=False)
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.klijent} - {self.iznos} KM"
    
    class Meta:
        ordering = ['-datum_transakcije']
        verbose_name_plural = "Email Inbox"


class SystemLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.timestamp} - {self.action}"
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "System Logs"


class FailedRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    error = models.TextField()
    retryable = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} - {self.error}"
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Failed Requests"


# ============================================
# ENHANCED MODELI (NOVI FEATURES)
# ============================================

class Currency(models.Model):
    """Valute i exchange rates"""
    code = models.CharField(max_length=3, unique=True)  # EUR, USD, GBP
    name = models.CharField(max_length=50)
    rate_to_km = models.DecimalField(max_digits=10, decimal_places=4)  # Kurs prema KM
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.rate_to_km} KM"
    
    class Meta:
        verbose_name_plural = "Currencies"


class UserPreferences(models.Model):
    """Korisničke preferencije"""
    LANGUAGE_CHOICES = [
        ('sr', 'Srpski'),
        ('en', 'English'),
    ]
    
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]
    
    korisnik = models.OneToOneField(Korisnik, on_delete=models.CASCADE, related_name='preferences')
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='sr')
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    default_currency = models.ForeignKey(Currency, on_delete=models.SET_NULL, null=True, blank=True)
    email_notifications = models.BooleanField(default=True)
    payment_reminders = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.korisnik.ime} - Preferences"
    
    class Meta:
        verbose_name_plural = "User Preferences"


class AuditLog(models.Model):
    """Audit trail za sve promjene"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    model_name = models.CharField(max_length=100)
    object_id = models.IntegerField()
    action = models.CharField(max_length=20)  # CREATE, UPDATE, DELETE
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} {self.model_name} by {self.user}"
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Audit Logs"


class PredictiveAnalytics(models.Model):
    """ML predikcije za prihode"""
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='predictions')
    mjesec = models.CharField(max_length=7)  # 2025-11
    predicted_income = models.DecimalField(max_digits=10, decimal_places=2)
    confidence = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100%
    actual_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.mjesec}: {self.predicted_income} KM ({self.confidence}%)"
    
    class Meta:
        ordering = ['mjesec']
        verbose_name_plural = "Predictive Analytics"


class GodisnjiIzvjestaj(models.Model):
    """Godišnji izvještaj za PURS"""
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='godisnji_izvjestaji')
    godina = models.IntegerField()  # 2025
    ukupan_prihod = models.DecimalField(max_digits=12, decimal_places=2)
    ukupan_porez = models.DecimalField(max_digits=12, decimal_places=2)
    ukupni_doprinosi = models.DecimalField(max_digits=12, decimal_places=2)
    neto_dohodak = models.DecimalField(max_digits=12, decimal_places=2)
    broj_faktura = models.IntegerField()
    broj_klijenata = models.IntegerField()
    fajl_pdf = models.FileField(upload_to='godisnji_izvjestaji/')
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Godišnji izvještaj {self.godina} - {self.korisnik.ime}"
    
    class Meta:
        ordering = ['-godina']
        verbose_name_plural = "Godišnji izvještaji"
        unique_together = ['korisnik', 'godina']


class EmailNotification(models.Model):
    """Zakazane email notifikacije"""
    NOTIFICATION_TYPES = [
        ('payment_reminder', 'Podsjetnik za plaćanje'),
        ('invoice_due', 'Faktura dospjeva'),
        ('monthly_summary', 'Mjesečni izvještaj'),
        ('annual_report', 'Godišnji izvještaj'),
    ]
    
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    scheduled_date = models.DateTimeField()
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    email_subject = models.CharField(max_length=200)
    email_body = models.TextField()
    
    def __str__(self):
        return f"{self.notification_type} - {self.korisnik.ime}"
    
    class Meta:
        ordering = ['scheduled_date']
        verbose_name_plural = "Email Notifications"


class UploadedDocument(models.Model):
    """Upload-ovani dokumenti (PDF fakture, računi)"""
    DOCUMENT_TYPES = [
        ('invoice', 'Faktura'),
        ('receipt', 'Račun'),
        ('contract', 'Ugovor'),
        ('other', 'Ostalo'),
    ]
    
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='uploaded_docs')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='uploads/')
    original_filename = models.CharField(max_length=255)
    extracted_data = models.JSONField(null=True, blank=True)  # OCR podaci
    processed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.original_filename} ({self.document_type})"
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name_plural = "Uploaded Documents"


class CalendarEvent(models.Model):
    """Kalendar događaja"""
    EVENT_TYPES = [
        ('payment_deadline', 'Rok plaćanja'),
        ('invoice_due', 'Faktura dospjeva'),
        ('meeting', 'Sastanak'),
        ('reminder', 'Podsjetnik'),
    ]
    
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='calendar_events')
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.title} - {self.start_date.strftime('%d.%m.%Y')}"
    
    class Meta:
        ordering = ['start_date']
        verbose_name_plural = "Calendar Events"