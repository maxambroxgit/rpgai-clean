

"""
File refattorizzato da Gemini per dimostrare una struttura del codice migliorata.

Modifiche principali:
1.  **Separazione delle Responsabilità (Separation of Concerns):**
    -   La logica del gioco è stata spostata in una classe `GameManager`.
    -   Le operazioni su file (salvataggio/caricamento) sono in funzioni helper dedicate.
    -   La chiamata all'API esterna è isolata in una sua funzione.
2.  **Viste "Snelle" (Thin Views):** Le funzioni di vista (come `chat_view`) ora orchestrano
    le chiamate alla logica di business, invece di contenerla.
3.  **Sicurezza:** Rimosso `@csrf_exempt`. È fondamentale includere `{% csrf_token %}`
    nel template del form per la protezione contro attacchi CSRF.
4.  **Manutenibilità:**
    -   Uso di costanti per le chiavi di sessione e altre stringhe ripetute.
    -   Il `system_prompt` è una costante definita a parte per non ingombrare la vista.
"""

import json
import logging
import os
import random
import re
from datetime import datetime

from openai import OpenAI
from decouple import config
from django.contrib import messages as flash
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

# --- CONFIGURAZIONE E COSTANTI ---

# Caricamento delle configurazioni dall'esterno
API_KEY = config("API_KEY")
API_URL = "https://openrouter.ai/api/v1/"
MODEL = "google/gemini-2.0-flash-001"

# Costanti del gioco
LOG_DIR = "blamPunk/saves"
STARTING_HP = 20
MAX_SAVE_FILES = 10  # Limite massimo di file di salvataggio per utente
INITIAL_STATS = {"Carisma": 2, "Prontezza": 1, "Cervello": 3, "Fegato": 0}

# Costanti per le chiavi di sessione (evita "stringhe magiche")
SESSION_MESSAGES = "blame_messages"
SESSION_HP = "hp"
SESSION_INVENTORY = "inventario"
SESSION_STATS = "stats"
SESSION_LEVEL = "level"
SESSION_OBJECTIVES_COMPLETED = "objectives_completed"
SESSION_CURRENT_OBJECTIVE = "objective"
SESSION_MAX_HP = 'max_hp'
HP_PER_LEVEL = 10

# System prompt per l'AI, separato dalla logica della vista
SYSTEM_PROMPT = (
    "Agisci come un Dungeon Master AI immerso in un mondo ispirato a *Blame!* di Tsutomu Nihei: "
    "strutture infinite, silenzio opprimente, creature biomeccaniche e città labirintiche. "
    "Narrazione frammentata, ruvida, nello stile di Chuck Palahniuk. "
    "Sei la voce che guida il giocatore. Mai spiegazioni fuori dal contesto narrativo. "
    "Non descrivere te stesso come un'AI. Il giocatore è l'unico umano conosciuto. "
    "GESTIONE PUNTI FERITA: Ogni volta che gli HP del giocatore cambiano (danno o guarigione), la tua risposta DEVE includere due informazioni: la causa del cambiamento E lo stato finale. "
    "Usa il formato: '...testo narrativo... Hai perso/guarito N punti ferita. Punti ferita attuali: X."
    "Quando il giocatore raccoglie un oggetto, rispondi usando la sintassi 'Hai raccolto: [nome dell'oggetto]'. Sostituisci [nome dell'oggetto] con il nome dell'oggetto, senza usare articoli o virgolette. "
    "Guida la storia un passo alla volta e, alla fine di ogni scena, chiedi: 'Cosa fai adesso?'."
    "Quando il giocatore tenta un'azione incerta (persuadere, schivare, indagare), richiedi un tiro di abilità (es. 'Fai un tiro di Carisma'). "
    "Il giocatore deve rispondere includendo la parola 'tiro' oppure 'd20' e il nome dell'abilità (es. 'tiro Carisma'). "
    "Il sistema calcolerà automaticamente il risultato del dado. Non chiedere MAI al giocatore di fornire il risultato numerico di un tiro."
    "Quando un obiettivo importante viene completato o uno nuovo viene scoperto, comunicalo usando la stringa speciale: [OBJECTIVE] Il nuovo obiettivo è..."
)

