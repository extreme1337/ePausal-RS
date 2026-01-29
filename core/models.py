from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.validators import MinValueValidator
import json

# ============================================
# OSNOVNI MODELI (OSTAJU ISTI)
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
    VRSTA_CHOICES = [
        ('prihod', 'Prihod'),
        ('rashod', 'Rashod'),
    ]
    
    korisnik = models.ForeignKey(Korisnik, on_delete=models.CASCADE, related_name='prihodi')
    mjesec = models.CharField(max_length=7)  # Format: 2025-01
    datum = models.DateField(null=True, blank=True)  # NOVO - tačan datum transakcije
    iznos = models.DecimalField(max_digits=10, decimal_places=2)
    vrsta = models.CharField(max_length=10, choices=VRSTA_CHOICES, default='prihod')  # NOVO
    opis = models.CharField(max_length=500, blank=True)  # NOVO
    izvod_fajl = models.FileField(upload_to='izvodi/', blank=True, null=True)  # NOVO - PDF izvoda
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        znak = '+' if self.vrsta == 'prihod' else '-'
        return f"{znak}{self.iznos} KM - {self.opis[:50]}"
    
    class Meta:
        ordering = ['-datum', '-mjesec']
        verbose_name_plural = "Prihodi i Rashodi"


# ============================================
# FAKTURE - POJEDNOSTAVLJEN SISTEM (SAMO TEKST)
# ============================================

class Faktura(models.Model):
    """Pojednostavljena faktura - sve podatke korisnik unosi direktno"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fakture')
    
    # Osnovni podaci
    broj_fakture = models.CharField(max_length=50, verbose_name="Broj fakture")
    datum_izdavanja = models.DateField(verbose_name="Datum izdavanja")
    mjesto_izdavanja = models.CharField(max_length=200, blank=True, verbose_name="Mjesto izdavanja")
    
    # IZDAVALAC - Tekstualna polja (korisnik unosi svaki put)
    izdavalac_naziv = models.CharField(max_length=300, verbose_name="Naziv izdavaoca")
    izdavalac_adresa = models.CharField(max_length=300, verbose_name="Adresa izdavaoca")
    izdavalac_mjesto = models.CharField(max_length=200, verbose_name="Mjesto izdavaoca")
    izdavalac_jib = models.CharField(max_length=20, blank=True, verbose_name="JIB izdavaoca")
    izdavalac_iban = models.CharField(max_length=50, blank=True, verbose_name="IBAN izdavaoca")
    izdavalac_racun = models.CharField(max_length=50, blank=True, verbose_name="Račun izdavaoca")
    
    # PRIMALAC - Tekstualna polja (korisnik unosi svaki put)
    primalac_naziv = models.CharField(max_length=300, verbose_name="Naziv primaoca")
    primalac_adresa = models.CharField(max_length=300, verbose_name="Adresa primaoca")
    primalac_mjesto = models.CharField(max_length=200, verbose_name="Mjesto primaoca")
    
    # Napomene
    napomena = models.TextField(verbose_name="Napomena", blank=True)
    
    # Valuta
    VALUTA_CHOICES = [
        ('BAM', 'KM'),
        ('EUR', 'EUR'),
        ('USD', 'USD'),
    ]
    valuta = models.CharField(max_length=3, choices=VALUTA_CHOICES, default='USD', verbose_name="Valuta")
    
    # Automatski računati iznosi
    ukupno_bez_pdv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Ukupno bez PDV")
    pdv_iznos = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Iznos PDV")
    ukupno_sa_pdv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Ukupno sa PDV")
    
    # Status
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('issued', 'Izdato'),
        ('paid', 'Plaćeno'),
        ('cancelled', 'Stornirano'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Status")
    
    # Datumi
    datum_placanja = models.DateField(verbose_name="Datum plaćanja", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'faktura'
        verbose_name = 'Faktura'
        verbose_name_plural = 'Fakture'
        ordering = ['-datum_izdavanja', '-broj_fakture']
        unique_together = ['user', 'broj_fakture']
    
    def __str__(self):
        return f"Faktura {self.broj_fakture} - {self.primalac_naziv}"
    
    def izracunaj_ukupno(self):
        """Izračunava ukupne iznose fakture"""
        stavke = self.stavke.all()
        
        ukupno_bez_pdv = sum(stavka.ukupna_cijena for stavka in stavke)
        pdv_iznos = sum(stavka.pdv_iznos for stavka in stavke)
        ukupno_sa_pdv = ukupno_bez_pdv + pdv_iznos
        
        self.ukupno_bez_pdv = ukupno_bez_pdv
        self.pdv_iznos = pdv_iznos
        self.ukupno_sa_pdv = ukupno_sa_pdv
        self.save()
        
        return {
            'ukupno_bez_pdv': ukupno_bez_pdv,
            'pdv_iznos': pdv_iznos,
            'ukupno_sa_pdv': ukupno_sa_pdv,
        }


class StavkaFakture(models.Model):
    """Stavka fakture"""
    faktura = models.ForeignKey(Faktura, on_delete=models.CASCADE, related_name='stavke', verbose_name="Faktura")
    redni_broj = models.PositiveIntegerField(verbose_name="Redni broj")
    
    # Opis proizvoda/usluge
    opis = models.CharField(max_length=500, verbose_name="Opis")
    
    # Jedinica mjere - jednostavno tekstualno polje
    jedinica_mjere = models.CharField(max_length=50, default='unit', verbose_name="Jedinica mjere")
    
    # Količina i cijena
    kolicina = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Količina"
    )
    cijena_po_jedinici = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Cijena po jedinici"
    )
    
    # PDV stopa (0 za USD fakture)
    pdv_stopa = models.IntegerField(default=0, verbose_name="PDV stopa")
    
    # Automatski računati iznosi
    ukupna_cijena = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Ukupna cijena bez PDV")
    pdv_iznos = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="PDV iznos")
    ukupna_cijena_sa_pdv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Ukupna cijena sa PDV")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stavka_fakture'
        verbose_name = 'Stavka fakture'
        verbose_name_plural = 'Stavke fakture'
        ordering = ['redni_broj']
    
    def __str__(self):
        return f"{self.redni_broj}. {self.opis}"
    
    def save(self, *args, **kwargs):
        """Override save da automatski računa iznose"""
        self.ukupna_cijena = self.kolicina * self.cijena_po_jedinici
        self.pdv_iznos = self.ukupna_cijena * (Decimal(self.pdv_stopa) / Decimal(100))
        self.ukupna_cijena_sa_pdv = self.ukupna_cijena + self.pdv_iznos
        
        super().save(*args, **kwargs)
        
        # Ažuriraj ukupne iznose fakture
        self.faktura.izracunaj_ukupno()


# ============================================
# OSTALI MODELI (OSTAJU ISTI)
# ============================================

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
    confidence = models.IntegerField(default=95)
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


class Currency(models.Model):
    """Valute i exchange rates"""
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    rate_to_km = models.DecimalField(max_digits=10, decimal_places=4)
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
    action = models.CharField(max_length=20)
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
    mjesec = models.CharField(max_length=7)
    predicted_income = models.DecimalField(max_digits=10, decimal_places=2)
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
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
    godina = models.IntegerField()
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
    """Upload-ovani dokumenti"""
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
    extracted_data = models.JSONField(null=True, blank=True)
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


