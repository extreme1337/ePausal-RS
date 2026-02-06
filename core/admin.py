from django.contrib import admin
from .models import (
    Korisnik,
    Prihod,
    Faktura,
    StavkaFakture,
    SupportOdgovor,
    SupportPitanje,
    SupportSlika,
    Uplatnica,
    Bilans,
    EmailInbox,
    SystemLog,
    FailedRequest,
    UserPreferences,
    AuditLog,
    PredictiveAnalytics,
    GodisnjiIzvjestaj,
    EmailNotification,
    SistemskiParametri,
    Banka,
)
from django.utils.html import format_html

# ============================================
# OSNOVNI MODELI
# ============================================


@admin.register(Korisnik)
class KorisnikAdmin(admin.ModelAdmin):
    list_display = [
        "ime",
        "user",
        "plan",
        "tip_preduzetnika",
        "jib",
        "racun",
        "registrovan",
    ]
    list_filter = ["plan", "tip_preduzetnika", "registrovan"]
    search_fields = ["ime", "jib", "user__email", "user__username"]
    readonly_fields = ["registrovan"]

    fieldsets = (
        ("👤 Osnovni podaci", {"fields": ("user", "ime", "plan")}),
        (
            "💼 Tip Preduzetnika",
            {
                "fields": ("tip_preduzetnika",),
                "description": """
                <div style="background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0;">
                    <b>Odaberite tip preduzetnika:</b><br>
                    • <b>Mali:</b> Porez 2% mjesečno<br>
                    • <b>Veliki:</b> Porez 10% godišnje (plaća se u martu)
                </div>
            """,
            },
        ),
        ("🏦 Finansijski podaci", {"fields": ("jib", "racun")}),
        ("📅 Dodatno", {"fields": ("registrovan",), "classes": ("collapse",)}),
    )


@admin.register(Prihod)
class PrihodAdmin(admin.ModelAdmin):
    list_display = ["korisnik", "mjesec", "iznos", "datum_kreiranja"]
    list_filter = ["mjesec", "datum_kreiranja"]
    search_fields = ["korisnik__ime"]
    date_hierarchy = "datum_kreiranja"


# ============================================
# FAKTURE - POJEDNOSTAVLJEN SISTEM
# ============================================


class StavkaFaktureInline(admin.TabularInline):
    """Inline admin za stavke fakture"""

    model = StavkaFakture
    extra = 1
    fields = [
        "redni_broj",
        "opis",
        "jedinica_mjere",
        "kolicina",
        "cijena_po_jedinici",
        "pdv_stopa",
        "ukupna_cijena",
    ]
    readonly_fields = ["ukupna_cijena"]


