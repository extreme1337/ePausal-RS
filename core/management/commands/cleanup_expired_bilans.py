from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Bilans
import os

class Command(BaseCommand):
    help = 'Očisti istekle bilanse (retention period expired)'

    def handle(self, *args, **kwargs):
        self.stdout.write('🗑️  Čišćenje isteklih bilansa...')
        self.stdout.write('')
        
        # Pronađi sve istekle bilanse
        istekli = Bilans.objects.filter(datum_isteka__lt=timezone.now())
        count = istekli.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ Nema isteklih bilansa za brisanje'))
            self.stdout.write('')
            return
        
        self.stdout.write(f'📋 Pronađeno {count} isteklih bilansa:')
        self.stdout.write('')
        
        # Obriši fajlove sa diska
        deleted_files = 0
        errors = 0
        
        for bilans in istekli:
            self.stdout.write(f'  🗑️  {bilans.korisnik.ime} - {bilans.od_mjesec}/{bilans.do_mjesec}')
            
            if bilans.fajl:
                try:
                    if os.path.isfile(bilans.fajl.path):
                        os.remove(bilans.fajl.path)
                        deleted_files += 1
                        self.stdout.write(f'     └─ Fajl obrisan: {bilans.fajl.name}')
                except Exception as e:
                    errors += 1
                    self.stdout.write(self.style.WARNING(f'     └─ ⚠️  Greška: {e}'))
        
        # Obriši iz baze
        istekli.delete()
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Obrisano {count} bilansa'))
        self.stdout.write(self.style.SUCCESS(f'📁 Obrisano {deleted_files} fajlova sa diska'))
        
        if errors > 0:
            self.stdout.write(self.style.WARNING(f'⚠️  {errors} greška/e prilikom brisanja fajlova'))
        
        self.stdout.write('')