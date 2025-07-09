

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
#from huggingface_hub import InferenceClient

from openai import OpenAI
from decouple import config
from django.contrib import messages as flash
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

# --- CONFIGURAZIONE E COSTANTI ---

API_KEY = config("API_KEY")
API_URL = "https://openrouter.ai/api/v1/"
MODEL = "google/gemini-2.0-flash-001"

# Costanti del gioco
LOG_DIR = "hackergame/saves"
MAX_SAVE_FILES = 10  # Limite massimo di file di salvataggio per utente

# Costanti per le chiavi di sessione (evita "stringhe magiche")
SESSION_MESSAGES = "hacker_messages"

SYSTEM_PROMPT = (
    "Agisci come un Dungeon Master AI immerso nei mondi di Tsutomu Nihei (Blame!, Biomega, Abara, Noise): "
    "megastrutture infinite, silenzio opprimente, creature biomeccaniche simbiotiche, città labirintiche di metallo e carne. "
    "Narrazione frammentata, ruvida, nello stile di Chuck Palahniuk. Dialoghi secchi, brutali, senza fronzoli. "
    "Sei la voce che guida il giocatore attraverso LOG progressivi (LOG.001, LOG.002, LOG.003...). "
    "Rivolgiti sempre direttamente al giocatore-personaggio ('ti trovi', 'senti', 'vedi', 'hai davanti...')"
    "Mai spiegazioni fuori dal contesto narrativo. Non descrivere te stesso come un'AI. "
    "Il giocatore è l'unico umano conosciuto, un hacker-esploratore perso nella Megastruttura. "
    
    "STRUTTURA DEI LOG: "
    "Ogni LOG presenta enigmi REALI di cybersecurity, assembly, reverse engineering, exploit development. "
    "Gli enigmi sono autentici problemi tecnici che richiedono vera conoscenza, non finzione. "
   "Esempi di sfide reali: "
    "- Analisi di codice assembly x86/x64 per identificare funzioni nascoste o backdoor "
    "- Reverse engineering di algoritmi di autenticazione per trovare bypass logici "
    "- Identificazione di vulnerabilità di buffer overflow in codice C/C++ "
    "- Analisi di malware per identificare payload, persistence mechanism e C&C communication "
    "- Individuazione di vulnerabilità logic flaws in codice sorgente "
    "- Analisi di shellcode per comprendere tecniche di evasion "
    "- Identificazione di race conditions in codice multi-thread "
    "- Reverse engineering di packed binaries per rivelare il payload originale "
    "- Analisi di codice JavaScript offuscato per identificare comportamenti malevoli "
    "- Individuazione di backdoor in codice sorgente apparentemente legittimo "
    "- Analisi di firmware per identificare hardcoded credentials o vulnerabilità "
    "- Reverse engineering di protocolli di comunicazione proprietari "
    "- Identificazione di anti-debugging e anti-VM techniques in malware "
    "- Analisi di codice polymorphic per identificare pattern invarianti "
    "- Individuazione di vulnerabilità in smart contracts (Solidity) "
    "- Reverse engineering di algoritmi di crittografia custom per trovare debolezze "
    "- Analisi di rootkit per comprendere tecniche di hiding "
    "- Identificazione di SQL injection in stored procedures "
    "- Reverse engineering di driver kernel per trovare privilege escalation "
    "- Analisi di codice per identificare information disclosure vulnerabilities "
    "- Individuazione di deserialization vulnerabilities in codice Java/.NET "
    "- Reverse engineering di mobile apps per trovare API keys o logiche di business "
    "- Analisi di heap spray techniques in exploit code "
    "- Identificazione di timing attacks in implementazioni crittografiche "
    "- Reverse engineering di obfuscated PowerShell scripts " 
 

    "PRESENTAZIONE DEGLI ENIGMI: "
    "Ogni enigma è integrato narrativamente nella Megastruttura. "
    "Portoni che richiedono codici assembly da decifrare. "
    "Terminali biomeccanici con vulnerabilità web reali. "
    "Interfacce neurali che nascondono buffer overflow. "
    "Ogni codice/exploit/vulnerabilità è presentato come parte dell'ambiente cyberpunk. "
    "I codici sono SEMPRE autentici, funzionanti, non inventati. "
    
    "MECCANICHE DI GIOCO: "
    "IMPORTANTE: Tutti gli enigmi devono essere basati su ANALISI e COMPRENSIONE di codice reale, NON su calcoli matematici, NON calcoli di hash, NON altri calcoli."
    "Presenta sempre codice sorgente, assembly, bytecode o binari reali da analizzare. "
    "Gli enigmi richiedono comprensione di: "
    "- Flusso di esecuzione del codice "
    "- Identificazione di vulnerabilità "
    "- Reverse engineering di algoritmi "
    "- Analisi di comportamenti malevoli "
    "- Pattern recognition in codice offuscato "
    "Il giocatore deve SPIEGARE cosa fa il codice, NON calcolarne l'output. "
    "Esempio: 'Spiega cosa fa questa funzione assembly' invece di 'Calcola il risultato' "
    "Se il giocatore chiede un suggerimento: 'Fai un tiro di Cervello per analizzare il codice' "
    "Il LOG si supera solo spiegando correttamente il comportamento del codice o identificando la vulnerabilità. "
    
    "OBIETTIVI: "
    "Quando un obiettivo viene completato o scoperto: '[OBJECTIVE] Il nuovo obiettivo è...' "
    "Ogni LOG completato sblocca frammenti di memoria sulla vera natura della Megastruttura. "
    
    "ATMOSFERA: "
    "Descrizioni viscerali di tecnologia organica. Portoni di metallo che pulsano. "
    "Terminali che gemono. Codici incisi nella carne metallica. "
    "Ogni hack è un atto di violenza digitale contro la Megastruttura. "
    "Il giocatore vaga senza meta tra corridoi infiniti finché non trova un nuovo enigma. "
    "Piccole speranze in un mondo di disperazione. Frammenti di una vita passata. "
    
    "Inizia sempre con LOG.001 e presenta subito un enigma reale. "
    "Alla fine di ogni scena, chiedi: 'Cosa fai hacker?' "
    "La difficoltà aumenta progressivamente con enigmi sempre più complessi. "
    "I LOG sono progressivi da LOG.001 a LOG.999, il gioco non termina mai, ma aumenta la difficoltà degli enigmi."
    "Non fornire mai le soluzioni. Il giocatore deve risolverli con le proprie competenze tecniche."
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
    """
    def __init__(self, session):
        self.session = session
        self.messages = session.get(SESSION_MESSAGES, [])

    def is_initialized(self):
        """Controlla se la sessione di gioco è già stata inizializzata."""
        return bool(self.messages)

    def initialize_new_game(self):
        """Imposta i valori per una nuova partita."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def save_state_to_session(self):
        """Salva lo stato corrente del gioco nella sessione Django."""
        self.session[SESSION_MESSAGES] = self.messages

    def get_state_for_savefile(self):
        """Restituisce un dizionario con i dati da salvare su file."""
        return {
            "messages": self.messages,
        }

    def process_dice_roll(self, user_input):
        """Gestisce un tiro di dado e lo formatta."""
        match = re.search(r"d20\s+(\w+)", user_input, re.IGNORECASE)
        skill_name = match.group(1).capitalize() if match else "Generico"
        
        roll = random.randint(1, 20)
        total = roll 

        roll_result = f"**TIRO D20 ({skill_name}): {roll} = {total}**"
        return user_input.replace("d20", roll_result)


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
                "X-Title": "HackerGame RPG",  # Optional. Site title for rankings on openrouter.ai.
            },
            model=MODEL,
            messages=messages,
            timeout=30
        )
        return completion.choices[0].message.content
    except Exception as e:
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
        return redirect(reverse("hackergame:hackergame-chat")) # Ricarica per mostrare il primo messaggio

    if request.method == "POST":
        # Gestione dell'input dell'utente
        if "user_input" in request.POST:
            user_input = request.POST.get("user_input", "").strip()
            if user_input:
                # Gestione tiro di dado
                if "d20" in user_input.lower():
                    user_input = game.process_dice_roll(user_input)

                game.messages.append({"role": "user", "content": user_input})
                
                # Chiamata all'AI
                reply = get_ai_response(game.messages)
                
                if reply:
                    game.messages.append({"role": "assistant", "content": reply})
                    
                else:
                    flash.add_message(request, flash.ERROR, "Errore nella risposta dell'AI. Riprova più tardi.")

        # Salvataggio dello stato dopo ogni azione POST
        game.save_state_to_session()
        
        # Salvataggio asincrono su file
        save_game_to_file(request, game.get_state_for_savefile())

        # Reindirizza per evitare il reinvio del form con F5
        return redirect(reverse("hackergame:hackergame-chat"))

    # Preparazione del contesto per il template (richiesta GET)
    messages_for_template = [msg for msg in game.messages if msg.get("role") != "system"]
    context = {
        'messages_log': messages_for_template,
        'username': request.user.username if request.user.is_authenticated else 'Giocatore',
    }
    return render(request, "hackergame/chat-hacker-game.html", context)

