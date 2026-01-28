from django.contrib import admin
from .models import (
    Korisnik, Prihod, Faktura, StavkaFakture,
    Uplatnica, Bilans, EmailInbox, SystemLog, FailedRequest,
    Currency, UserPreferences, AuditLog, PredictiveAnalytics,
    GodisnjiIzvjestaj, EmailNotification, UploadedDocument, CalendarEvent
)


# ============================================
# OSNOVNI MODELI
# ============================================

@admin.register(Korisnik)
class KorisnikAdmin(admin.ModelAdmin):
    list_display = ['ime', 'plan', 'jib', 'registrovan']
    list_filter = ['plan', 'registrovan']
    search_fields = ['ime', 'jib', 'user__username', 'user__email']


@admin.register(Prihod)
class PrihodAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'mjesec', 'iznos', 'datum_kreiranja']
    list_filter = ['mjesec', 'datum_kreiranja']
    search_fields = ['korisnik__ime']
    date_hierarchy = 'datum_kreiranja'


# ============================================
# FAKTURE - POJEDNOSTAVLJEN SISTEM
# ============================================

class StavkaFaktureInline(admin.TabularInline):
    """Inline admin za stavke fakture"""
    model = StavkaFakture
    extra = 1
    fields = ['redni_broj', 'opis', 'jedinica_mjere', 'kolicina', 'cijena_po_jedinici', 'pdv_stopa', 'ukupna_cijena']
    readonly_fields = ['ukupna_cijena']


@admin.register(Faktura)
class FakturaAdmin(admin.ModelAdmin):
    list_display = ['broj_fakture', 'primalac_naziv', 'datum_izdavanja', 'ukupno_sa_pdv', 'status', 'created_at']
    list_filter = ['status', 'datum_izdavanja', 'valuta']
    search_fields = ['broj_fakture', 'primalac_naziv', 'izdavalac_naziv']
    date_hierarchy = 'datum_izdavanja'
    inlines = [StavkaFaktureInline]
    
    fieldsets = (
        ('Osnovni podaci', {
            'fields': ('user', 'broj_fakture', 'datum_izdavanja', 'mjesto_izdavanja', 'status')
        }),
        ('Izdavalac', {
            'fields': ('izdavalac_naziv', 'izdavalac_adresa', 'izdavalac_mjesto', 'izdavalac_jib', 'izdavalac_iban', 'izdavalac_racun')
        }),
        ('Primalac', {
            'fields': ('primalac_naziv', 'primalac_adresa', 'primalac_mjesto')
        }),
        ('Finansije', {
            'fields': ('valuta', 'ukupno_bez_pdv', 'pdv_iznos', 'ukupno_sa_pdv', 'datum_placanja')
        }),
        ('Dodatno', {
            'fields': ('napomena',)
        }),
    )
    
    readonly_fields = ['ukupno_bez_pdv', 'pdv_iznos', 'ukupno_sa_pdv']
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.izracunaj_ukupno()


@admin.register(StavkaFakture)
class StavkaFaktureAdmin(admin.ModelAdmin):
    list_display = ['faktura', 'redni_broj', 'opis', 'jedinica_mjere', 'kolicina', 'cijena_po_jedinici', 'ukupna_cijena_sa_pdv']
    list_filter = ['faktura__datum_izdavanja', 'jedinica_mjere']
    search_fields = ['opis', 'faktura__broj_fakture']


# ============================================
# UPLATNICE I BILANSI
# ============================================

@admin.register(Uplatnica)
class UplatnicaAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'datum', 'primalac', 'iznos', 'datum_kreiranja']
    list_filter = ['primalac', 'datum']
    search_fields = ['korisnik__ime', 'svrha']
    date_hierarchy = 'datum'


@admin.register(Bilans)
class BilansAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'od_mjesec', 'do_mjesec', 'ukupan_prihod', 'neto', 'datum_kreiranja', 'days_until_expiry']
    list_filter = ['datum_kreiranja', 'korisnik__plan']
    search_fields = ['korisnik__ime']
    date_hierarchy = 'datum_kreiranja'


@admin.register(EmailInbox)
class EmailInboxAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'klijent', 'iznos', 'datum_transakcije', 'confidence', 'potvrdjeno']
    list_filter = ['potvrdjeno', 'datum_transakcije']
    search_fields = ['klijent', 'from_email', 'korisnik__ime']
    date_hierarchy = 'datum_transakcije'


# ============================================
# SYSTEM LOGS
# ============================================

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'status', 'ip_address', 'timestamp']
    list_filter = ['status', 'action', 'timestamp']
    search_fields = ['user__username', 'action', 'ip_address']
    date_hierarchy = 'timestamp'
    readonly_fields = ['user', 'action', 'status', 'ip_address', 'timestamp', 'details']


@admin.register(FailedRequest)
class FailedRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'retryable', 'timestamp']
    list_filter = ['retryable', 'timestamp']
    search_fields = ['user__username', 'action', 'error']
    date_hierarchy = 'timestamp'


# ============================================
# ENHANCED MODELI
# ============================================

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'rate_to_km', 'last_updated']
    search_fields = ['code', 'name']


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'language', 'theme', 'email_notifications', 'payment_reminders']
    list_filter = ['language', 'theme', 'email_notifications']
    search_fields = ['korisnik__ime']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'model_name', 'object_id', 'action', 'timestamp']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__username', 'model_name']
    date_hierarchy = 'timestamp'
    readonly_fields = ['user', 'model_name', 'object_id', 'action', 'old_value', 'new_value', 'ip_address', 'timestamp']


@admin.register(PredictiveAnalytics)
class PredictiveAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'mjesec', 'predicted_income', 'confidence', 'actual_income', 'accuracy']
    list_filter = ['mjesec', 'created_at']
    search_fields = ['korisnik__ime']


@admin.register(GodisnjiIzvjestaj)
class GodisnjiIzvjestajAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'godina', 'ukupan_prihod', 'ukupan_porez', 'neto_dohodak', 'broj_faktura']
    list_filter = ['godina']
    search_fields = ['korisnik__ime']


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'notification_type', 'scheduled_date', 'sent', 'sent_at']
    list_filter = ['notification_type', 'sent', 'scheduled_date']
    search_fields = ['korisnik__ime', 'email_subject']
    date_hierarchy = 'scheduled_date'


@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'document_type', 'original_filename', 'processed', 'uploaded_at']
    list_filter = ['document_type', 'processed', 'uploaded_at']
    search_fields = ['korisnik__ime', 'original_filename']
    date_hierarchy = 'uploaded_at'


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'event_type', 'title', 'start_date', 'all_day', 'reminder_sent']
    list_filter = ['event_type', 'all_day', 'reminder_sent', 'start_date']
    search_fields = ['korisnik__ime', 'title', 'description']
    date_hierarchy = 'start_date'