@admin.register(Faktura)
class FakturaAdmin(admin.ModelAdmin):
    list_display = [
        "broj_fakture",
        "primalac_naziv",
        "datum_izdavanja",
        "ukupno_sa_pdv",
        "status",
        "created_at",
    ]
    list_filter = ["status", "datum_izdavanja", "valuta"]
    search_fields = ["broj_fakture", "primalac_naziv", "izdavalac_naziv"]
    date_hierarchy = "datum_izdavanja"
    inlines = [StavkaFaktureInline]

    fieldsets = (
        (
            "Osnovni podaci",
            {
                "fields": (
                    "user",
                    "broj_fakture",
                    "datum_izdavanja",
                    "mjesto_izdavanja",
                    "status",
                )
            },
        ),
        (
            "Izdavalac",
            {
                "fields": (
                    "izdavalac_naziv",
                    "izdavalac_adresa",
                    "izdavalac_mjesto",
                    "izdavalac_jib",
                    "izdavalac_iban",
                    "izdavalac_racun",
                )
            },
        ),
        (
            "Primalac",
            {
                "fields": (
                    "primalac_naziv",
                    "primalac_adresa",
                    "primalac_mjesto",
                    "primalac_jib",
                )
            },
        ),
        (
            "Finansije",
            {
                "fields": (
                    "valuta",
                    "ukupno_bez_pdv",
                    "pdv_iznos",
                    "ukupno_sa_pdv",
                    "datum_placanja",
                )
            },
        ),
        ("Dodatno", {"fields": ("napomena",)}),
    )

    readonly_fields = ["ukupno_bez_pdv", "pdv_iznos", "ukupno_sa_pdv"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.izracunaj_ukupno()


@admin.register(StavkaFakture)
class StavkaFaktureAdmin(admin.ModelAdmin):
    list_display = [
        "faktura",
        "redni_broj",
        "opis",
        "jedinica_mjere",
        "kolicina",
        "cijena_po_jedinici",
        "ukupna_cijena_sa_pdv",
    ]
    list_filter = ["faktura__datum_izdavanja", "jedinica_mjere"]
    search_fields = ["opis", "faktura__broj_fakture"]


@admin.register(Banka)
class BankaAdmin(admin.ModelAdmin):
    list_display = [
        "naziv",
        "skraceni_naziv",
        "racun_doprinosi",
        "racun_porez",
        "aktivna",
        "zadnje_azurirano",
    ]
    list_filter = ["aktivna"]
    search_fields = ["naziv", "skraceni_naziv", "racun_doprinosi", "racun_porez"]
    readonly_fields = ["datum_kreiranja", "zadnje_azurirano"]

    fieldsets = (
        ("Osnovno", {"fields": ("naziv", "skraceni_naziv", "aktivna")}),
        (
            "Račun za Doprinose",
            {
                "fields": (
                    "primalac_doprinosi",
                    "racun_doprinosi",
                    "model_doprinosi",
                    "svrha_doprinosi_template",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Račun za Porez",
            {
                "fields": (
                    "primalac_porez",
                    "racun_porez",
                    "model_porez",
                    "svrha_porez_template",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("datum_kreiranja", "zadnje_azurirano"),
                "classes": ("collapse",),
            },
        ),
    )


# ============================================
# UPLATNICE I BILANSI
# ============================================


@admin.register(Uplatnica)
class UplatnicaAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "datum",
        "vrsta_uplate",
        "primalac_naziv",
        "iznos",
        "datum_kreiranja",
    ]
    list_filter = ["vrsta_uplate", "primalac_tip", "datum", "datum_kreiranja"]
    search_fields = ["korisnik__ime", "svrha", "primalac_naziv"]
    date_hierarchy = "datum"
    readonly_fields = ["datum_kreiranja"]

    fieldsets = (
        ("Osnovni podaci", {"fields": ("korisnik", "vrsta_uplate", "datum", "iznos")}),
        (
            "Primalac",
            {
                "fields": (
                    "primalac_tip",
                    "primalac_naziv",
                    "primalac_adresa",
                    "primalac_grad",
                )
            },
        ),
        ("Računi", {"fields": ("racun_posiljaoca", "racun_primaoca")}),
        (
            "Poreska polja",
            {
                "fields": (
                    "poresko_broj",
                    "vrsta_placanja",
                    "vrsta_prihoda",
                    "opstina",
                    "budzetska_organizacija",
                    "sifra_placanja",
                    "poziv_na_broj",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Ostalo",
            {"fields": ("svrha", "fajl", "datum_kreiranja"), "classes": ("collapse",)},
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing
            return self.readonly_fields + ["datum_kreiranja"]
        return self.readonly_fields


@admin.register(Bilans)
class BilansAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "od_mjesec",
        "do_mjesec",
        "ukupan_prihod",
        "neto",
        "datum_kreiranja",
        "days_until_expiry",
    ]
    list_filter = ["datum_kreiranja", "korisnik__plan"]
    search_fields = ["korisnik__ime"]
    date_hierarchy = "datum_kreiranja"


@admin.register(EmailInbox)
class EmailInboxAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "from_email",
        "banka_naziv",
        "broj_transakcija",
        "ukupno_prihodi",
        "ukupno_rashodi",
        "procesuirano",
        "datum_prijema",
    ]

    list_filter = ["procesuirano", "banka_naziv", "datum_prijema"]
    search_fields = ["from_email", "subject", "korisnik__ime", "pdf_hash"]
    date_hierarchy = "datum_prijema"
    readonly_fields = [
        "pdf_hash",
        "datum_prijema",
        "datum_odobravanja",
        "transakcije_display",
        "ukupno_prihodi",
        "ukupno_rashodi",
        "neto",
    ]

    fieldsets = (
        (
            "Email Info",
            {"fields": ("korisnik", "from_email", "subject", "banka_naziv")},
        ),
        ("PDF Fajl", {"fields": ("pdf_fajl", "pdf_hash")}),
        (
            "Parsovane Transakcije",
            {"fields": ("transakcije_display", "confidence"), "classes": ("collapse",)},
        ),
        ("Ukupno", {"fields": ("ukupno_prihodi", "ukupno_rashodi", "neto")}),
        ("Status", {"fields": ("procesuirano", "datum_prijema", "datum_odobravanja")}),
    )

    def broj_transakcija(self, obj):
        if obj.transakcije_json:
            return len(obj.transakcije_json)
        return 0

    broj_transakcija.short_description = "Broj trans."

    def ukupno_prihodi(self, obj):
        return f"{obj.get_ukupno_prihodi():.2f} KM"

    ukupno_prihodi.short_description = "Prihodi"

    def ukupno_rashodi(self, obj):
        return f"{obj.get_ukupno_rashodi():.2f} KM"

    ukupno_rashodi.short_description = "Rashodi"

    def neto(self, obj):
        neto = obj.get_neto()
        color = "green" if neto >= 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f} KM</span>', color, neto
        )

    neto.short_description = "Neto"

    def transakcije_display(self, obj):
        if not obj.transakcije_json:
            return "Nema transakcija"

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th>Datum</th><th>Opis</th><th>Tip</th><th>Iznos</th></tr>'

        for trans in obj.transakcije_json:
            tip_color = "green" if trans["tip"] == "prihod" else "red"
            html += f"""
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 5px;">{trans['datum']}</td>
                <td style="padding: 5px;">{trans['opis']}</td>
                <td style="padding: 5px; color: {tip_color}; font-weight: bold;">{trans['tip'].upper()}</td>
                <td style="padding: 5px; text-align: right; font-weight: bold;">{trans['iznos']:.2f} KM</td>
            </tr>
            """

        html += "</table>"
        return format_html(html)

    transakcije_display.short_description = "Transakcije"


# ============================================
# SYSTEM LOGS
# ============================================


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ["user", "action", "status", "ip_address", "timestamp"]
    list_filter = ["status", "action", "timestamp"]
    search_fields = ["user__username", "action", "ip_address"]
    date_hierarchy = "timestamp"
    readonly_fields = ["user", "action", "status", "ip_address", "timestamp", "details"]


@admin.register(FailedRequest)
class FailedRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "action", "retryable", "timestamp"]
    list_filter = ["retryable", "timestamp"]
    search_fields = ["user__username", "action", "error"]
    date_hierarchy = "timestamp"


# ============================================
# ENHANCED MODELI
# ============================================


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "language",
        "theme",
        "email_notifications",
        "payment_reminders",
    ]
    list_filter = ["language", "theme", "email_notifications"]
    search_fields = ["korisnik__ime"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["user", "model_name", "object_id", "action", "timestamp"]
    list_filter = ["action", "model_name", "timestamp"]
    search_fields = ["user__username", "model_name"]
    date_hierarchy = "timestamp"
    readonly_fields = [
        "user",
        "model_name",
        "object_id",
        "action",
        "old_value",
        "new_value",
        "ip_address",
        "timestamp",
    ]


@admin.register(PredictiveAnalytics)
class PredictiveAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "mjesec",
        "predicted_income",
        "confidence",
        "actual_income",
        "accuracy",
    ]
    list_filter = ["mjesec", "created_at"]
    search_fields = ["korisnik__ime"]


@admin.register(GodisnjiIzvjestaj)
class GodisnjiIzvjestajAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "godina",
        "ukupan_prihod",
        "ukupan_porez",
        "neto_dohodak",
        "broj_faktura",
    ]
    list_filter = ["godina"]
    search_fields = ["korisnik__ime"]


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "korisnik",
        "notification_type",
        "scheduled_date",
        "sent",
        "sent_at",
    ]
    list_filter = ["notification_type", "sent", "scheduled_date"]
    search_fields = ["korisnik__ime", "email_subject"]
    date_hierarchy = "scheduled_date"


