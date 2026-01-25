from django.contrib import admin
from .models import *

@admin.register(Korisnik)
class KorisnikAdmin(admin.ModelAdmin):
    list_display = ['ime', 'user', 'plan', 'jib', 'racun', 'registrovan']
    list_filter = ['plan', 'registrovan']
    search_fields = ['ime', 'jib', 'user__email']
    readonly_fields = ['registrovan']
    
    fieldsets = (
        ('Osnovni podaci', {
            'fields': ('user', 'ime', 'plan')
        }),
        ('Finansijski podaci', {
            'fields': ('jib', 'racun')
        }),
        ('Dodatno', {
            'fields': ('registrovan',)
        }),
    )

@admin.register(Prihod)
class PrihodAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'mjesec', 'iznos', 'datum_kreiranja']
    list_filter = ['mjesec', 'korisnik', 'datum_kreiranja']
    search_fields = ['korisnik__ime', 'mjesec']
    readonly_fields = ['datum_kreiranja']
    date_hierarchy = 'datum_kreiranja'

@admin.register(Faktura)
class FakturaAdmin(admin.ModelAdmin):
    list_display = ['broj', 'korisnik', 'datum', 'klijent', 'iznos', 'status', 'datum_kreiranja']
    list_filter = ['status', 'datum', 'korisnik']
    search_fields = ['broj', 'klijent', 'korisnik__ime']
    readonly_fields = ['datum_kreiranja', 'fajl']
    date_hierarchy = 'datum'
    
    fieldsets = (
        ('Osnovni podaci', {
            'fields': ('korisnik', 'broj', 'datum', 'klijent')
        }),
        ('Finansijski podaci', {
            'fields': ('iznos', 'status')
        }),
        ('Dodatno', {
            'fields': ('opis', 'fajl', 'datum_kreiranja')
        }),
    )

@admin.register(Uplatnica)
class UplatnicaAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'datum', 'primalac', 'iznos', 'svrha', 'datum_kreiranja']
    list_filter = ['primalac', 'datum', 'korisnik']
    search_fields = ['korisnik__ime', 'svrha']
    readonly_fields = ['datum_kreiranja', 'fajl']
    date_hierarchy = 'datum'

@admin.register(Bilans)
class BilansAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'od_mjesec', 'do_mjesec', 'ukupan_prihod', 'neto', 'datum_kreiranja', 'datum_isteka', 'is_expired']
    list_filter = ['korisnik', 'datum_kreiranja']
    readonly_fields = ['datum_kreiranja', 'datum_isteka', 'fajl', 'days_until_expiry']
    search_fields = ['korisnik__ime']
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Istekao?'
    
    fieldsets = (
        ('Period', {
            'fields': ('korisnik', 'od_mjesec', 'do_mjesec')
        }),
        ('Finansijski podaci', {
            'fields': ('ukupan_prihod', 'porez', 'doprinosi', 'neto')
        }),
        ('Fajl i datumi', {
            'fields': ('fajl', 'datum_kreiranja', 'datum_isteka', 'days_until_expiry')
        }),
    )

@admin.register(EmailInbox)
class EmailInboxAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'klijent', 'iznos', 'confidence', 'potvrdjeno', 'datum_transakcije', 'datum_kreiranja']
    list_filter = ['potvrdjeno', 'korisnik', 'datum_transakcije']
    search_fields = ['klijent', 'svrha', 'korisnik__ime']
    readonly_fields = ['datum_kreiranja']
    date_hierarchy = 'datum_transakcije'
    
    actions = ['mark_as_confirmed']
    
    def mark_as_confirmed(self, request, queryset):
        count = queryset.update(potvrdjeno=True)
        self.message_user(request, f'{count} transakcija potvrđeno.')
    mark_as_confirmed.short_description = 'Potvrdi odabrane transakcije'

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'status', 'ip_address']
    list_filter = ['status', 'action', 'timestamp']
    search_fields = ['user__email', 'action', 'details']
    readonly_fields = ['timestamp', 'user', 'action', 'status', 'ip_address', 'details']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(FailedRequest)
class FailedRequestAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'error_short', 'retryable']
    list_filter = ['retryable', 'timestamp', 'action']
    search_fields = ['user__email', 'action', 'error']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def error_short(self, obj):
        return obj.error[:50] + '...' if len(obj.error) > 50 else obj.error
    error_short.short_description = 'Error'
    
    actions = ['mark_as_resolved']
    
    def mark_as_resolved(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} zahtjeva riješeno.')
    mark_as_resolved.short_description = 'Označi kao riješeno'

# ============================================
# ENHANCED MODELI - ADMIN
# ============================================

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'rate_to_km', 'last_updated']
    list_filter = ['code']
    search_fields = ['code', 'name']
    readonly_fields = ['last_updated']

@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'language', 'theme', 'email_notifications', 'payment_reminders']
    list_filter = ['language', 'theme', 'email_notifications']
    search_fields = ['korisnik__ime']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'model_name', 'object_id', 'action', 'ip_address']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__email', 'model_name']
    readonly_fields = ['timestamp', 'user', 'model_name', 'object_id', 'action', 'old_value', 'new_value', 'ip_address']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(PredictiveAnalytics)
class PredictiveAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'mjesec', 'predicted_income', 'confidence', 'actual_income', 'accuracy']
    list_filter = ['korisnik', 'mjesec']
    search_fields = ['korisnik__ime']
    readonly_fields = ['created_at']

@admin.register(GodisnjiIzvjestaj)
class GodisnjiIzvjestajAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'godina', 'ukupan_prihod', 'neto_dohodak', 'broj_faktura', 'datum_kreiranja']
    list_filter = ['godina', 'korisnik']
    search_fields = ['korisnik__ime']
    readonly_fields = ['datum_kreiranja', 'fajl_pdf']

@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ['korisnik', 'notification_type', 'scheduled_date', 'sent', 'sent_at']
    list_filter = ['notification_type', 'sent', 'scheduled_date']
    search_fields = ['korisnik__ime', 'email_subject']
    readonly_fields = ['sent_at']
    date_hierarchy = 'scheduled_date'

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'korisnik', 'document_type', 'processed', 'uploaded_at']
    list_filter = ['document_type', 'processed', 'uploaded_at']
    search_fields = ['original_filename', 'korisnik__ime']
    readonly_fields = ['uploaded_at', 'extracted_data']

@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'korisnik', 'event_type', 'start_date', 'all_day', 'reminder_sent']
    list_filter = ['event_type', 'all_day', 'reminder_sent', 'start_date']
    search_fields = ['title', 'description', 'korisnik__ime']
    date_hierarchy = 'start_date'