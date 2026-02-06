from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.validators import MinValueValidator
import json
import hashlib

# ============================================
# OSNOVNI MODELI (OSTAJU ISTI)
# ============================================


class Korisnik(models.Model):
    PLAN_CHOICES = [
        ("Starter", "Starter"),
        ("Professional", "Professional"),
        ("Business", "Business"),
        ("Enterprise", "Enterprise"),
    ]

    TIP_CHOICES = [
        ("mali", "Mali preduzetnik (2% mjesečno)"),
        ("veliki", "Veliki preduzetnik (10% godišnje u martu)"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ime = models.CharField(max_length=200)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="Starter")
    jib = models.CharField(max_length=13)
    racun = models.CharField(max_length=20)
    registrovan = models.DateField(auto_now_add=True)

    tip_preduzetnika = models.CharField(
        max_length=10,
        choices=TIP_CHOICES,
        default="mali",
        verbose_name="Tip preduzetnika",
        help_text="Odaberite tip preduzetnika za izračunavanje poreza",
    )

    trial_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Datum isteka trial perioda",
        help_text="Automatski se postavlja 30 dana od registracije",
    )
    is_trial_extended = models.BooleanField(
        default=False,
        verbose_name="Trial produžen",
        help_text="Da li je admin ručno produžio trial period",
    )

    def __str__(self):
        return f"{self.ime} ({self.plan})"

    def get_retention_days(self):
        retention = {
            "Starter": 30,
            "Professional": 90,
            "Business": 180,
            "Enterprise": 365,
        }
        return retention.get(self.plan, 30)

    class Meta:
        verbose_name_plural = "Korisnici"


class Prihod(models.Model):
    VRSTA_CHOICES = [
        ("prihod", "Prihod"),
        ("rashod", "Rashod"),
    ]

    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="prihodi"
    )
    mjesec = models.CharField(max_length=7)  # Format: 2025-01
    datum = models.DateField(null=True, blank=True)  # NOVO - tačan datum transakcije
    iznos = models.DecimalField(max_digits=10, decimal_places=2)
    vrsta = models.CharField(
        max_length=10, choices=VRSTA_CHOICES, default="prihod"
    )  # NOVO
    opis = models.CharField(max_length=500, blank=True)  # NOVO
    izvod_fajl = models.FileField(
        upload_to="izvodi/", blank=True, null=True
    )  # NOVO - PDF izvoda
    datum_kreiranja = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        znak = "+" if self.vrsta == "prihod" else "-"
        return f"{znak}{self.iznos} KM - {self.opis[:50]}"

    class Meta:
        ordering = ["-datum", "-mjesec"]
        verbose_name_plural = "Prihodi i Rashodi"


# ============================================
# FAKTURE - POJEDNOSTAVLJEN SISTEM (SAMO TEKST)
# ============================================