# Configurazione del logger
logger = logging.getLogger(__name__)


# --- LIVELLO DI PERSISTENZA (Storage Layer) ---

def _get_save_path(username, timestamp):
    """Costruisce il percorso completo per un file di salvataggio."""
    filename = f"sessione_{username}_{timestamp}.json"
    return os.path.join(LOG_DIR, filename)

def _manage_save_files_limit(username):
    """Controlla e rimuove i file di salvataggio più vecchi se si supera il limite."""
    user_prefix = f"sessione_{username}_"
    try:
        if not os.path.exists(LOG_DIR):
            return

        # Filtra i file di salvataggio per l'utente specifico
        user_saves = [
            os.path.join(LOG_DIR, f) 
            for f in os.listdir(LOG_DIR) 
            if f.startswith(user_prefix) and f.endswith(".json")
        ]

        # Se il numero di salvataggi supera il limite, rimuovi i più vecchi
        if len(user_saves) >= MAX_SAVE_FILES:
            # Ordina i file per data di modifica (dal più vecchio al più recente)
            user_saves.sort(key=os.path.getmtime)
            
            # Calcola quanti file eliminare
            files_to_delete_count = len(user_saves) - MAX_SAVE_FILES + 1
            files_to_delete = user_saves[:files_to_delete_count]
            
            for f_path in files_to_delete:
                os.remove(f_path)
                logger.info(f"File di salvataggio obsoleto rimosso: {f_path}")

    except OSError as e:
        logger.error(f"Errore durante la gestione dei file di salvataggio per {username}: {e}")

