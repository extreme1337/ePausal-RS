from django.core.management.base import BaseCommand
from core.models import Korisnik, PredictiveAnalytics
from decimal import Decimal


class Command(BaseCommand):
    help = 'Generiši AI predikcije prihoda za sve korisnike'

    def handle(self, *args, **kwargs):
        self.stdout.write('🤖 Generisanje AI predikcija...\n')

        korisnici = Korisnik.objects.all()
        total_predictions = 0

        for korisnik in korisnici:
            prihodi = korisnik.prihodi.order_by('mjesec')

            if prihodi.count() < 3:
                self.stdout.write(
                    f'  ⏭️  {korisnik.ime} - Nedovoljno podataka (min 3 mjeseca)'
                )
                continue

            # ✅ UZMI POSLEDNJIH 6 MESECI (Django-safe)
            last_prihodi = list(prihodi.order_by('-mjesec')[:6])
            last_prihodi.reverse()  # hronološki redosled

            iznosi = [float(p.iznos) for p in last_prihodi]

            avg = sum(iznosi) / len(iznosi)

            trend = 0
            if len(iznosi) >= 2:
                trend = (iznosi[-1] - iznosi[0]) / len(iznosi)

            last_month = prihodi.last().mjesec
            year, month = map(int, last_month.split('-'))

            korisnik_predictions = []

            for i in range(1, 4):
                month += 1
                if month > 12:
                    month = 1
                    year += 1

                predicted_amount = avg + (trend * i)
                confidence = max(50, 95 - (i * 10))

                pred, created = PredictiveAnalytics.objects.update_or_create(
                    korisnik=korisnik,
                    mjesec=f'{year}-{str(month).zfill(2)}',
                    defaults={
                        'predicted_income': Decimal(str(round(predicted_amount, 2))),
                        'confidence': Decimal(confidence)
                    }
                )

                korisnik_predictions.append(pred)
                total_predictions += 1

            self.stdout.write(self.style.SUCCESS(
                f'  ✅ {korisnik.ime}: {len(korisnik_predictions)} predikcija'
            ))

        self.stdout.write('\n' + self.style.SUCCESS(
            f'✅ Generisano {total_predictions} predikcija za {korisnici.count()} korisnika!'
        ) + '\n')
