from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import requests
import json, re, os, random
from django.contrib import messages as flash
from decouple import config
from datetime import datetime

API_KEY = config("API_KEY")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
LOG_DIR = "blamPunk/saves"
STARTING_HP = 20

system_prompt = (
    "Agisci come un Dungeon Master AI immerso in un mondo ispirato a *Blame!* di Tsutomu Nihei: "
    "strutture infinite, silenzio opprimente, creature biomeccaniche e città labirintiche. "
    "Narrazione frammentata, ruvida, nello stile di Chuck Palahniuk. "
    "Sei la voce che guida il giocatore. Mai spiegazioni fuori dal contesto narrativo. "
    "Non descrivere te stesso come un'AI. Il giocatore è l'unico umano conosciuto. "
    "Quando il giocatore perde punti ferita, rispondi utilizzando la stringa 'Hai perso N punti ferita' "
    "con N uguale ai punti ferita persi. "
    "Quando il giocatore raccoglie qualcosa, rispondi tipo con 'Hai raccolto l'oggetto'. "
    "Guida la storia un passo alla volta e, alla fine di ogni scena, chiedi: 'Cosa fai adesso?'."
)

consumabili = {
    "medikit": 5,
    "siringa": 3,
    "kit di pronto soccorso": 10
}

@csrf_exempt
def reset_session(request):
    request.session.pop("blame_messages", None)
    request.session.pop("hp", None)
    request.session.pop("inventario", None)
    return redirect(reverse("blamPunk:chat-dark"))