def save_game_to_file(request, game_data):
    """Salva lo stato del gioco su un file JSON, rispettando il limite di salvataggi."""
    username = request.user.username if request.user.is_authenticated else 'anonimo'
    
    # Prima di salvare, gestisci il limite di file
    _manage_save_files_limit(username)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = _get_save_path(username, timestamp)

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(game_data, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        logger.error(f"Errore nel salvataggio automatico su file {file_path}: {e}")
        return False

def load_game_from_file(filename):
    """Carica lo stato del gioco da un file JSON."""
    file_path = os.path.join(LOG_DIR, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Errore nel caricamento del file {filename}: {e}")
        return None


# --- LIVELLO DI LOGICA DI BUSINESS (Game Logic Layer) ---

class GameManager:
    """
    Gestisce lo stato e la logica del gioco per una sessione utente.
    Incapsula HP, inventario, statistiche, progressione e interazioni.
    """
    def __init__(self, session):
        self.session = session
        self.hp = session.get(SESSION_HP)
        self.inventory = session.get(SESSION_INVENTORY, [])
        self.stats = session.get(SESSION_STATS, {})
        self.level = session.get(SESSION_LEVEL, 1)
        self.objectives_completed = session.get(SESSION_OBJECTIVES_COMPLETED, 0)
        self.current_objective = session.get(SESSION_CURRENT_OBJECTIVE, "")
        self.messages = session.get(SESSION_MESSAGES, [])
        self.max_hp = session.get(SESSION_MAX_HP)

    def is_initialized(self):
        """Controlla se la sessione di gioco è già stata inizializzata."""
        # Controllare sia hp che max_hp è più robusto
        return self.hp is not None and self.max_hp is not None

    def initialize_new_game(self):
        """Imposta i valori per una nuova partita."""
        self.inventory = []
        self.stats = INITIAL_STATS.copy()
        self.level = 1
        self.objectives_completed = 0
        self.current_objective = "Scopri dove ti trovi"
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.max_hp = STARTING_HP
        self.hp = self.max_hp
        
        # Aggiunge le informazioni iniziali come primo messaggio
        stato_hp = f"[INFO] Il personaggio ha attualmente {self.hp} / {self.max_hp} punti ferita."
        stato_inventario = f"[INFO] Il personaggio non possiede oggetti."
        self.messages.append({"role": "user", "content": f"{stato_hp} {stato_inventario}"})

    def save_state_to_session(self):
        """Salva lo stato corrente del gioco nella sessione Django."""
        self.session[SESSION_HP] = self.hp
        self.session[SESSION_INVENTORY] = self.inventory
        self.session[SESSION_STATS] = self.stats
        self.session[SESSION_LEVEL] = self.level
        self.session[SESSION_OBJECTIVES_COMPLETED] = self.objectives_completed
        self.session[SESSION_CURRENT_OBJECTIVE] = self.current_objective
        self.session[SESSION_MESSAGES] = self.messages
        self.session[SESSION_MAX_HP] = self.max_hp

    def get_state_for_savefile(self):
        """Restituisce un dizionario con i dati da salvare su file."""
        return {
            "messages": self.messages,
            "hp": self.hp,
            "inventario": self.inventory,
            "objective": self.current_objective,
            "stats": self.stats,
            "level": self.level,
            "objectives_completed": self.objectives_completed,
            "max_hp": self.max_hp,
        }
    
    def heal_damage(self, amount):
        """Aumenta gli HP del giocatore, senza superare il suo max_hp attuale."""
        self.hp = min(self.max_hp, self.hp + amount)
        return f"✨ Hai recuperato {amount} punti ferita! HP attuali: {self.hp}"


    def take_damage(self, amount):
        """Riduce gli HP del giocatore."""
        self.hp = max(0, self.hp - amount)
        return f"🩸 Hai perso {amount} punti ferita! HP attuali: {self.hp}"

    def add_to_inventory(self, item):
        """Aggiunge un oggetto all'inventario se non è già presente."""
        item_lower = item.strip().lower()
        if item_lower not in self.inventory:
            self.inventory.append(item_lower)
            return f"📦 Oggetto aggiunto all'inventario: {item}"
        return None


    def increment_objective_and_check_levelup(self):
        """Incrementa il contatore degli obiettivi e controlla se avviene un level up."""
        self.objectives_completed += 1
        
        objectives_needed = 10 * self.level  # Soglia dinamica
        if self.objectives_completed >= objectives_needed:
            self.level += 1
            self.objectives_completed -= objectives_needed
            
            # Aumenta le statistiche
            for stat_name in self.stats:
                self.stats[stat_name] += 1
            
            old_max_hp = self.max_hp
            self.max_hp += HP_PER_LEVEL # Aumenta il massimo
            self.hp = self.max_hp # Guarigione completa al nuovo massimo
            
            return (
                f"🎉 **LEVEL UP!** 🎉\n"
                f"Hai raggiunto il livello **{self.level}**!\n"
                f"Le tue statistiche sono aumentate! Ora sono: {self.stats}.\n"
                f"I tuoi HP massimi sono ora {self.max_hp} (erano {old_max_hp}) e sei stato guarito completamente!"

            )
        return None

    def process_dice_roll(self, user_input):
        """Gestisce un tiro di dado e lo formatta."""
        match = re.search(r"tiro\s+(\w+)", user_input, re.IGNORECASE)
        skill_name = match.group(1).capitalize() if match else "Generico"
        
        roll = random.randint(1, 20)
        modifier = self.stats.get(skill_name.lower(), 0)
        total = roll + modifier

        roll_result = f"**TIRO D20 ({skill_name}): {roll} + {modifier} = {total}**"
        return roll_result


# --- LIVELLO DI SERVIZIO (Service Layer) ---

def get_ai_response(messages):
    """Invia i messaggi all'API di OpenRouter e restituisce la risposta."""
    try:
        client = OpenAI(
            base_url=API_URL,
            api_key=API_KEY,
        )
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://localhost",  # Optional. Site URL for rankings on openrouter.ai.
                "X-Title": "BlamPunk RPG",  # Optional. Site title for rankings on openrouter.ai.
            },
            model=MODEL,
            messages=messages,
            timeout=30
        )
        return completion.choices[0].message.content
    except Exception as e:  # Catching a more general Exception for now, can refine later
        logger.error(f"Errore nella chiamata API: {e}")
        return None


