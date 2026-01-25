from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import *
from decimal import Decimal
from datetime import date

class Command(BaseCommand):
    help = 'Učitaj sve dummy test podatke za demo'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🚀 Učitavanje dummy podataka...'))
        self.stdout.write('')
        
        # ============================================
        # 1. JELENA - Enterprise
        # ============================================
        
        self.stdout.write('👤 Kreiranje: Jelena Jovanović (Enterprise)...')
        
        user_jelena, created = User.objects.get_or_create(
            username='jelena@techsolutions.rs',
            email='jelena@techsolutions.rs',
            defaults={'first_name': 'Jelena', 'last_name': 'Jovanović'}
        )
        if created:
            user_jelena.set_password('jelena123')
            user_jelena.save()
        
        korisnik_jelena, _ = Korisnik.objects.get_or_create(
            user=user_jelena,
            defaults={
                'ime': 'Jelena Jovanović',
                'plan': 'Enterprise',
                'jib': '4512358270004',
                'racun': '562-008-81727093-99'
            }
        )
        
        # Prihodi
        mjeseci_prihodi = [25600, 23450, 27890, 26120, 28340, 24780, 26550, 29120, 27340, 25890]
        for i, iznos in enumerate(mjeseci_prihodi, 1):
            Prihod.objects.get_or_create(
                korisnik=korisnik_jelena,
                mjesec=f'2025-{str(i).zfill(2)}',
                defaults={'iznos': Decimal(iznos)}
            )
        
        # Fakture
        fakture_jelena = [
            ('F001/25', date(2025, 1, 3), 'MICROSOFT IRELAND OPERATIONS LTD', 25600, 'Plaćena', 'Enterprise cloud consulting - Azure'),
            ('F002/25', date(2025, 2, 10), 'GOOGLE IRELAND LIMITED', 23450, 'Plaćena', 'GCP optimization'),
            ('F003/25', date(2025, 3, 17), 'AMAZON WEB SERVICES EMEA SARL', 27890, 'Plaćena', 'AWS implementation'),
            ('F004/25', date(2025, 4, 8), 'IBM EUROPE', 26120, 'Plaćena', 'AI integration'),
            ('F005/25', date(2025, 5, 22), 'ORACLE CORPORATION UK LTD', 28340, 'Plaćena', 'Database migration'),
            ('F006/25', date(2025, 6, 15), 'SAP SE', 24780, 'Na čekanju', 'ERP integration'),
        ]
        
        for broj, datum, klijent, iznos, status, opis in fakture_jelena:
            Faktura.objects.get_or_create(
                korisnik=korisnik_jelena,
                broj=broj,
                defaults={
                    'datum': datum,
                    'klijent': klijent,
                    'iznos': Decimal(iznos),
                    'status': status,
                    'opis': opis
                }
            )
        
        # Email Inbox
        inbox_jelena = [
            ('MICROSOFT IRELAND OPERATIONS LTD', 15000, 'Azure consulting Q1', date(2025, 1, 20), 98),
            ('GOOGLE IRELAND LIMITED', 12500, 'GCP development', date(2025, 1, 18), 97),
            ('AMAZON WEB SERVICES EMEA SARL', 8900, 'AWS architecture', date(2025, 1, 15), 96),
        ]
        
        for klijent, iznos, svrha, datum_trans, confidence in inbox_jelena:
            EmailInbox.objects.get_or_create(
                korisnik=korisnik_jelena,
                klijent=klijent,
                datum_transakcije=datum_trans,
                defaults={
                    'from_email': 'izvod@nlb.rs',
                    'iznos': Decimal(iznos),
                    'svrha': svrha,
                    'confidence': confidence,
                    'potvrdjeno': False
                }
            )
        
        # Uplatnice
        Uplatnica.objects.get_or_create(
            korisnik=korisnik_jelena,
            datum=date(2025, 1, 8),
            primalac='PURS',
            defaults={'iznos': Decimal('512.00'), 'svrha': 'Porez na dohodak 01/2025'}
        )
        
        Uplatnica.objects.get_or_create(
            korisnik=korisnik_jelena,
            datum=date(2025, 1, 8),
            primalac='FZO RS',
            defaults={'iznos': Decimal('665.26'), 'svrha': 'Doprinosi 01/2025'}
        )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Jelena kreirana!'))
        
        # ============================================
        # 2. ANA - Professional
        # ============================================
        
        self.stdout.write('👤 Kreiranje: Ana Anić (Professional)...')
        
        user_ana, created = User.objects.get_or_create(
            username='ana.anic@consultant.rs',
            email='ana.anic@consultant.rs',
            defaults={'first_name': 'Ana', 'last_name': 'Anić'}
        )
        if created:
            user_ana.set_password('ana123')
            user_ana.save()
        
        korisnik_ana, _ = Korisnik.objects.get_or_create(
            user=user_ana,
            defaults={
                'ime': 'Ana Anić',
                'plan': 'Professional',
                'jib': '4512358270002',
                'racun': '562-008-81727093-98'
            }
        )
        
        # Prihodi
        ana_prihodi = [6250, 5890, 7120, 6450, 6880, 5920, 6340, 7050, 6570, 6290]
        for i, iznos in enumerate(ana_prihodi, 1):
            Prihod.objects.get_or_create(
                korisnik=korisnik_ana,
                mjesec=f'2025-{str(i).zfill(2)}',
                defaults={'iznos': Decimal(iznos)}
            )
        
        # Email Inbox - NLB izvodi
        ana_inbox = [
            ('LECIC MIRJANA', 35, 'OBJAVA VELIKA ID 37146', date(2025, 12, 10), 95),
            ('PTT-RADENKO BRKIC', 20, 'OBJAVA ID 37125', date(2025, 12, 10), 96),
            ('PTT-GORAN ANDJELIC', 20, 'OBJAVA OSNOVNA ID 37181', date(2025, 12, 10), 92),
            ('NEBOJSA SUSIC', 20, 'OBJAVA ID 37158', date(2025, 12, 3), 94),
            ('BORILOVIC MIRJANA', 20, 'OBJAVA/OSNOVNA/ ID 36887', date(2025, 12, 3), 93),
        ]
        
        for klijent, iznos, svrha, datum_trans, confidence in ana_inbox:
            EmailInbox.objects.get_or_create(
                korisnik=korisnik_ana,
                klijent=klijent,
                datum_transakcije=datum_trans,
                defaults={
                    'from_email': 'izvod@nlb.rs',
                    'iznos': Decimal(iznos),
                    'svrha': svrha,
                    'confidence': confidence
                }
            )
        
        # Fakture
        Faktura.objects.get_or_create(
            korisnik=korisnik_ana,
            broj='F001/25',
            defaults={
                'datum': date(2025, 1, 8),
                'klijent': 'MEGA DOO Banja Luka',
                'iznos': Decimal('6250.00'),
                'status': 'Plaćena',
                'opis': 'Business consulting'
            }
        )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Ana kreirana!'))
        
        # ============================================
        # 3. PETAR - Business
        # ============================================
        
        self.stdout.write('👤 Kreiranje: Petar Petrović (Business)...')
        
        user_petar, created = User.objects.get_or_create(
            username='petar@gradevina-plus.com',
            email='petar@gradevina-plus.com',
            defaults={'first_name': 'Petar', 'last_name': 'Petrović'}
        )
        if created:
            user_petar.set_password('petar123')
            user_petar.save()
        
        korisnik_petar, _ = Korisnik.objects.get_or_create(
            user=user_petar,
            defaults={
                'ime': 'Petar Petrović',
                'plan': 'Business',
                'jib': '4512358270003',
                'racun': '562-008-81727093-92'
            }
        )
        
        # Prihodi
        petar_prihodi = [12450, 11890, 13670, 14220, 12880, 13450, 11920, 14560, 13110, 12780]
        for i, iznos in enumerate(petar_prihodi, 1):
            Prihod.objects.get_or_create(
                korisnik=korisnik_petar,
                mjesec=f'2025-{str(i).zfill(2)}',
                defaults={'iznos': Decimal(iznos)}
            )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Petar kreiran!'))
        
        # ============================================
        # 4. MARKO - Starter
        # ============================================
        
        self.stdout.write('👤 Kreiranje: Marko Marković (Starter)...')
        
        user_marko, created = User.objects.get_or_create(
            username='marko.markovic@gmail.com',
            email='marko.markovic@gmail.com',
            defaults={'first_name': 'Marko', 'last_name': 'Marković'}
        )
        if created:
            user_marko.set_password('marko123')
            user_marko.save()
        
        korisnik_marko, _ = Korisnik.objects.get_or_create(
            user=user_marko,
            defaults={
                'ime': 'Marko Marković',
                'plan': 'Starter',
                'jib': '4512358270001',
                'racun': '562-008-81727093-91'
            }
        )
        
        # Prihodi
        marko_prihodi = [2350.50, 2180, 2890, 2125, 2670.50, 2440, 2290, 2755, 2510, 2380]
        for i, iznos in enumerate(marko_prihodi, 1):
            Prihod.objects.get_or_create(
                korisnik=korisnik_marko,
                mjesec=f'2025-{str(i).zfill(2)}',
                defaults={'iznos': Decimal(str(iznos))}
            )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Marko kreiran!'))
        
        # ============================================
        # 5. CURRENCIES
        # ============================================
        
        self.stdout.write('💱 Kreiranje valuta...')
        
        Currency.objects.get_or_create(code='EUR', defaults={'name': 'Euro', 'rate_to_km': Decimal('1.96')})
        Currency.objects.get_or_create(code='USD', defaults={'name': 'US Dollar', 'rate_to_km': Decimal('1.75')})
        Currency.objects.get_or_create(code='GBP', defaults={'name': 'British Pound', 'rate_to_km': Decimal('2.28')})
        Currency.objects.get_or_create(code='CHF', defaults={'name': 'Swiss Franc', 'rate_to_km': Decimal('2.02')})
        
        self.stdout.write(self.style.SUCCESS('  ✅ 4 valute kreirane!'))
        
        # ============================================
        # 6. SYSTEM LOGS (demo)
        # ============================================
        
        self.stdout.write('📊 Kreiranje demo system logs...')
        
        SystemLog.objects.get_or_create(
            user=user_ana,
            action='LOGIN',
            defaults={'status': 'success', 'ip_address': '78.45.123.90'}
        )
        
        SystemLog.objects.get_or_create(
            user=user_jelena,
            action='GENERATE_INVOICE',
            defaults={'status': 'success', 'ip_address': '92.55.67.34'}
        )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Demo logs kreirani!'))
        
        # ============================================
        # 7. FAILED REQUESTS (demo)
        # ============================================
        
        self.stdout.write('⚠️  Kreiranje demo failed requests...')
        
        FailedRequest.objects.get_or_create(
            user=user_ana,
            action='EMAIL_FETCH',
            defaults={'error': 'Connection timeout', 'retryable': True}
        )
        
        FailedRequest.objects.get_or_create(
            user=user_petar,
            action='API_CALL',
            defaults={'error': 'Rate limit exceeded', 'retryable': True}
        )
        
        self.stdout.write(self.style.SUCCESS('  ✅ Demo failed requests kreirani!'))
        
        # ============================================
        # SUMMARY
        # ============================================
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('✅ SVE DUMMY PODACI USPJEŠNO UČITANI!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write('👥 TEST NALOZI:')
        self.stdout.write('   • Jelena (Enterprise): jelena@techsolutions.rs / jelena123')
        self.stdout.write('   • Ana (Professional): ana.anic@consultant.rs / ana123')
        self.stdout.write('   • Petar (Business): petar@gradevina-plus.com / petar123')
        self.stdout.write('   • Marko (Starter): marko.markovic@gmail.com / marko123')
        self.stdout.write('')
        self.stdout.write('📊 PODACI:')
        self.stdout.write(f'   • {Korisnik.objects.count()} korisnika')
        self.stdout.write(f'   • {Prihod.objects.count()} prihoda')
        self.stdout.write(f'   • {Faktura.objects.count()} faktura')
        self.stdout.write(f'   • {EmailInbox.objects.count()} inbox transakcija')
        self.stdout.write(f'   • {Currency.objects.count()} valuta')
        self.stdout.write('')
        self.stdout.write('🚀 Pokreni server: python manage.py runserver')
        self.stdout.write('🌐 Otvori: http://127.0.0.1:8000/')
        self.stdout.write('')