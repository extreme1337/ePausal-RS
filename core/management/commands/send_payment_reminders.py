from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from core.models import Korisnik, UserPreferences, EmailNotification
from decimal import Decimal
from datetime import datetime

class Command(BaseCommand):
    help = 'Pošalji email podsjetnike za plaćanje poreza (pokreni svaki dan)'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        
        self.stdout.write('=' * 60)
        self.stdout.write(f'📧 Email Podsjetnici - {today.strftime("%d.%m.%Y")}')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        # Pošalji podsjetnik 5 dana prije roka (5. u mjesecu)
        if today.day == 5:
            trenutni_mjesec = f'{today.year}-{str(today.month).zfill(2)}'
            
            korisnici = Korisnik.objects.all()
            sent_count = 0
            skipped_count = 0
            
            for korisnik in korisnici:
                # Provjeri preferences
                try:
                    prefs = korisnik.preferences
                    if not prefs.email_notifications or not prefs.payment_reminders:
                        self.stdout.write(f'  ⏭️  {korisnik.ime} - Notifikacije isključene')
                        skipped_count += 1
                        continue
                except UserPreferences.DoesNotExist:
                    pass  # Default: pošalji
                
                # Provjeri da li ima prihod za ovaj mjesec
                prihod = korisnik.prihodi.filter(mjesec=trenutni_mjesec).first()
                
                if not prihod:
                    self.stdout.write(f'  ⏭️  {korisnik.ime} - Nema prihoda za {trenutni_mjesec}')
                    skipped_count += 1
                    continue
                
                # Kalkuliši iznose
                porez = prihod.iznos * Decimal('0.02')
                doprinosi = Decimal(str(settings.PROSJECNA_BRUTO_PLATA)) * Decimal('0.70')
                ukupno = porez + doprinosi
                
                # Email sadržaj
                subject = f'⏰ Podsjetnik: Uplata poreza za {trenutni_mjesec}'
                
                message = f"""Poštovani {korisnik.ime},

Podsjetnik za uplatu poreza i doprinosa za mjesec {trenutni_mjesec}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IZNOSI ZA UPLATU:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Porez na dohodak (2%): {porez} KM
• Doprinosi za zdravstvo (70%): {doprinosi} KM

UKUPNO ZA UPLATU: {ukupno} KM

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  ROK ZA UPLATU: 10. {today.month + 1}. 2025.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Možete kreirati uplatnice u ePauša RS sistemu.

Lijep pozdrav,
ePauša RS tim
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Automatska poruka. Ne odgovarajte na ovaj email.
"""
                
                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [korisnik.user.email],
                        fail_silently=False,
                    )
                    
                    # Log notifikaciju
                    EmailNotification.objects.create(
                        korisnik=korisnik,
                        notification_type='payment_reminder',
                        scheduled_date=timezone.now(),
                        sent=True,
                        sent_at=timezone.now(),
                        email_subject=subject,
                        email_body=message
                    )
                    
                    sent_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Email poslat: {korisnik.ime} ({korisnik.user.email})'))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Greška za {korisnik.ime}: {str(e)}'))
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'✅ Poslato {sent_count} email-ova'))
            self.stdout.write(self.style.WARNING(f'⏭️  Preskočeno {skipped_count} korisnika'))
            
        else:
            self.stdout.write(self.style.WARNING(f'📅 Danas nije 5. u mjesecu (danas je {today.day}.)'))
            self.stdout.write('   Email podsjetnici se šalju samo 5. u mjesecu.')
            self.stdout.write('')
            self.stdout.write('💡 Za testiranje, možeš ručno pozvati send_payment_reminder() funkciju.')
        
        self.stdout.write('')