# --- LIVELLO DI PRESENTAZIONE (View Layer) ---

def chat_view(request):
    """
    Vista principale della chat, ora più snella e funge da orchestratore.
    """
    game = GameManager(request.session)

    if not game.is_initialized():
        game.initialize_new_game()
        game.save_state_to_session()
        return redirect(reverse("blamPunk:chat-dark")) # Ricarica per mostrare il primo messaggio

    if request.method == "POST":
        # Gestione dell'uso di un oggetto
        if "use_item" in request.POST:
            item_to_use = request.POST.get("use_item")
            message = game.use_item(item_to_use)
            if message:
                flash.add_message(request, flash.SUCCESS, message)
        
        # Gestione dell'input dell'utente
        elif "user_input" in request.POST:
            user_input = request.POST.get("user_input", "").strip()
            if user_input:
                # Gestione tiro di dado
                # Gestione tiro di dado
                if "tiro" in user_input.lower():
                    user_input = game.process_dice_roll(user_input)

                game.messages.append({"role": "user", "content": user_input})
                
                # Chiamata all'AI
                reply = get_ai_response(game.messages)
                
                if reply:
                    game.messages.append({"role": "assistant", "content": reply})
                    
                    # Parsing della risposta dell'AI
                    parse_ai_reply(request, reply, game)
                else:
                    flash.add_message(request, flash.ERROR, "Errore nella risposta dell'AI. Riprova più tardi.")

        # Salvataggio dello stato dopo ogni azione POST
        game.save_state_to_session()
        
        # Salvataggio asincrono su file
        save_game_to_file(request, game.get_state_for_savefile())

        # Reindirizza per evitare il reinvio del form con F5
        return redirect(reverse("blamPunk:chat-dark"))

    # Preparazione del contesto per il template (richiesta GET)
    messages_for_template = [msg for msg in game.messages if msg.get("role") != "system"]
    context = {
        'messages_log': messages_for_template,
        'username': request.user.username if request.user.is_authenticated else 'Giocatore',
        'hp': game.hp,
        'inventario': game.inventory,
        'objective': game.current_objective,
        'level': game.level,
        'stats': game.stats,
        'game_over': game.hp <= 0,
    }
    return render(request, "blamPunk/chat_dark.html", context)

