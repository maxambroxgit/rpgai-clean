from django.shortcuts import render
from datetime import datetime

def home(request):
    hour = datetime.now().hour
    if hour < 6:
        callout_text = "Benvenuto, Viaggiatore delle Tenebre."
    elif hour < 12:
        callout_text = "Il mattino è silenzioso... troppo silenzioso."
    elif hour < 18:
        callout_text = "Il sole filtra nei cunicoli: sei ancora vivo."
    else:
        callout_text = "Benvenuto, Viaggiatore Notturno."

    return render(request, "home/home.html", {
        "callout_text": callout_text
    })
