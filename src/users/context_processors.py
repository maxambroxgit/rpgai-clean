# tua_app/context_processors.py

def gtm_user_data(request):
    """
    Aggiunge dati utente al contesto di ogni template per GTM.
    Questo ci dice CHI è l'utente su ogni pagina.
    """
    user_data = {
        'is_logged_in': False,
        'user_type': 'anonymous',
        'user_id': None
    }

    if request.user.is_authenticated:
        user_data['is_logged_in'] = True
        user_data['user_type'] = 'registered'
        user_data['user_id'] = request.user.id

    return {'gtm_user_data': user_data}