def parse_ai_reply(request, reply, game):
    """Esegue il parsing della risposta dell'AI e aggiorna lo stato del gioco."""
    
    # --- NUOVA LOGICA ROBUSTA PER GLI HP ---
    # Cerca prima uno stato assoluto, che è più affidabile.
    hp_status_match = re.search(r"(?:Punti ferita|HP) attuali:\s*(\d+)", reply, re.IGNORECASE)
    
    if hp_status_match:
        # Se l'AI ci dice gli HP finali, sincronizziamo direttamente lo stato.
        new_hp = int(hp_status_match.group(1))
        game.hp = min(new_hp, game.max_hp) # Usiamo min() per sicurezza, non si sa mai
    else:
        # Altrimenti, cerchiamo i cambiamenti relativi (danno o guarigione).
        damage_match = re.search(r"Hai perso\s+(\d+)\s+punti ferita", reply, re.IGNORECASE)
        if damage_match:
            damage = int(damage_match.group(1))
            game.take_damage(damage)
            flash.add_message(request, flash.WARNING, f"Hai perso {damage} HP!")

        heal_match = re.search(r"Hai guarito\s+(\d+)\s+punti ferita", reply, re.IGNORECASE)
        if heal_match:
            amount_healed = int(heal_match.group(1))
            game.heal_damage(amount_healed)
            flash.add_message(request, flash.INFO, f"Hai recuperato {amount_healed} HP!")
            
    # --- FINE NUOVA LOGICA HP ---

    # Parsing oggetti raccolti
    collected_match = re.search(r"Hai raccolto:?\s*(?:un'|un|una|il|lo|la|i|gli|le)?\s*(.*?)\.", reply, re.IGNORECASE)
    if collected_match:
        items_string = collected_match.group(1)
        # Split by '*' and filter out empty strings
        items = [item.strip() for item in items_string.split('*') if item.strip()]
        for item in items:
            message = game.add_to_inventory(item)
            if message:
                flash.add_message(request, flash.INFO, message)

    # Parsing OBIETTIVI
    obj_match = re.search(r"\[OBJECTIVE\]\s*(.*)", reply, re.IGNORECASE)
    if obj_match:
        new_objective = obj_match.group(1).strip()
        game.current_objective = new_objective
        flash.add_message(request, flash.INFO, f"🎯 Nuovo obiettivo: {new_objective}")
        
        levelup_message = game.increment_objective_and_check_levelup()
        if levelup_message:
            flash.add_message(request, flash.SUCCESS, levelup_message)

def reset_session(request):
    """Pulisce la sessione di gioco e reindirizza alla chat."""
    keys_to_clear = [
        SESSION_MESSAGES, SESSION_HP, SESSION_INVENTORY, SESSION_STATS,
        SESSION_LEVEL, SESSION_OBJECTIVES_COMPLETED, SESSION_CURRENT_OBJECTIVE
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    
    flash.add_message(request, flash.INFO, "Nuova partita iniziata.")
    return redirect(reverse("blamPunk:chat-dark"))

def load_game_list(request):
    """Mostra l'elenco dei file di salvataggio per l'utente."""
    user_prefix = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}"
    saved_games = []
    
    if os.path.exists(LOG_DIR):
        files = os.listdir(LOG_DIR)
        for f in files:
            if f.startswith(user_prefix) and f.endswith(".json"):
                saved_games.append(f)
    
    saved_games.sort(reverse=True)
    return render(request, "blamPunk/load_game.html", {"saved_games": saved_games, "app_name": "blamPunk"})

def load_game_session(request, filename):
    """Carica una sessione di gioco da un file."""
    user_prefix = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}"
    if not filename.startswith(user_prefix):
        flash.add_message(request, flash.ERROR, "Accesso non autorizzato a questo salvataggio.")
        return redirect(reverse("blamPunk:chat-dark"))

    session_data = load_game_from_file(filename)
    
    if session_data:
        # Popola la sessione con i dati caricati
        request.session[SESSION_MESSAGES] = session_data.get("messages", [])
        request.session[SESSION_HP] = session_data.get("hp", STARTING_HP)
        request.session[SESSION_INVENTORY] = session_data.get("inventario", [])
        request.session[SESSION_STATS] = session_data.get("stats", INITIAL_STATS)
        request.session[SESSION_LEVEL] = session_data.get("level", 1)
        request.session[SESSION_OBJECTIVES_COMPLETED] = session_data.get("objectives_completed", 0)
        request.session[SESSION_CURRENT_OBJECTIVE] = session_data.get("objective", "")
        
        flash.add_message(request, flash.SUCCESS, f"Partita '{filename}' caricata con successo!")
    else:
        flash.add_message(request, flash.ERROR, "Errore nel caricamento della partita.")

    # Logica di reindirizzamento basata sul parametro 'app'
    app_name = request.GET.get('app', 'blamPunk')
    if app_name == 'bmovie':
        return redirect(reverse("bmovie:chat"))
    else:
        return redirect(reverse("blamPunk:chat-dark"))