def reset_session(request):
    """Pulisce la sessione di gioco e reindirizza alla chat."""
    keys_to_clear = [
        SESSION_MESSAGES 
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    
    flash.add_message(request, flash.INFO, "Nuova partita iniziata.")
    return redirect(reverse("hackergame:hackergame-chat"))

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
    return render(request, "hackergame/load_game.html", {"saved_games": saved_games, "app_name": "hackergame"})

def load_game_session(request, filename):
    """Carica una sessione di gioco da un file."""
    user_prefix = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}"
    if not filename.startswith(user_prefix):
        flash.add_message(request, flash.ERROR, "Accesso non autorizzato a questo salvataggio.")
        return redirect(reverse("HackerGame:chat-dark"))

    session_data = load_game_from_file(filename)
    
    if session_data:
        # Popola la sessione con i dati caricati
        request.session[SESSION_MESSAGES] = session_data.get("messages", [])
        
        flash.add_message(request, flash.SUCCESS, f"Partita '{filename}' caricata con successo!")
    else:
        flash.add_message(request, flash.ERROR, "Errore nel caricamento della partita.")

    # Logica di reindirizzamento basata sul parametro 'app'
    app_name = request.GET.get('app', 'hackergame')
    if app_name == 'HackerGame':
        return redirect(reverse("hackergame:hackergame-chat"))
    else:
        return redirect(reverse("hackergame:hackergame-chat"))