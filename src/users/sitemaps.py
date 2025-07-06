# users/sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    """
    Sitemap per le pagine statiche del sito (pagine che non dipendono da oggetti del database).
    """
    priority = 0.8  # Priorità da 0.0 a 1.0
    changefreq = 'weekly' # Frequenza di aggiornamento: always, hourly, daily, weekly, monthly, yearly, never

    def items(self):
        # Restituisce una lista di nomi di URL (quelli che hai definito in urls.py)
        return ['home:home', 'login', 'djang_registration_register']

    def location(self, item):
        # Per ogni nome di URL nella lista sopra, Django calcola l'URL completo
        return reverse(item)

class GameSitemap(Sitemap):
    """
    Sitemap per le pagine principali dei giochi.
    """
    priority = 0.9
    changefreq = 'monthly'

    def items(self):
        # Qui elenchiamo i nomi degli URL delle pagine principali dei tuoi giochi
        return ['blamPunk:chat-dark', 'bmovie:chat'] # Assumendo che questi siano i nomi corretti

    def location(self, item):
        return reverse(item)

# Potresti anche creare sitemap per oggetti dinamici del database.
# Esempio ipotetico se avessi un modello "Game" con le pagine dei giochi:
#
# from blamPunk.models import Game
#
# class GameDetailSitemap(Sitemap):
#     changefreq = "weekly"
#     priority = 0.7
#
#     def items(self):
#         return Game.objects.filter(is_public=True) # Prendi tutti i giochi pubblici
#
#     def lastmod(self, obj):
#         return obj.updated_at # Usa un campo data per dire a Google quando la pagina è cambiata