class Faktura(models.Model):
    """Pojednostavljena faktura - sve podatke korisnik unosi direktno"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fakture")

    # Osnovni podaci
    broj_fakture = models.CharField(max_length=50, verbose_name="Broj fakture")
    datum_izdavanja = models.DateField(verbose_name="Datum izdavanja")
    mjesto_izdavanja = models.CharField(
        max_length=200, blank=True, verbose_name="Mjesto izdavanja"
    )

    # IZDAVALAC - Tekstualna polja (korisnik unosi svaki put)
    izdavalac_naziv = models.CharField(max_length=300, verbose_name="Naziv izdavaoca")
    izdavalac_adresa = models.CharField(max_length=300, verbose_name="Adresa izdavaoca")
    izdavalac_mjesto = models.CharField(max_length=200, verbose_name="Mjesto izdavaoca")
    izdavalac_jib = models.CharField(
        max_length=20, blank=True, verbose_name="JIB izdavaoca"
    )
    izdavalac_iban = models.CharField(
        max_length=50, blank=True, verbose_name="IBAN izdavaoca"
    )
    izdavalac_racun = models.CharField(
        max_length=50, blank=True, verbose_name="Račun izdavaoca"
    )

    # PRIMALAC - Tekstualna polja (korisnik unosi svaki put)
    primalac_naziv = models.CharField(max_length=300, verbose_name="Naziv primaoca")
    primalac_adresa = models.CharField(max_length=300, verbose_name="Adresa primaoca")
    primalac_mjesto = models.CharField(max_length=200, verbose_name="Mjesto primaoca")

    primalac_jib = models.CharField(
        max_length=13,
        blank=True,
        null=True,
        verbose_name="JIB primaoca (firme)",
        help_text="JIB broj firme za koju se izdaje faktura (opcionalno)",
    )

    # Napomene
    napomena = models.TextField(verbose_name="Napomena", blank=True)

    # Valuta
    VALUTA_CHOICES = [
        ("BAM", "KM"),
        ("EUR", "EUR"),
        ("USD", "USD"),
    ]
    valuta = models.CharField(
        max_length=3, choices=VALUTA_CHOICES, default="BAM", verbose_name="Valuta"
    )

    # Automatski računati iznosi
    ukupno_bez_pdv = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Ukupno bez PDV"
    )
    pdv_iznos = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Iznos PDV"
    )
    ukupno_sa_pdv = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Ukupno sa PDV"
    )

    # Status
    STATUS_CHOICES = [
        ("draft", "Nacrt"),
        ("issued", "Izdato"),
        ("paid", "Plaćeno"),
        ("cancelled", "Stornirano"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="Status"
    )

    # Datumi
    datum_placanja = models.DateField(
        verbose_name="Datum plaćanja", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "faktura"
        verbose_name = "Faktura"
        verbose_name_plural = "Fakture"
        ordering = ["-datum_izdavanja", "-broj_fakture"]
        unique_together = ["user", "broj_fakture"]

    def __str__(self):
        return f"Faktura {self.broj_fakture} - {self.primalac_naziv}"

    def izracunaj_ukupno(self):
        """Izračunava ukupne iznose fakture uključujući PDV i dinamičku valutu"""
        stavke = self.stavke.all()

        # Računanje suma na osnovu stavki
        # Prema tvom modelu StavkaFakture: koristimo cijena_po_jedinici, kolicina i pdv_iznos
        ukupno_bez_pdv = sum(stavka.ukupna_cijena for stavka in stavke)
        pdv_iznos = sum(stavka.pdv_iznos for stavka in stavke)
        ukupno_sa_pdv = ukupno_bez_pdv + pdv_iznos

        # Ažuriranje numeričkih polja u modelu Faktura
        self.ukupno_bez_pdv = ukupno_bez_pdv
        self.pdv_iznos = pdv_iznos
        self.ukupno_sa_pdv = ukupno_sa_pdv

        # KLJUČNA ISPRAVKA: Postavljanje polja koja utils.py koristi za PDF
        self.ukupno_iznos = ukupno_sa_pdv
        # Koristimo self.valuta umjesto fiksnog "BAM"
        self.ukupno_tekst = f"{ukupno_sa_pdv:.2f} {self.valuta}"

        self.save()

        return {
            "ukupno_bez_pdv": ukupno_bez_pdv,
            "pdv_iznos": pdv_iznos,
            "ukupno_sa_pdv": ukupno_sa_pdv,
            "ukupno_tekst": self.ukupno_tekst,
            "valuta": self.valuta,
        }


class StavkaFakture(models.Model):
    """Stavka fakture"""

    faktura = models.ForeignKey(
        Faktura, on_delete=models.CASCADE, related_name="stavke", verbose_name="Faktura"
    )
    redni_broj = models.PositiveIntegerField(verbose_name="Redni broj")

    # Opis proizvoda/usluge
    opis = models.CharField(max_length=500, verbose_name="Opis")

    # Jedinica mjere - jednostavno tekstualno polje
    jedinica_mjere = models.CharField(
        max_length=50, default="unit", verbose_name="Jedinica mjere"
    )

    # Količina i cijena
    kolicina = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Količina",
    )
    cijena_po_jedinici = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Cijena po jedinici",
    )

    # PDV stopa (0 za USD fakture)
    pdv_stopa = models.IntegerField(default=0, verbose_name="PDV stopa")

    # Automatski računati iznosi
    ukupna_cijena = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Ukupna cijena bez PDV"
    )
    pdv_iznos = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="PDV iznos"
    )
    ukupna_cijena_sa_pdv = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Ukupna cijena sa PDV"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stavka_fakture"
        verbose_name = "Stavka fakture"
        verbose_name_plural = "Stavke fakture"
        ordering = ["redni_broj"]

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
    """Uplatnica za plaćanje poreza/doprinosa"""

    VRSTA_UPLATE_CHOICES = [
        ("doprinosi", "Lični doprinosi"),
        ("porez", "Porez na dohodak"),
        ("custom", "Custom uplatnica"),
    ]

    PRIMALAC_CHOICES = [
        ("PURS", "Poreska uprava RS"),
        ("FZO", "Fond zdravstva RS"),
        ("CUSTOM", "Drugi primalac (custom)"),
    ]

    OPSTINA_CHOICES = [
        ("001", "001 - Sarajevo - Centar"),
        ("002", "002 - Banja Luka"),
        ("003", "003 - Bihać"),
        ("004", "004 - Banovići"),
        ("005", "005 - Bijeljina"),
        ("007", "007 - Bileća"),
        ("008", "008 - Gradiška"),
        ("009", "009 - Bosanska Krupa"),
        ("010", "010 - Bosansko Grahovo"),
        ("011", "011 - Bosanski Petrovac"),
        ("012", "012 - Bratunac"),
        ("013", "013 - Breza"),
        ("014", "014 - Brod"),
        ("015", "015 - Bugojno"),
        ("016", "016 - Busovača"),
        ("017", "017 - Gračanica"),
        ("018", "018 - Kozarska Dubica"),
        ("019", "019 - Šamac"),
        ("020", "020 - Cazin"),
        ("021", "021 - Čapljina"),
        ("022", "022 - Čelinac"),
        ("023", "023 - Čitluk"),
        ("024", "024 - Grude"),
        ("025", "025 - Derventa"),
        ("026", "026 - Domaljevac-Šamac"),
        ("027", "027 - Donji Vakuf"),
        ("028", "028 - Doboj"),
        ("029", "029 - Drvar"),
        ("030", "030 - Tomislavgrad"),
        ("031", "031 - Foča-Ustikolina"),
        ("032", "032 - Fojnica"),
        ("033", "033 - Goražde"),
        ("034", "034 - Gacko"),
        ("035", "035 - Sarajevo - Hadžići"),
        ("036", "036 - Glamoč"),
        ("037", "037 - Gornji Vakuf-Usk."),
        ("038", "038 - Sarajevo - Ilidža"),
        ("039", "039 - Ilijaš"),
        ("040", "040 - Jablanica"),
        ("041", "041 - Jajce"),
        ("042", "042 - Kakanj"),
        ("043", "043 - Kalesija"),
        ("044", "044 - Istočno Novo Sarajevo"),
        ("045", "045 - Kalinovik"),
        ("046", "046 - Kiseljak"),
        ("047", "047 - Kladanj"),
        ("048", "048 - Ključ"),
        ("049", "049 - Konjic"),
        ("050", "050 - Ribnik"),
        ("051", "051 - Kotor Varoš"),
        ("052", "052 - Kreševo"),
        ("053", "053 - Kupres (FBiH)"),
        ("054", "054 - Novo Goražde"),
        ("056", "056 - Laktaši"),
        ("058", "058 - Livno"),
        ("059", "059 - Lopare"),
        ("060", "060 - Lukavac"),
        ("061", "061 - Ljubinje"),
        ("062", "062 - Ljubuški"),
        ("063", "063 - Maglaj"),
        ("064", "064 - Modriča"),
        ("065", "065 - Mrkonjić Grad"),
        ("066", "066 - Neum"),
        ("067", "067 - Nevesinje"),
        ("070", "070 - Novi Travnik"),
        ("071", "071 - Odžak"),
        ("072", "072 - Olovo"),
        ("073", "073 - Orašje"),
        ("074", "074 - Prijedor"),
        ("075", "075 - Prnjavor"),
        ("076", "076 - Ravno"),
        ("077", "077 - Rogatica"),
        ("078", "078 - Rudo"),
        ("079", "079 - Sanski Most"),
        ("080", "080 - Oštra Luka"),
        ("081", "081 - Sarajevo - Novi Grad"),
        ("082", "082 - Sarajevo - Novo Sar."),
        ("083", "083 - Sarajevo - Stari Grad"),
        ("085", "085 - Pale (RS)"),
        ("086", "086 - Posušje"),
        ("088", "088 - Kneževo"),
        ("089", "089 - Sokolac"),
        ("090", "090 - Srbac"),
        ("091", "091 - Srebrenica"),
        ("092", "092 - Srebrenik"),
        ("093", "093 - Stolac"),
        ("094", "094 - Čajniče"),
        ("095", "095 - Šekovići"),
        ("096", "096 - Šipovo"),
        ("097", "097 - Han Pijesak"),
        ("099", "099 - Brčko Distrikt"),
        ("100", "100 - Široki Brijeg"),
        ("101", "101 - Živinice"),
        ("102", "102 - Tešanj"),
        ("103", "103 - Teslić"),
        ("104", "104 - Sarajevo - Trnovo (F)"),
        ("105", "105 - Žepče"),
        ("106", "106 - Travnik"),
        ("107", "107 - Trebinje"),
        ("108", "108 - Tuzla"),
        ("109", "109 - Ugljevik"),
        ("110", "110 - Vareš"),
        ("111", "111 - Zenica"),
        ("112", "112 - Velika Kladuša"),
        ("113", "113 - Visoko"),
        ("114", "114 - Višegrad"),
        ("115", "115 - Sarajevo - Vogošća"),
        ("116", "116 - Vitez"),
        ("117", "117 - Zavidovići"),
        ("118", "118 - Zvornik"),
        ("119", "119 - Bužim"),
        ("120", "120 - Berkovići"),
        ("121", "121 - Kostajnica"),
        ("122", "122 - Sarajevo - Trnovo (RS)"),
        ("123", "123 - Istočni Stari Grad"),
        ("124", "124 - Istočni Drvar"),
        ("158", "158 - Istočni Mostar"),
        ("159", "159 - Jezero"),
        ("160", "160 - Krupa na Uni"),
        ("161", "161 - Kupres (RS)"),
        ("163", "163 - Milići"),
        ("164", "164 - Petrovac (RS)"),
        ("165", "165 - Osmaci"),
        ("166", "166 - Pelagićevo"),
        ("167", "167 - Vukosavlje"),
        ("180", "180 - Mostar"),
        ("181", "181 - Čelić"),
        ("182", "182 - Doboj Istok"),
        ("183", "183 - Doboj Jug"),
        ("184", "184 - Dobretići"),
        ("185", "185 - Sapna"),
        ("186", "186 - Teočak"),
        ("187", "187 - Usora"),
        ("188", "188 - Pale-Prača"),
        ("199", "199 - Stanari"),
        ("241", "241 - Foča (RS)"),
    ]

    VRSTA_PLACANJA_CHOICES = [
        ("0", "0 - Redovna/Tekuća uplata"),
        ("1", "1 - Uplata po rješenju"),
        ("2", "2 - Uplata po rješenju o prinudnoj naplati"),
        ("3", "3 - Uplata po rješenju o odgođenom plaćanju"),
        ("4", "4 - Uplata po rješenju iz inspekcijskog nadzora"),
        ("5", "5 - Uplata po rješenju o prekršaju"),
        ("6", "6 - Uplata po rješenju suda"),
        ("7", "7 - Uplata zaostalih obaveza"),
        ("8", "8 - Dobrovoljna uplata"),
        ("9", "9 - Ostale uplate"),
    ]

    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="uplatnice"
    )

    # Tip uplate
    vrsta_uplate = models.CharField(
        max_length=20,
        choices=VRSTA_UPLATE_CHOICES,
        default="doprinosi",
        verbose_name="Vrsta uplate",
    )

    datum = models.DateField(verbose_name="Datum uplate")

    # Primalac
    primalac_tip = models.CharField(
        max_length=20,
        choices=PRIMALAC_CHOICES,
        default="PURS",
        verbose_name="Tip primaoca",
    )

    primalac_naziv = models.CharField(max_length=200, verbose_name="Naziv primaoca")

    primalac_adresa = models.CharField(
        max_length=200, blank=True, verbose_name="Adresa primaoca"
    )

    primalac_grad = models.CharField(
        max_length=100, blank=True, verbose_name="Grad primaoca"
    )

    # Računi
    racun_posiljaoca = models.CharField(max_length=30, verbose_name="Račun pošiljaoca")

    racun_primaoca = models.CharField(max_length=30, verbose_name="Račun primaoca")

    # Iznos
    iznos = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Iznos (KM)"
    )

    # Svrha
    svrha = models.CharField(max_length=200, verbose_name="Svrha uplate")

    # Poreska polja
    poresko_broj = models.CharField(
        max_length=13, blank=True, verbose_name="Poresko broj (JIB)"
    )

    vrsta_placanja = models.CharField(
        max_length=2,
        choices=VRSTA_PLACANJA_CHOICES,
        default="0",
        verbose_name="Vrsta plaćanja",
    )

    vrsta_prihoda = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Vrsta prihoda",
        help_text="712199 - doprinosi, 713111 - porez",
    )

    opstina = models.CharField(
        max_length=3,  # Promijenjeno sa 2 na 3 (241 ima 3 cifre)
        choices=OPSTINA_CHOICES,
        default="014",  # '014' umjesto '14'
        verbose_name="Opština",
    )

    budzetska_organizacija = models.CharField(
        max_length=10, default="9999999", verbose_name="Budžetska organizacija"
    )

    sifra_placanja = models.CharField(
        max_length=2, default="43", verbose_name="Šifra plaćanja"
    )

    poziv_na_broj = models.CharField(
        max_length=20, default="0000000000", verbose_name="Poziv na broj"
    )

    # Fajl
    fajl = models.FileField(upload_to="uplatnice/", blank=True, null=True)

    datum_kreiranja = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.datum} - {self.primalac_naziv} - {self.iznos} KM"

    class Meta:
        ordering = ["-datum"]
        verbose_name_plural = "Uplatnice"

    def get_vrsta_prihoda_auto(self):
        """Automatski odredi vrstu prihoda"""
        if self.vrsta_uplate == "doprinosi":
            return "712199"
        elif self.vrsta_uplate == "porez":
            return "713111"
        else:
            return self.vrsta_prihoda or ""

    def get_budzetska_org_auto(self):
        """Automatski odredi budžetsku org"""
        if self.primalac_tip == "PURS":
            return "9999999"
        elif self.primalac_tip == "FZO":
            return "9999999"
        else:
            return self.budzetska_organizacija or "9999999"


class Bilans(models.Model):
    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="bilansi"
    )
    od_mjesec = models.CharField(max_length=7)
    do_mjesec = models.CharField(max_length=7)
    ukupan_prihod = models.DecimalField(max_digits=10, decimal_places=2)
    porez = models.DecimalField(max_digits=10, decimal_places=2)
    doprinosi = models.DecimalField(max_digits=10, decimal_places=2)
    neto = models.DecimalField(max_digits=10, decimal_places=2)
    fajl = models.FileField(upload_to="bilans/")
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
        ordering = ["-datum_kreiranja"]
        verbose_name_plural = "Bilansi"


class EmailInbox(models.Model):
    """Email inbox - parsira izvode i prikazuje transakcije prije odobrenja"""

    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="inbox_poruke"
    )

    # Email metadata
    from_email = models.EmailField(verbose_name="Od koga")
    subject = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Naslov"
    )

    # PDF izvod
    pdf_fajl = models.FileField(upload_to="inbox_pdf/%Y/%m/", blank=True, null=True)
    pdf_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="PDF Hash (za duplikat detekciju)",
    )

    # Banka info
    banka_naziv = models.CharField(max_length=100, blank=True, verbose_name="Banka")

    # PARSOVANE TRANSAKCIJE - čuvamo kao JSON
    transakcije_json = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Parsovane transakcije",
        help_text="Lista transakcija: [{datum, opis, iznos, tip}, ...]",
    )

    # Status
    procesuirano = models.BooleanField(default=False, verbose_name="Odobreno")
    datum_prijema = models.DateTimeField(auto_now_add=True, verbose_name="Primljeno")
    datum_odobravanja = models.DateTimeField(
        blank=True, null=True, verbose_name="Odobreno"
    )

    # AI confidence
    confidence = models.IntegerField(default=0, verbose_name="AI Pouzdanost (%)")

    class Meta:
        ordering = ["-datum_prijema"]
        verbose_name = "Email Inbox"
        verbose_name_plural = "Email Inbox"
        indexes = [
            models.Index(fields=["korisnik", "procesuirano"]),
            models.Index(fields=["pdf_hash"]),
        ]

    def __str__(self):
        return f"Izvod: {self.korisnik.ime} - {self.datum_prijema.strftime('%d.%m.%Y')}"

    def calculate_pdf_hash(self):
        """Izračunaj SHA256 hash PDF fajla"""
        if not self.pdf_fajl:
            return None

        self.pdf_fajl.seek(0)
        file_hash = hashlib.sha256()

        # Čitaj u chunk-ovima za velike fajlove
        for chunk in iter(lambda: self.pdf_fajl.read(4096), b""):
            file_hash.update(chunk)

        self.pdf_fajl.seek(0)
        return file_hash.hexdigest()

    def parse_pdf(self):
        """Parsuj PDF i sačuvaj transakcije"""
        from .utils import parse_bank_statement_pdf

        if not self.pdf_fajl:
            return []

        transakcije = parse_bank_statement_pdf(self.pdf_fajl)

        # Konvertuj u JSON-friendly format
        self.transakcije_json = [
            {
                "datum": t["datum"].strftime("%Y-%m-%d"),
                "opis": t["opis"],
                "iznos": float(t["iznos"]),
                "tip": "prihod" if t["iznos"] > 0 else "rashod",
            }
            for t in transakcije
        ]

        self.save()
        return self.transakcije_json

    def get_ukupno_prihodi(self):
        """Ukupan iznos prihoda"""
        if not self.transakcije_json:
            return Decimal("0")
        return sum(
            Decimal(str(t["iznos"])) for t in self.transakcije_json if t["iznos"] > 0
        )

    def get_ukupno_rashodi(self):
        """Ukupan iznos rashoda"""
        if not self.transakcije_json:
            return Decimal("0")
        return sum(
            Decimal(str(abs(t["iznos"])))
            for t in self.transakcije_json
            if t["iznos"] < 0
        )

    def get_neto(self):
        """Neto razlika"""
        return self.get_ukupno_prihodi() - self.get_ukupno_rashodi()

    @classmethod
    def check_duplicate(cls, pdf_file, korisnik):
        """Provjeri da li PDF već postoji"""
        pdf_file.seek(0)
        file_hash = hashlib.sha256()

        for chunk in iter(lambda: pdf_file.read(4096), b""):
            file_hash.update(chunk)

        pdf_file.seek(0)
        pdf_hash = file_hash.hexdigest()

        # Provjeri da li hash postoji
        return (
            cls.objects.filter(korisnik=korisnik, pdf_hash=pdf_hash).exists(),
            pdf_hash,
        )


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
        ordering = ["-timestamp"]
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
        ordering = ["-timestamp"]
        verbose_name_plural = "Failed Requests"


class UserPreferences(models.Model):
    """Korisničke preferencije"""

    LANGUAGE_CHOICES = [
        ("sr", "Srpski"),
        ("en", "English"),
    ]

    THEME_CHOICES = [
        ("light", "Light"),
        ("dark", "Dark"),
    ]

    korisnik = models.OneToOneField(
        Korisnik, on_delete=models.CASCADE, related_name="preferences"
    )
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="sr")
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="light")

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
        ordering = ["-timestamp"]
        verbose_name_plural = "Audit Logs"


class PredictiveAnalytics(models.Model):
    """ML predikcije za prihode"""

    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="predictions"
    )
    mjesec = models.CharField(max_length=7)
    predicted_income = models.DecimalField(max_digits=10, decimal_places=2)
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    actual_income = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    accuracy = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mjesec}: {self.predicted_income} KM ({self.confidence}%)"

    class Meta:
        ordering = ["mjesec"]
        verbose_name_plural = "Predictive Analytics"


class GodisnjiIzvjestaj(models.Model):
    """Godišnji izvještaj za PURS"""

    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="godisnji_izvjestaji"
    )
    godina = models.IntegerField()
    ukupan_prihod = models.DecimalField(max_digits=12, decimal_places=2)
    ukupan_porez = models.DecimalField(max_digits=12, decimal_places=2)
    ukupni_doprinosi = models.DecimalField(max_digits=12, decimal_places=2)
    neto_dohodak = models.DecimalField(max_digits=12, decimal_places=2)
    broj_faktura = models.IntegerField()
    broj_klijenata = models.IntegerField()
    fajl_pdf = models.FileField(upload_to="godisnji_izvjestaji/")
    datum_kreiranja = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Godišnji izvještaj {self.godina} - {self.korisnik.ime}"

    class Meta:
        ordering = ["-godina"]
        verbose_name_plural = "Godišnji izvještaji"
        unique_together = ["korisnik", "godina"]


class EmailNotification(models.Model):
    """Zakazane email notifikacije"""

    NOTIFICATION_TYPES = [
        ("payment_reminder", "Podsjetnik za plaćanje"),
        ("invoice_due", "Faktura dospjeva"),
        ("monthly_summary", "Mjesečni izvještaj"),
        ("annual_report", "Godišnji izvještaj"),
    ]

    korisnik = models.ForeignKey(
        Korisnik, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    scheduled_date = models.DateTimeField()
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    email_subject = models.CharField(max_length=200)
    email_body = models.TextField()

    def __str__(self):
        return f"{self.notification_type} - {self.korisnik.ime}"

    class Meta:
        ordering = ["scheduled_date"]
        verbose_name_plural = "Email Notifications"


class SistemskiParametri(models.Model):
    """Sistemski parametri - može biti samo jedan red u bazi"""

    # Doprinosi
    mjesecni_doprinosi = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("466.00"),
        verbose_name="Mjesečni doprinosi (KM)",
        help_text="Lični doprinosi koji se koriste pri kreiranju uplatnice",
    )

    prag_mali_preduzetnik = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("100000.00"),
        verbose_name="Prag za malog preduzetnika (KM godišnje)",
        help_text="Do ovog iznosa korisnik je mali preduzetnik (2%), preko je veliki (10%)",
    )

    # Poreske stope
    porez_mali_preduzetnik = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        verbose_name="Porez za malog preduzetnika (%)",
        help_text="Plaća se mjesečno",
    )

    porez_veliki_preduzetnik = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        verbose_name="Porez za velikog preduzetnika (%)",
        help_text="Plaća se godišnje",
    )

    # Mjesec plaćanja poreza za velike preduzetnike
    mjesec_placanja_poreza = models.IntegerField(
        default=3,
        verbose_name="Mjesec plaćanja poreza za velike preduzetnike",
        help_text="Broj mjeseca (1-12), default: 3 = Mart",
    )

    # Metadata
    zadnje_azurirano = models.DateTimeField(auto_now=True)
    azurirao = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Sistemski parametri - Doprinosi: {self.mjesecni_doprinosi} KM"

    class Meta:
        verbose_name = "Sistemski parametri"
        verbose_name_plural = "Sistemski parametri"

    @classmethod
    def get_parametri(cls):
        """Helper metod - vraća parametre ili kreira default ako ne postoje"""
        parametri, created = cls.objects.get_or_create(pk=1)
        return parametri

    def save(self, *args, **kwargs):
        # Dozvoli samo jedan red
        self.pk = 1
        super().save(*args, **kwargs)


# core/models.py - DODAJ OVE MODELE NA KRAJ


class Banka(models.Model):
    """Banke u Republici Srpskoj"""

    naziv = models.CharField(max_length=200, verbose_name="Naziv banke")
    skraceni_naziv = models.CharField(max_length=50, verbose_name="Skraćeni naziv")

    # Računi - DVA obavezna računa
    racun_doprinosi = models.CharField(
        max_length=30,
        verbose_name="Račun za doprinose",
        help_text="Račun Poreske uprave za uplate doprinosa",
    )

    racun_porez = models.CharField(
        max_length=30,
        verbose_name="Račun za porez",
        help_text="Račun Poreske uprave za uplate poreza",
    )

    # Primalac (obično isti za obe uplate)
    primalac_doprinosi = models.CharField(
        max_length=300,
        default="PORESKA UPRAVA REPUBLIKE SRPSKE",
        verbose_name="Primalac - Doprinosi",
    )

    primalac_porez = models.CharField(
        max_length=300,
        default="PORESKA UPRAVA REPUBLIKE SRPSKE",
        verbose_name="Primalac - Porez",
    )

    # Pozivi na broj (ako se razlikuju)
    poziv_doprinosi = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Poziv na broj (doprinosi)",
        help_text="Ako je različit od JIB-a",
    )

    poziv_porez = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Poziv na broj (porez)",
        help_text="Ako je različit od JIB-a",
    )

    # Svrha (template sa {mjesec} i {godina})
    svrha_doprinosi_template = models.CharField(
        max_length=200,
        default="Lični doprinosi za {mjesec}/{godina}",
        verbose_name="Template svrhe - Doprinosi",
        help_text="Koristi {mjesec} i {godina} za dinamički tekst",
    )

    svrha_porez_template = models.CharField(
        max_length=200,
        default="Porez na prihod za {godina}",
        verbose_name="Template svrhe - Porez",
    )

    # Status
    aktivna = models.BooleanField(default=True, verbose_name="Aktivna")

    # Metadata
    datum_kreiranja = models.DateTimeField(auto_now_add=True)
    zadnje_azurirano = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.naziv

    class Meta:
        ordering = ["naziv"]
        verbose_name = "Banka"
        verbose_name_plural = "Banke"

    def get_racun_za_vrstu(self, vrsta):
        """Vraća pravi račun za vrstu uplate"""
        if vrsta == "doprinosi":
            return self.racun_doprinosi
        elif vrsta == "porez":
            return self.racun_porez
        return self.racun_doprinosi

    def get_primalac_za_vrstu(self, vrsta):
        """Vraća primaoca za vrstu uplate"""
        if vrsta == "doprinosi":
            return self.primalac_doprinosi
        elif vrsta == "porez":
            return self.primalac_porez
        return self.primalac_doprinosi

    def get_svrhu_za_vrstu(self, vrsta, mjesec, godina):
        """Generiši svrhu uplate sa dinamičkim podacima"""
        if vrsta == "doprinosi":
            template = self.svrha_doprinosi_template
        else:
            template = self.svrha_porez_template

        return template.format(mjesec=mjesec, godina=godina)


class SupportPitanje(models.Model):
    """Korisnička pitanja i support ticketi"""

    STATUS_CHOICES = [
        ("novo", "Novo"),
        ("u_obradi", "U obradi"),
        ("rijeseno", "Riješeno"),
        ("zatvoreno", "Zatvoreno"),
    ]

    PRIORITET_CHOICES = [
        ("nizak", "Nizak"),
        ("srednji", "Srednji"),
        ("visok", "Visok"),
        ("hitan", "Hitan"),
    ]

    korisnik = models.ForeignKey(
        Korisnik,
        on_delete=models.CASCADE,
        related_name="support_pitanja",
        verbose_name="Korisnik",
    )

    naslov = models.CharField(max_length=200, verbose_name="Naslov")
    poruka = models.TextField(verbose_name="Poruka")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="novo", verbose_name="Status"
    )

    prioritet = models.CharField(
        max_length=20,
        choices=PRIORITET_CHOICES,
        default="srednji",
        verbose_name="Prioritet",
    )

    # Timestamps
    datum_kreiranja = models.DateTimeField(auto_now_add=True, verbose_name="Kreirano")
    datum_azuriranja = models.DateTimeField(auto_now=True, verbose_name="Ažurirano")
    datum_zatvaranja = models.DateTimeField(
        blank=True, null=True, verbose_name="Zatvoreno"
    )

    # Admin koji rješava
    obradjuje = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="support_tickets_assigned",
        verbose_name="Obrađuje admin",
    )

    class Meta:
        ordering = ["-datum_kreiranja"]
        verbose_name = "Support Pitanje"
        verbose_name_plural = "Support Pitanja"

    def __str__(self):
        return f"{self.naslov} - {self.korisnik.ime} ({self.status})"

    def get_slike(self):
        """Vrati sve priložene slike"""
        return self.slike.all()


class SupportSlika(models.Model):
    """Slike priložene uz support pitanje"""

    pitanje = models.ForeignKey(
        SupportPitanje,
        on_delete=models.CASCADE,
        related_name="slike",
        verbose_name="Pitanje",
    )

    slika = models.ImageField(upload_to="support_slike/%Y/%m/", verbose_name="Slika")

    datum_upload = models.DateTimeField(auto_now_add=True, verbose_name="Upload-ovano")

    class Meta:
        ordering = ["datum_upload"]
        verbose_name = "Support Slika"
        verbose_name_plural = "Support Slike"

    def __str__(self):
        return f"Slika za: {self.pitanje.naslov}"

    def delete(self, *args, **kwargs):
        """Obriši sliku sa diska pri brisanju"""
        if self.slika:
            if os.path.isfile(self.slika.path):
                os.remove(self.slika.path)
        super().delete(*args, **kwargs)


class SupportOdgovor(models.Model):
    """Odgovori na support pitanja - thread konverzacija"""

    pitanje = models.ForeignKey(
        SupportPitanje,
        on_delete=models.CASCADE,
        related_name="odgovori",
        verbose_name="Pitanje",
    )

    # Ko je odgovorio
    autor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, verbose_name="Autor"
    )

    # Da li je admin ili korisnik
    je_admin_odgovor = models.BooleanField(default=False, verbose_name="Admin odgovor")

    odgovor = models.TextField(verbose_name="Odgovor")
    datum_odgovora = models.DateTimeField(auto_now_add=True, verbose_name="Datum")

    class Meta:
        ordering = ["datum_odgovora"]
        verbose_name = "Support Odgovor"
        verbose_name_plural = "Support Odgovori"

    def __str__(self):
        tip = "Admin" if self.je_admin_odgovor else "Korisnik"
        return f"{tip} odgovor na {self.pitanje.naslov}"