# ============================================
# SISTEMSKI PARAMETRI
# ============================================


@admin.register(SistemskiParametri)
class SistemskiParametriAdmin(admin.ModelAdmin):
    """Admin za sistemske parametre - samo jedan red u bazi"""

    list_display = [
        "mjesecni_doprinosi",
        "porez_mali_preduzetnik",
        "porez_veliki_preduzetnik",
        "mjesec_placanja_poreza",
        "zadnje_azurirano",
    ]

    fieldsets = (
        (
            "💰 Doprinosi",
            {
                "fields": ("mjesecni_doprinosi",),
                "description": '<b style="color: #0066cc;">Mjesečni doprinosi za lične doprinose</b><br>Ovaj iznos se koristi pri kreiranju uplatnice i dodaje se svakom mjesecu.',
            },
        ),
        (
            "📊 Poreske Stope",
            {
                "fields": (
                    "porez_mali_preduzetnik",
                    "porez_veliki_preduzetnik",
                    "mjesec_placanja_poreza",
                ),
                "description": """
                <b style="color: #0066cc;">Postavke za izračunavanje poreza:</b><br>
                • <b>Mali preduzetnik:</b> Porez se plaća <b>mjesečno</b><br>
                • <b>Veliki preduzetnik:</b> Porez se plaća <b>jednom godišnje</b> u odabranom mjesecu
            """,
            },
        ),
        (
            "ℹ️ Metadata",
            {"fields": ("zadnje_azurirano", "azurirao"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["zadnje_azurirano", "azurirao"]

    def has_add_permission(self, request):
        # Dozvoli dodavanje samo ako ne postoji nijedan red
        return SistemskiParametri.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        # Ne dozvoli brisanje
        return False

    def save_model(self, request, obj, form, change):
        obj.azurirao = request.user
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        # Automatski kreiraj parametre ako ne postoje
        if SistemskiParametri.objects.count() == 0:
            SistemskiParametri.objects.create()
        return super().changelist_view(request, extra_context)


# ============================================
# SUPPORT
# ============================================


@admin.register(SupportPitanje)
class SupportPitanjeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "korisnik",
        "naslov",
        "status_badge",
        "prioritet_badge",
        "broj_slika",
        "broj_odgovora",
        "datum_kreiranja",
    ]
    list_filter = ["status", "prioritet", "datum_kreiranja"]
    search_fields = ["naslov", "poruka", "korisnik__ime", "korisnik__user__email"]
    readonly_fields = ["datum_kreiranja", "datum_azuriranja", "prikaz_slika"]

    fieldsets = (
        ("Ticket Info", {"fields": ("korisnik", "naslov", "poruka")}),
        ("Status", {"fields": ("status", "prioritet", "obradjuje")}),
        ("Slike", {"fields": ("prikaz_slika",), "classes": ("collapse",)}),
        (
            "Datumi",
            {
                "fields": ("datum_kreiranja", "datum_azuriranja", "datum_zatvaranja"),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj):
        colors = {
            "novo": "blue",
            "u_obradi": "yellow",
            "rijeseno": "green",
            "zatvoreno": "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 10px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def prioritet_badge(self, obj):
        colors = {
            "nizak": "#9CA3AF",
            "srednji": "#3B82F6",
            "visok": "#F59E0B",
            "hitan": "#EF4444",
        }
        color = colors.get(obj.prioritet, "#9CA3AF")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 10px; font-weight: bold;">{}</span>',
            color,
            obj.get_prioritet_display(),
        )

    prioritet_badge.short_description = "Prioritet"

    def broj_slika(self, obj):
        return obj.slike.count()

    broj_slika.short_description = "Slike"

    def broj_odgovora(self, obj):
        count = obj.odgovori.count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>', count
            )
        return "0"

    broj_odgovora.short_description = "Odgovori"

    def prikaz_slika(self, obj):
        """Prikaži sve slike"""
        if not obj.slike.exists():
            return "Nema slika"

        html = '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
        for slika in obj.slike.all():
            html += f'<a href="{slika.slika.url}" target="_blank"><img src="{slika.slika.url}" style="max-width: 150px; max-height: 150px; border-radius: 5px; border: 2px solid #ddd;"></a>'
        html += "</div>"
        return format_html(html)

    prikaz_slika.short_description = "Priložene slike"


@admin.register(SupportOdgovor)
class SupportOdgovorAdmin(admin.ModelAdmin):
    list_display = ["pitanje", "autor", "je_admin_odgovor", "datum_odgovora"]
    list_filter = ["je_admin_odgovor", "datum_odgovora"]
    search_fields = ["odgovor", "pitanje__naslov"]
    readonly_fields = ["datum_odgovora"]

    fieldsets = (
        ("Odgovor", {"fields": ("pitanje", "autor", "je_admin_odgovor", "odgovor")}),
        ("Datum", {"fields": ("datum_odgovora",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("pitanje", "autor")


@admin.register(SupportSlika)
class SupportSlikaAdmin(admin.ModelAdmin):
    list_display = ["pitanje", "slika_preview", "datum_upload"]
    readonly_fields = ["datum_upload", "slika_preview"]

    def slika_preview(self, obj):
        if obj.slika:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;">',
                obj.slika.url,
            )
        return "Nema slike"

    slika_preview.short_description = "Preview"
