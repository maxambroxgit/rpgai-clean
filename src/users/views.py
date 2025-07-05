# tua_app/views.py
from django.shortcuts import render
from django.contrib import messages  # Importa il framework dei messaggi

# ... le tue altre view ...

def registration_complete_view(request):
    """
    Questa view viene mostrata subito dopo una registrazione andata a buon fine.
    È il posto perfetto per inviare il nostro evento a GTM.
    """
    # --- ECCO IL NOSTRO CODICE PER GTM ---
    gtm_event_data = "{'event': 'registration_complete', 'auth_method': 'email'}"
    messages.success(request, gtm_event_data, extra_tags='gtm_event')
    # ------------------------------------

    # Renderizza un semplice template di "Benvenuto"
    return render(request, 'django_registration/registration_complete.html')