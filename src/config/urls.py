"""
URL configuration for rpgAI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import path, include, reverse_lazy
from django_registration.backends.one_step.views import RegistrationView
from users.forms import customUserRegistrationForm
from users.views import registration_complete_view
from django.contrib.sitemaps.views import sitemap
from users.sitemaps import StaticViewSitemap, GameSitemap
from django.views.generic.base import TemplateView # Importa TemplateView



# Crea un dizionario che mappa un nome a ogni classe sitemap
sitemaps = {
    'static': StaticViewSitemap,
    'games': GameSitemap,
    # Se avessi una sitemap per modelli, la aggiungeresti qui:
    # 'game-details': GameDetailSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('blampunk/', include('blamPunk.urls', namespace="blamPunk")),
    path('bmovie/', include('bmovie.urls', namespace="bmovie")),
    path('hacker-game/', include('hackergame.urls', namespace="hackergame")),
    path('ade/', include('ade.urls', namespace="ade")),
    path('', include('home.urls', namespace="home")),
    path("privacy/", TemplateView.as_view(template_name="privacy-policy.html"), name="privacy"),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', RegistrationView.as_view(
        form_class=customUserRegistrationForm,
        success_url=reverse_lazy("registration_complete")
    ),
        name = "djang_registration_register"),
    path("accounts/register/complete/", registration_complete_view, name='registration_complete'
        #TemplateView.as_view(template_name="django_registration/registration_complete.html"),
    ),

    path(
        "sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")
    ),

]
