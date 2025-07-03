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
    "Quando il giocatore tenta un'azione incerta (persuadere, schivare, indagare), richiedi un tiro di abilità. "
    "Ad esempio: 'Per convincere l'alieno, fai un tiro di Carisma'. Il giocatore risponderà con 'tiro d20 Carisma'."
    "Altro esempio: sil giocatore vuole esplorare, cercare o scoprire, fai un tiro Cervello. Il giocatore risponderà con 'tiro d20 Cervello'"
    "Quando un obiettivo importante viene completato o uno nuovo viene scoperto, comunicalo usando la stringa speciale: [OBJECTIVE] Il nuovo obiettivo è..."
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

def check_for_level_up(request):
    """
    Controlla se il giocatore ha completato abbastanza obiettivi per salire di livello.
    Se sì, aggiorna il livello, le statistiche e invia un messaggio di notifica.
    Restituisce True se il level up è avvenuto, altrimenti False.
    """
    # Carica i dati correnti dalla sessione

    stats = request.session.get("stats", {})

    # --- BLOCCO DI SICUREZZA AGGIUNTO ---
    # Se il dizionario stats è vuoto (perché caricato da un vecchio salvataggio),
    # lo inizializziamo con i valori di default prima di procedere.
    if not stats:
        stats = {"Carisma": 2, "Prontezza": 1, "Cervello": 3, "Fegato": 0}
        # (Opzionale ma consigliato) Salva le stats appena create nella sessione
        request.session["stats"] = stats
    # --- FINE BLOCCO DI SICUREZZA ---

    level = request.session.get("level", 1)
    objectives_completed = request.session.get("objectives_completed", 0)
    
    # Definisci la soglia per il level up (es. 10 obiettivi)
    # Potresti renderla dinamica, es. 10 * level
    objectives_needed = 10
    
    if objectives_completed >= objectives_needed:
        # --- LEVEL UP! ---
        
        # 1. Aumenta il livello
        new_level = level + 1
        request.session["level"] = new_level
        
        # 2. Resetta il contatore degli obiettivi per il prossimo livello
        # (sottraendo quelli già usati per questo level up)
        request.session["objectives_completed"] = objectives_completed - objectives_needed
        
        # 3. Aumenta le statistiche (logica di esempio)
        # Qui puoi essere creativo. Aumentiamo ogni stat di 1.
        for stat_name in stats.keys():
            stats[stat_name] += 1
        request.session["stats"] = stats
        
        # 4. (Opzionale) Aumenta anche gli HP massimi/correnti
        hp = request.session.get("hp", 100)
        hp += 10 # Aumento di esempio
        request.session["hp"] = hp
        
        # 5. Crea un messaggio di notifica per il giocatore
        level_up_message = (
            f"🎉 **LEVEL UP!** 🎉\n"
            f"Hai raggiunto il livello **{new_level}**!\n"
            f"Le tue statistiche sono aumentate! Ora sono:\n"
            f"Carisma: {stats['Carisma']}, Prontezza: {stats['Prontezza']}, "
            f"Cervello: {stats['Cervello']}, Fegato: {stats['Fegato']}.\n"
            f"I tuoi HP sono stati ricaricati e aumentati a {hp}!"
        )
        flash.add_message(request, flash.SUCCESS, level_up_message)
        
        return True # Level up avvenuto
        
    return False # Nessun level up

