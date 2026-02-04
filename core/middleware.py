from django.utils import timezone
from datetime import timedelta
from .models import Korisnik


class SubscriptionMiddleware:
    """Middleware koji provjerava da li je korisnikova pretplata aktivna"""

    def __init__(self, get_response):
        self.get_response = get_response

        # URL-ovi koji su dozvoljeni čak i sa isteklom pretplatom
        self.allowed_paths = [
            "/login/",
            "/logout/",
            "/register/",
            "/payment/",
            "/static/",
            "/media/",
            "/admin/",
        ]

    def __call__(self, request):
        # Provjeri da li je korisnik ulogovan
        if request.user.is_authenticated and not request.user.is_staff:
            # Provjeri da li path nije u allowed paths
            if not any(request.path.startswith(path) for path in self.allowed_paths):
                try:
                    korisnik = Korisnik.objects.get(user=request.user)

                    # Izračunaj datum isteka
                    if korisnik.trial_end_date:
                        datum_isteka = korisnik.trial_end_date
                    else:
                        # Ako nema trial_end_date, postavi default od registracije
                        datum_isteka = korisnik.registrovan + timedelta(days=30)
                        korisnik.trial_end_date = datum_isteka
                        korisnik.save()

                    today = timezone.now().date()

                    # Provjeri da li je pretplata istekla
                    if today > datum_isteka:
                        request.subscription_expired = True
                        request.expired_date = datum_isteka
                        request.days_expired = (today - datum_isteka).days
                    else:
                        request.subscription_expired = False

                except Korisnik.DoesNotExist:
                    pass

        response = self.get_response(request)
        return response
