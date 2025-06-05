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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('blampunk/', include('blamPunk.urls', namespace="blamPunk")),
    path('', include('home.urls', namespace="home")),
    path("privacy/", TemplateView.as_view(template_name="privacy-policy.html"), name="privacy"),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', RegistrationView.as_view(
        form_class=customUserRegistrationForm,
        success_url=reverse_lazy("registration_complete")
    ),
        name = "djang_registration_register"),
    path("accounts/register/complete/",
        TemplateView.as_view(template_name="django_registration/registration_complete.html"),
        name="registration_complete"
    ),

]