@csrf_exempt
def chat_V2(request):
    messages = request.session.get("blame_messages", [])
    hp = request.session.get("hp")
    inventario = request.session.get("inventario")

    if not messages or not isinstance(hp, int) or not isinstance(inventario, list):
        messages = [{"role": "system", "content": system_prompt}]
        hp = STARTING_HP
        inventario = []
        stato_hp = f"[INFO] Il personaggio ha attualmente {hp} punti ferita."
        stato_inventario = f"[INFO] Il personaggio non possiede oggetti."        
        request.session["objective"] = "Scopri dove ti trovi"       

        #INIZIALIZZAZIONE DELLE CARATTERISTICHE
        initial_stats = {"Carisma": 2, "Prontezza": 1, "Cervello": 3, "Fegato": 0}
        request.session["stats"] = initial_stats

        # CAMPI PER LA PROGRESSIONE DEL LIVELLO
        request.session["level"] = 1
        request.session["objectives_completed"] = 0

        messages.append({"role": "user", "content": stato_hp + " " + stato_inventario})

    if request.method == "POST":
        # Check se uso oggetto dal <select>
        item_selected = request.POST.get("use_item")
        if item_selected in inventario and item_selected in consumabili:
            cura = consumabili[item_selected]
            hp = min(hp + cura, STARTING_HP)
            inventario.remove(item_selected)
            flash.add_message(request, flash.SUCCESS, f"💊 Hai usato '{item_selected}' e recuperato {cura} HP. HP attuali: {hp}")

            request.session["blame_messages"] = messages
            request.session["hp"] = hp
            request.session["inventario"] = inventario
            request.session["stats"] = stats


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
            stats = request.session.get("stats", {})
            match = re.search(r"d20\s+(\w+)", user_input, re.IGNORECASE)
            skill_name = match.group(1).capitalize() if match else None
            
            roll = random.randint(1, 20)
            modifier = stats.get(skill_name, 0)
            total = roll + modifier

            roll_result = f"**TIRO D20 ({skill_name or 'Generico'}): {roll} + {modifier} = {total}**"

            user_input = user_input.replace("d20", roll_result)
            


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
                        flash.add_message(request, flash.WARNING, f"🩸 Hai perso {danno} punti ferita! HP attuali: {hp}")
                except (ValueError, TypeError):
                    pass

            # Parsing OBIETTIVI
            obj_match = re.search(r"\[OBJECTIVE\]\s*(.*)", reply, re.IGNORECASE)
            if obj_match:
                new_objective = obj_match.group(1).strip()
                request.session["objective"] = new_objective
                flash.add_message(request, flash.INFO, f"🎯 Nuovo obiettivo: {new_objective}")

                # 2. Incrementa il contatore degli obiettivi completati
                # Usiamo .get(key, 0) + 1 per sicurezza se la chiave non esistesse
                current_completed = request.session.get("objectives_completed", 0)
                request.session["objectives_completed"] = current_completed + 1
                
                # 3. CHIAMA LA NUOVA FUNZIONE PER IL CONTROLLO DEL LEVEL UP!
                # Questo è il punto perfetto per farlo.
                check_for_level_up(request)

            # Parsing oggetti raccolti
            oggetti = re.findall(r"Hai raccolto\s+(?:un[oa]?|il|lo|la|le|gli|i)\s+([\w\s]+?)(?:\.|\n|$)", reply, re.IGNORECASE)
            for oggetto in oggetti:
                oggetto = oggetto.strip().lower()
                if oggetto not in inventario:
                    inventario.append(oggetto)
                    flash.add_message(request, flash.INFO, f"📦 Oggetto aggiunto all'inventario: {oggetto}")

            request.session["blame_messages"] = messages
            request.session["hp"] = hp
            request.session["inventario"] = inventario

            # Salvataggio su file JSON
            session_data = {
                "messages": messages,
                "hp": hp,
                "inventario": inventario,
                "objective": request.session["objective"]
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

    

    messages_for_template = [msg for msg in messages if msg.get("role") != "system"]

    context = {
        'messages_log': messages_for_template,  # <-- USA LA LISTA FILTRATA
        'username': request.user.username if request.user.is_authenticated else 'Giocatore',
        'hp': request.session.get("hp"),
        'inventario': request.session.get("inventario"),
        'objective': request.session.get("objective"),
        'level': request.session.get("level"),
        'stats': request.session.get("stats"),
    }

    return render(request, "blamPunk/chat_dark.html", context)


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