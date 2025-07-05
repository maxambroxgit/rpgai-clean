# users/signals.py

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib import messages

# Il decoratore @receiver collega la nostra funzione al segnale user_logged_in
@receiver(user_logged_in)
def send_gtm_login_event(sender, request, user, **kwargs):
    """
    Questa funzione viene eseguita AUTOMATICAMENTE dopo ogni login andato a buon fine,
    indipendentemente da dove o come è avvenuto il login.
    """
    # Prepariamo la stringa per il dataLayer di GTM
    gtm_event_data = "{'event': 'login', 'auth_method': 'email'}"

    # Usiamo il framework dei messaggi di Django per passare l'evento al template
    messages.success(request, gtm_event_data, extra_tags='gtm_event')