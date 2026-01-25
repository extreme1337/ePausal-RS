from django.core.management.base import BaseCommand
from core.models import Currency
from decimal import Decimal

class Command(BaseCommand):
    help = 'Ažuriraj kursnu listu valuta'

    def handle(self, *args, **kwargs):
        self.stdout.write('💱 Ažuriranje exchange rates...')
        self.stdout.write('')
        
        currencies_data = [
            {'code': 'EUR', 'name': 'Euro', 'rate': Decimal('1.96')},
            {'code': 'USD', 'name': 'US Dollar', 'rate': Decimal('1.75')},
            {'code': 'GBP', 'name': 'British Pound', 'rate': Decimal('2.28')},
            {'code': 'CHF', 'name': 'Swiss Franc', 'rate': Decimal('2.02')},
        ]
        
        updated_count = 0
        
        for data in currencies_data:
            currency, created = Currency.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'rate_to_km': data['rate']
                }
            )
            
            if created:
                self.stdout.write(f"  ✅ Kreiran: {data['code']} - {data['rate']} KM")
            else:
                self.stdout.write(f"  🔄 Ažuriran: {data['code']} - {data['rate']} KM")
            
            updated_count += 1
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Ažurirano {updated_count} valuta!'))
        self.stdout.write('')