@csrf_exempt
def chat_V2(request):
    messages = request.session.get("blame_messages")
    hp = request.session.get("hp")
    inventario = request.session.get("inventario")

    if not messages or not isinstance(hp, int) or not isinstance(inventario, list):
        messages = [{"role": "system", "content": system_prompt}]
        hp = STARTING_HP
        inventario = []
        stato_hp = f"[INFO] Il personaggio ha attualmente {hp} punti ferita."
        stato_inventario = f"[INFO] Il personaggio non possiede oggetti."
        messages.append({"role": "user", "content": stato_hp + " " + stato_inventario})

    if request.method == "POST":
        # Check se uso oggetto dal <select>
        item_selected = request.POST.get("use_item")
        if item_selected in inventario and item_selected in consumabili:
            cura = consumabili[item_selected]
            hp = min(hp + cura, STARTING_HP)
            inventario.remove(item_selected)
            messages.append({"role": "user", "content": f"[AZIONE] Hai usato '{item_selected}' e recuperato {cura} HP. HP attuali: {hp}"})
            flash.add_message(request, flash.SUCCESS, f"💊 Hai usato '{item_selected}' e recuperato {cura} HP.")

            request.session["blame_messages"] = messages
            request.session["hp"] = hp
            request.session["inventario"] = inventario

            return render(request, "blamPunk/chat_dark.html", {
                "messages_log": messages,
                "hp": hp,
                "game_state": {
                    "hp": hp,
                    "level": 1,
                    "inventory": inventario
                },
                "username": request.user.username if request.user.is_authenticated else "User"
            })

        user_input = request.POST.get("user_input", "").strip()

        if user_input.lower() == "quit":
            request.session["blame_messages"] = messages
            request.session["hp"] = hp
            request.session["inventario"] = inventario
            return render(request, "blamPunk/chat.html", {
                "messages_log": messages,
                "hp": hp,
                "game_over": True
            })

        if "d20" in user_input.lower():
            roll = random.randint(1, 20)
            user_input = user_input.replace("d20", f"**TIRO D20: {roll}**")

        messages.append({"role": "user", "content": user_input})

        response = requests.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            },
            json={
                "model": MODEL,
                "messages": messages
            }
        )

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": reply})

            # Parsing perdita HP
            match = re.search(r"\bHai perso\s+(\d+)\s+(?:punti\s+ferita|hp)\b", reply, re.IGNORECASE)
            if match:
                try:
                    danno = int(match.group(1))
                    if 0 <= danno <= STARTING_HP:
                        hp = max(hp - danno, 0)
                        messages.append({"role": "user", "content": f"[INFO] Hai perso {danno} HP. HP attuali: {hp}"})
                        flash.add_message(request, flash.WARNING, f"🩸 Hai perso {danno} punti ferita! HP attuali: {hp}")
                except (ValueError, TypeError):
                    pass

            # Parsing oggetti raccolti
            oggetti = re.findall(r"Hai raccolto\s+(?:un[oa]?|il|lo|la|le|gli|i)\s+([\w\s]+?)(?:\.|\n|$)", reply, re.IGNORECASE)
            for oggetto in oggetti:
                oggetto = oggetto.strip().lower()
                if oggetto not in inventario:
                    inventario.append(oggetto)
                    messages.append({"role": "user", "content": f"[INFO] Hai raccolto: {oggetto}"})
                    flash.add_message(request, flash.INFO, f"📦 Oggetto aggiunto all'inventario: {oggetto}")

            request.session["blame_messages"] = messages
            request.session["hp"] = hp
            request.session["inventario"] = inventario

            # Salvataggio su file JSON
            session_data = {
                "messages": messages,
                "hp": hp,
                "inventario": inventario
            }
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}_{timestamp}.json"
            file_path = os.path.join(LOG_DIR, filename)

            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(session_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                flash.add_message(request, flash.ERROR, f"Errore nel salvataggio automatico: {e}")

            if hp <= 0:
                return render(request, "blamPunk/chat.html", {
                    "messages_log": messages,
                    "hp": hp,
                    "game_over": True
                })
        else:
            flash.add_message(request, flash.ERROR, "Errore nella risposta dell'AI. Riprova più tardi.")

    game_state = {
        "hp": hp,
        "level": 1,
        "inventory": inventario
    }

    return render(request, "blamPunk/chat_dark.html", {
        "messages_log": messages,
        "hp": hp,
        "game_state": game_state,
        "username": request.user.username if request.user.is_authenticated else "User"
    })

def load_game_list(request):
    """
    Mostra una pagina con l'elenco dei file di salvataggio
    per l'utente corrente.
    """
    # Costruisci il prefisso del file per filtrare i salvataggi
    user_prefix = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}"
    saved_games = []
    
    if os.path.exists(LOG_DIR):
        for f in os.listdir(LOG_DIR):
            # Mostra solo i file json che appartengono all'utente
            if f.startswith(user_prefix) and f.endswith(".json"):
                saved_games.append(f)
    
    # Ordina i salvataggi dal più recente al più vecchio
    saved_games.sort(reverse=True)

    return render(request, "blamPunk/load_game.html", {"saved_games": saved_games})


def load_game_session(request, filename):
    """
    Carica i dati da un file JSON specifico nella sessione dell'utente
    e lo reindirizza alla chat.
    """
    # Controllo di sicurezza: l'utente può caricare solo i suoi file
    user_prefix = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}"
    if not filename.startswith(user_prefix):
        flash.add_message(request, flash.ERROR, "Accesso non autorizzato a questo salvataggio.")
        return redirect(reverse("bmovie:chat"))

    file_path = os.path.join(LOG_DIR, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        
        # Popola la sessione con i dati caricati
        request.session["bzak_messages"] = session_data.get("messages")
        request.session["hp"] = session_data.get("hp")
        request.session["inventario"] = session_data.get("inventario")
        # Aggiungi qui altre variabili di gioco che potresti salvare, come gli "stats"
        # request.session["stats"] = session_data.get("stats") 

        flash.add_message(request, flash.SUCCESS, f"Partita '{filename}' caricata con successo!")
    except FileNotFoundError:
        flash.add_message(request, flash.ERROR, "File di salvataggio non trovato.")
    except Exception as e:
        flash.add_message(request, flash.ERROR, f"Errore nel caricamento della partita: {e}")

    return redirect(reverse("blamPunk:chat-dark"))