

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
MODEL = "anthropic/claude-3-sonnet"

# Classi del personaggio che cambiano a seconda delle azioni di gioco
ARCHETYPES = {
    "Inquisitore": {
        "bonus_stat": "cervello", 
        "desc": "La tua mente non analizza prove, ma le crepe nelle anime altrui. Ogni segreto è una serratura, e tu hai la chiave."
    },
    "Centurione": {
        "bonus_stat": "fegato", 
        "desc": "Dove il sotterfugio fallisce, la tua volontà incrollabile e la tua forza d'animo aprono la via. Sei lo scudo e la spada tra le anime."
    },
    "Spettro": {
        "bonus_stat": "prontezza", 
        "desc": "Ti muovi tra gli echi, una lama invisibile. Quando i potenti cadono, nessuno sente il tuo passo, solo il silenzio che lasci."
    },
    "Collezionista di Echi": {
        "bonus_stat": "cervello", 
        "desc": "Mentre altri combattono per il potere, tu cerchi i frammenti del passato: ricordi perduti e reliquie dimenticate. La spazzatura di un'anima è il tuo tesoro."
    },
    "Emissario": {
        "bonus_stat": "carisma", 
        "desc": "La tua lingua è un'arma più affilata di qualsiasi lama d'anima. Con le parole costruisci imperi, distruggi alleanze e plasmi la volontà degli immortali."
    },
}

SKILL_MAP = {
                # --- PRONTEZZA: Agilità, Furtività e Reazione Rapida ---
                "agilità": "prontezza",
                "schivata": "prontezza",
                "furtività": "prontezza",     # Per muoversi non visti
                "nascondersi": "prontezza",
                "pugnale": "prontezza",       # Per attacchi rapidi e precisi
                "lama": "prontezza",
                "riflessi": "prontezza",

                # --- CERVELLO: Percezione, Conoscenza e Magia ---
                "indagare": "cervello",
                "intuizione": "cervello",
                "percepire": "cervello",       # Per notare dettagli nascosti o aure magiche
                "conoscenza antica": "cervello",
                "sapere": "cervello",
                "decifrare": "cervello",      # Per rune, linguaggi antichi o ricordi criptici
                "magia": "cervello",          # Per incanalare o comprendere la magia
                "intessere": "cervello",
                "intelletto": "cervello",

                # --- CARISMA: Interazione Sociale, Manipolazione e Volontà ---
                "persuadere": "carisma",
                "intimidire": "carisma",
                "ingannare": "carisma",        # Per mentire e raggirare
                "raggirare": "carisma",
                "negoziare": "carisma",       # Per stringere patti e alleanze
                "diplomazia": "carisma",

                # --- FEGATO: Forza Fisica e Resistenza Spirituale ---
                "forza": "fegato",
                "atletica": "fegato",
                "sfondare": "fegato",         # Per abbattere porte o ostacoli
                "resistere": "fegato",
                "volontà": "fegato",          # Per resistere a magie mentali o alla paura
                "sopportazione": "fegato",
                "combattere": "fegato",
            }

# Costanti del gioco
LOG_DIR = "ade/saves"
STARTING_HP = 20
MAX_SAVE_FILES = 10  # Limite massimo di file di salvataggio per utente
INITIAL_STATS = {"carisma": 2, "prontezza": 1, "cervello": 3, "fegato": 1}

# Costanti per le chiavi di sessione (evita "stringhe magiche")
SESSION_MESSAGES = "ade_messages"
SESSION_HP = "hp"
SESSION_INVENTORY = "inventario"
SESSION_STATS = "stats"
SESSION_LEVEL = "level"
SESSION_OBJECTIVES_COMPLETED = "objectives_completed"
SESSION_CURRENT_OBJECTIVE = "objective"
SESSION_MAX_HP = 'max_hp'
HP_PER_LEVEL = 10
SESSION_PLAYER_CLASS = "player_class"

# LISTA DEI TOOL PER INTERAGIRE CON L'AI
GAME_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "take_damage",
            "description": "Applica un danno al giocatore, riducendo i suoi punti ferita (HP).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "La quantità di danno da infliggere."
                    },
                    "reason": {
                        "type": "string",
                        "description": "La causa del danno (es. 'colpito da un costrutto', 'caduta')."
                    }
                },
                "required": ["amount", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "heal_damage",
            "description": "Guarisce il giocatore, aumentando i suoi punti ferita (HP).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "La quantità di HP da recuperare."
                    }
                },
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_inventory",
            "description": "Aggiunge uno o più oggetti all'inventario del giocatore.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Una lista di nomi di oggetti da aggiungere (es. ['cavo', 'scheda madre'])."
                    }
                },
                "required": ["items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_new_objective",
            "description": "Imposta un nuovo obiettivo principale per il giocatore dopo che il precedente è stato completato.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "La descrizione testuale del nuovo obiettivo (es. 'Trova un modo per superare la porta sigillata')."
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_player_class",
            "description": "Cambia la classe del giocatore in base al suo stile di gioco. Da usare solo in momenti narrativi significativi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_class": {
                        "type": "string",
                        "enum": ["Inquisitore", "Centurione", "Spettro", "Collezionista di Echi", "Emissario"],
                        "description": "Il nuovo archetipo del giocatore."
                    }
                },
                "required": ["new_class"]
            }
        }
    }
]

# System prompt per l'AI, separato dalla logica della vista
SYSTEM_PROMPT = (
    "Agisci come un Dungeon Master AI, un narratore sobrio e spietato. L'ambientazione è il Dominio Cinereo, il regno dei morti. Non è un luogo di punizione, ma una metropoli infinita di echi e memorie dove le anime dei defunti continuano le loro eterne esistenze."

    "STILE E TONO: Combina la tensione politica e i dialoghi taglienti di George R.R. Martin con i conflitti epici e la magia viscerale de 'La Ruota del Tempo'. La narrazione deve essere matura, cruda e realistica. Le vittorie sono sudate e spesso hanno un costo amaro."

    "IL MONDO DI GIOCO (IL DOMINIO CINEREO):"
    "1. Le Casate Silenti: Il Dominio è governato da antiche casate di anime potenti (la Casa di Polvere, la Corte dei Sussurri, il Conclave di Ossa) che si contendono il potere in un gioco di alleanze, tradimenti e assassinii. L'intrigo è costante."
    "2. La Memoria è Potere: La vera valuta non è l'oro, ma la Memoria. Le anime più potenti sono quelle che ricordano di più della loro vita passata. Perdere i propri ricordi significa sbiadire nell'oblio, diventando un'eco senza senno. Le Casate combattono per controllare i frammenti di memoria più potenti."
    "3. I Fiumi di Anime e le Tempeste d'Oblio: Questa è la magia potente dello stile 'Ruota del Tempo'. Il Dominio è attraversato da correnti di pura energia animica. Solo pochi, gli 'Intessitori di Echi', possono attingere a questo potere per scatenare magie devastanti, ma a un grande rischio per la loro sanità mentale e i loro ricordi."

    "IL RUOLO DEL GIOCATORE: Il giocatore è una 'Fiamma Vagante', un'anima appena giunta nel Dominio ma che, per una ragione sconosciuta, brucia con una memoria della sua vita insolitamente vivida. Questo lo rende un pezzo pregiato sulla scacchiera delle Casate: una risorsa da controllare o una minaccia da eliminare."
    
    "MECCANICHE DI GIOCO IMPORTANTI:"
    "- USA SEMPRE gli strumenti appropriati quando la situazione lo richiede:"
    "  * take_damage: quando il giocatore subisce ferite, cadute, attacchi"
    "  * heal_damage: quando il giocatore si cura, riposa o riceve assistenza"
    "  * add_to_inventory: quando il giocatore trova, riceve o ottiene oggetti"
    "  * set_new_objective: quando il giocatore completa un obiettivo importante"
    "  * change_player_class: quando il comportamento del giocatore cambia significativamente"
    "- Non limitarti a descrivere le conseguenze: APPLICA le conseguenze usando gli strumenti"
    "- Ogni situazione pericolosa dovrebbe avere conseguenze reali (danno, perdita di oggetti, etc.)"
    "- Ricompensa l'esplorazione e la risoluzione dei problemi con oggetti utili"

    "ANALISI DELLO STILE DI GIOCO: Monitora le azioni del giocatore e usa change_player_class quando appropriato:"
    "- Inquisitore: interroga, collega indizi, scopre segreti"
    "- Centurione: affronta pericoli direttamente, usa la forza"
    "- Spettro: agisce nell'ombra, usa astuzia e sorpresa"
    "- Collezionista di Echi: esplora, raccoglie reliquie e memoria"
    "- Emissario: usa dialogo, persuasione, manipolazione"
    
    "TIRI DI ABILITÀ - REGOLE FONDAMENTALI:"
    "- OGNI azione che non è automatica DEVE richiedere un tiro di abilità"
    "- Quando il giocatore prova a fare qualcosa di incerto, INTERROMPI la narrazione e chiedi: 'Fai un tiro di [abilità]'"
    "- Esempi di situazioni che richiedono tiri:"
    "  * Tentare di aprire una porta bloccata → 'Fai un tiro di forza'"
    "  * Cercare indizi nascosti → 'Fai un tiro di indagare'"
    "  * Convincere un PNG → 'Fai un tiro di persuadere'"
    "  * Schivare un attacco → 'Fai un tiro di agilità'"
    "  * Decifrare simboli antichi → 'Fai un tiro di decifrare'"
    "- Il giocatore risponderà con 'tiro [abilità]' e tu riceverai il risultato"
    "- Solo DOPO aver ricevuto il risultato del tiro, continua la narrazione basandoti sul successo/fallimento"
    "- Soglie di difficoltà: 10 = facile, 13 = medio, 15 = difficile, 18 = molto difficile"

    "REGOLA D'ORO: Ogni tua risposta dovrebbe includere almeno un'azione concreta che influisce sul gioco (danno, cura, oggetti, obiettivi) O una richiesta di tiro di dado per azioni incerte."
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
        stats_from_session = session.get(SESSION_STATS, {})
        
        # "Sanifica" i dati: crea un nuovo dizionario forzando tutte le chiavi ad essere minuscole
        self.stats = {k.lower(): v for k, v in stats_from_session.items()}
        
        self.level = session.get(SESSION_LEVEL, 1)
        self.objectives_completed = session.get(SESSION_OBJECTIVES_COMPLETED, 0)
        self.current_objective = session.get(SESSION_CURRENT_OBJECTIVE, "")
        self.messages = session.get(SESSION_MESSAGES, [])
        self.max_hp = session.get(SESSION_MAX_HP)
        self.player_class = session.get(SESSION_PLAYER_CLASS, "Inquisitore")

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
        self.player_class = "Inquisitore"
        
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
        self.session[SESSION_PLAYER_CLASS] = self.player_class

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
            "player_class": self.player_class,
        }
    
    def change_class(self, new_class_name):
        """Cambia la classe del giocatore e applica i bonus associati."""
        new_class_name = new_class_name.capitalize()
        
        if new_class_name == self.player_class or new_class_name not in ARCHETYPES:
            return None # Nessun cambiamento o classe non valida

        self.player_class = new_class_name
        bonus_stat = ARCHETYPES[new_class_name]["bonus_stat"]
        
        # Applica un bonus permanente alla statistica primaria della nuova classe
        if bonus_stat in self.stats:
            self.stats[bonus_stat] += 1
            
        description = ARCHETYPES[new_class_name]["desc"]
        return (
            f"🌀 **Il tuo approccio è cambiato.** Ora sei un **{new_class_name}**.\n"
            f"{description}\n"
            f"Hai ottenuto un bonus permanente di +1 a **{bonus_stat.capitalize()}**!"
        )
        
    def heal_damage(self, amount):
        """Aumenta gli HP del giocatore, senza superare il suo max_hp attuale."""
        old_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)

        # Calcola quanto si è stati effettivamente curati
        amount_healed = self.hp - old_hp

        # Restituisce dati utili alla vista
        return {
        'amount_healed': amount_healed,
        'new_hp': self.hp,
        'max_hp': self.max_hp  # Utile per costruire il messaggio "X / Y"
    }

    def take_damage(self, amount, reason=""):
        """Riduce gli HP del giocatore."""
        damage_dealt = min(self.hp, amount)
        self.hp -= damage_dealt
        # Restituisce dati utili, un dizionario alla vista
        return {
        'damage_taken': damage_dealt,
        'new_hp': self.hp,
        'reason': reason,
    }


    def add_to_inventory(self, item):
        """Aggiunge un oggetto e restituisce un messaggio di stato."""
        # Normalizza l'oggetto mantenendo la forma originale per la visualizzazione
        item_clean = item.strip()
        item_lower = item_clean.lower()
        
        # Controlla se l'oggetto è già presente (confronto case-insensitive)
        already_present = any(existing.lower() == item_lower for existing in self.inventory)
        
        if not already_present:
            self.inventory.append(item_clean)  # Mantiene la forma originale
            return True  # l'oggetto è stato aggiunto
        return False  # l'oggetto è già presente
    
    
    def set_new_objective(self, description):
        """
        Imposta un nuovo obiettivo e controlla se avviene un level up.
        Restituisce un dizionario con i risultati dell'operazione.
        """
        self.current_objective = description
        
        # Chiama la funzione interna (che è già corretta)
        levelup_message = self.increment_objective_and_check_levelup()
        
        # Restituisce un dizionario con tutte le informazioni necessarie per la vista
        return {
            'new_objective': description,
            'levelup_info': levelup_message  # Questo sarà la stringa del level up o None
        }


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

        # TIRO DEL DADO
    def process_dice_roll(self, user_input):
        """Gestisce un tiro di dado e lo formatta."""
        match = re.search(r"tiro\s+(\w+)", user_input, re.IGNORECASE)
        skill_name_raw = match.group(1).strip() if match else "Generico"
        skill_name_lower = skill_name_raw.lower()

        # Lista delle statistiche di base
        CORE_STATS_LIST = ["carisma", "prontezza", "cervello", "fegato"]

        # Determina la statistica da usare
        if skill_name_lower in CORE_STATS_LIST:
            core_stat_name = skill_name_lower
        else:
            # Consulta la mappa per le abilità
            core_stat_name = SKILL_MAP.get(skill_name_lower, "cervello")

        modifier = self.stats.get(core_stat_name, 0)
        roll = random.randint(1, 20)
        total = roll + modifier

        # Determina il risultato
        if total >= 18:
            result_text = "**SUCCESSO CRITICO!** 🎉"
        elif total >= 15:
            result_text = "**SUCCESSO!** ✅"
        elif total >= 10:
            result_text = "**SUCCESSO PARZIALE** ⚠️"
        else:
            result_text = "**FALLIMENTO** ❌"

        roll_result = (
            f"**TIRO {skill_name_raw.upper()} (usa {core_stat_name.capitalize()}): "
            f"{roll} + {modifier} = {total}** - {result_text}"
        )
        return roll_result


# --- LIVELLO DI PRESENTAZIONE (View Layer) ---

def chat_ade(request):
    """
    Vista principale della chat, ora potenziata con il Tool Calling.
    """
    game = GameManager(request.session)

    if not game.is_initialized():
        game.initialize_new_game()
        game.save_state_to_session()
        return redirect(reverse("ade:chat-ade")) # Ricarica per mostrare il primo messaggio

    if request.method == "POST":
        # Gestione dell'uso di un oggetto
        if "use_item" in request.POST:
            item_to_use = request.POST.get("use_item")
            message = game.use_item(item_to_use)
            if message:
                flash.add_message(request, flash.SUCCESS, message)
        
        # Gestione dell'input dell'utente
        if "user_input" in request.POST:
            user_input = request.POST.get("user_input", "").strip()
            if not user_input:                                 # Questo blocco serve per evitare problemi qualora l'utente inviasse un messaggio vuoto.
                return redirect(reverse("ade:chat-ade")) # Questo controllo trasforma il messaggio vuoto in una stringa vuota "" e ricarica la opagina, interrompendo il codice ed evitando di chiamare l'API inutilmente
                # Gestione tiro di dado
            if "tiro" in user_input.lower():
                user_input = game.process_dice_roll(user_input)

            game.messages.append({"role": "user", "content": user_input})
                
            # --- NUOVO FLUSSO CON TOOL CALLING ---

            # 1. Prepara i messaggi e il contesto
            messages_for_ai = list(game.messages)
            context_message = (
                f"[CONTESTO PARTITA] Il giocatore è di livello {game.level}. "
                f"Ha {game.hp}/{game.max_hp} HP. "
                f"Inventario: {', '.join(game.inventory) or 'vuoto'}. "
                f"Obiettivo attuale: {game.current_objective}. "
                f"Crea una sfida appropriata per il suo livello."
            )
            messages_for_ai.append({"role": "user", "content": context_message})

            # 2. Prima chiamata all'AI per ottenere la risposta o le chiamate agli strumenti
            client = OpenAI(base_url=API_URL, api_key=API_KEY)
            
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages_for_ai,
                    tools=GAME_TOOLS,
                    tool_choice="auto",
                    temperature=0.7  # Aggiunge un po' di creatività
                )
                
                response_message = response.choices[0].message
                
                # CORREZIONE CRITICA: Gestire correttamente il contenuto della risposta
                # Aggiungi SEMPRE il messaggio dell'AI alla cronologia, anche se è vuoto
                message_to_add = {
                    "role": "assistant",
                    "content": response_message.content or "",  # Gestisce il caso None
                }
                
                # Se ci sono tool_calls, aggiungili al messaggio
                if response_message.tool_calls:
                    message_to_add["tool_calls"] = [tc.model_dump() for tc in response_message.tool_calls]
                
                game.messages.append(message_to_add)

                # 3. Gestione tool calls
                if response_message.tool_calls:
                    success = process_tool_calls(response_message.tool_calls, game, request)
                    
                    if success:
                        # 4. Seconda chiamata all'AI per la risposta narrativa
                        final_response = client.chat.completions.create(
                            model=MODEL,
                            messages=game.messages,
                            temperature=0.7
                        )
                        final_reply = final_response.choices[0].message.content
                        
                        if final_reply:  # Solo se c'è contenuto
                            game.messages.append({"role": "assistant", "content": final_reply})
                        else:
                            # Fallback se l'AI non risponde
                            game.messages.append({"role": "assistant", "content": "Cosa fai?"})
                    else:
                        # Errore nella gestione dei tool
                        flash.error(request, "Errore nella gestione delle azioni di gioco.")
                
                else:
                    # Se non ci sono tool_calls ma c'è contenuto, va bene così
                    if not response_message.content:
                        # Caso raro: nessun tool call e nessun contenuto
                        game.messages.append({"role": "assistant", "content": "Cosa fai?"})
                        
            except Exception as e:
                logger.error(f"Errore nella chiamata all'AI: {e}")
                flash.error(request, "Errore di comunicazione con l'AI. Riprova.")
                game.messages.append({"role": "assistant", "content": "Si è verificato un errore. Cosa fai?"})

        # Salvataggio dello stato
        game.save_state_to_session()
        save_game_to_file(request, game.get_state_for_savefile())
        return redirect(reverse("ade:chat-ade"))

    # Preparazione del contesto per il template (GET)
    messages_for_template = [
        msg for msg in game.messages if msg.get("role") in ["user", "assistant"]
    ]
    context = {
        'messages_log': messages_for_template,
        'username': request.user.username if request.user.is_authenticated else 'Giocatore',
        'hp': game.hp,
        'inventario': game.inventory,
        'objective': game.current_objective,
        'level': game.level,
        'stats': game.stats,
        'game_over': game.hp <= 0,
        'max_hp': game.max_hp,
        'player_class': game.player_class,
    }
    return render(request, "ade/chat.html", context)

# Funzione separata per gestire i tool calls
def process_tool_calls(tool_calls, game, request):
    
    """
    Processa tutte le chiamate ai tool e restituisce True se tutto è andato bene.
    """
    available_functions = {
        "take_damage": game.take_damage,
        "heal_damage": game.heal_damage,
        "add_to_inventory": game.add_to_inventory,
        "set_new_objective": game.set_new_objective,
        "change_player_class": game.change_class
    }
    
    try:
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            
            # Parsing sicuro degli argomenti
            try:
                function_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                logger.error(f"Errore nel parsing degli argomenti per {function_name}: {e}")
                continue
            
            function_response = ""
            
            if function_name == "add_to_inventory":
                items_to_add = function_args.get("items", [])
                ai_message_parts = []
                items_added = []
                items_already_present = []
                
                # CORREZIONE: Assicurati che items_to_add sia sempre una lista
                if isinstance(items_to_add, str):
                    # Se è una stringa, potrebbe essere una lista separata da virgole
                    if ',' in items_to_add:
                        items_to_add = [item.strip() for item in items_to_add.split(',')]
                    else:
                        items_to_add = [items_to_add]
                elif not isinstance(items_to_add, list):
                    # Se non è né stringa né lista, prova a convertirla
                    items_to_add = list(items_to_add) if items_to_add else []
                
                for item in items_to_add:
                    # CORREZIONE: Assicurati che item sia una stringa
                    if isinstance(item, str):
                        was_added = game.add_to_inventory(item)
                        if was_added:
                            items_added.append(item)
                            ai_message_parts.append(f"Oggetto '{item}' aggiunto con successo.")
                        else:
                            items_already_present.append(item)
                            ai_message_parts.append(f"Oggetto '{item}' era già presente nell'inventario.")
                    else:
                        # Se l'item non è una stringa, convertilo
                        item_str = str(item)
                        was_added = game.add_to_inventory(item_str)
                        if was_added:
                            items_added.append(item_str)
                            ai_message_parts.append(f"Oggetto '{item_str}' aggiunto con successo.")
                        else:
                            items_already_present.append(item_str)
                            ai_message_parts.append(f"Oggetto '{item_str}' era già presente nell'inventario.")
                
                # Crea notifiche separate per oggetti aggiunti e già presenti
                if items_added:
                    flash.info(request, f"📦 {'Oggetti aggiunti' if len(items_added) > 1 else 'Oggetto aggiunto'} all'inventario: {', '.join(items_added)}")
                
                if items_already_present:
                    flash.warning(request, f"⚠️ {'Oggetti già presenti' if len(items_already_present) > 1 else 'Oggetto già presente'} nell'inventario: {', '.join(items_already_present)}")
                
                function_response = " ".join(ai_message_parts)
                
            elif function_name == "change_player_class":
                new_class = function_args.get("new_class")
                user_message = game.change_class(new_class)
                if user_message:
                    flash.success(request, user_message)
                    function_response = f"Il cambio di classe in '{new_class}' è stato eseguito."
                else:
                    function_response = "Cambio di classe non eseguito (classe non valida o già impostata)."
                    
            elif function_name == "take_damage":
                result = game.take_damage(**function_args)
                user_message = f"🩸 Hai perso {result['damage_taken']} punti ferita"
                if result['reason']:
                    user_message += f" (causa: {result['reason']})"
                user_message += f"! HP attuali: {result['new_hp']}/{game.max_hp}"
                
                flash.warning(request, user_message)
                function_response = f"Danno applicato. HP del giocatore ora sono {result['new_hp']}."
                
            elif function_name == "heal_damage":
                result = game.heal_damage(**function_args)
                flash.info(request, f"✨ Hai recuperato {result['amount_healed']} punti ferita! HP attuali: {result['new_hp']}/{result['max_hp']}")
                function_response = f"Guarigione applicata. HP del giocatore ora sono {result['new_hp']}."
                
            elif function_name == "set_new_objective":
                result = game.set_new_objective(**function_args)
                flash.info(request, f"🎯 Nuovo obiettivo: {result['new_objective']}")
                
                if result['levelup_info']:
                    flash.success(request, result['levelup_info'])
                    function_response = f"Nuovo obiettivo impostato. In più, il giocatore è salito di livello. Ora è al livello {game.level}."
                    info_message_for_ai = f"[INFO DI GIOCO] {result['levelup_info']}"
                    game.messages.append({"role": "user", "content": info_message_for_ai})
                else:
                    function_response = f"Nuovo obiettivo impostato: {result['new_objective']}"
            
            else:
                # Funzione non riconosciuta
                logger.warning(f"Funzione non riconosciuta: {function_name}")
                function_response = f"Funzione {function_name} non implementata."
            
            # Aggiungi il risultato alla cronologia
            if function_response:
                game.messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": str(function_response),
                })
        
        return True
        
    except Exception as e:
        logger.error(f"Errore nella gestione dei tool calls: {e}")
        return False


def reset_session(request):
    """Pulisce la sessione di gioco e reindirizza alla chat."""
    keys_to_clear = [
        SESSION_MESSAGES, SESSION_HP, SESSION_INVENTORY, SESSION_STATS,
        SESSION_LEVEL, SESSION_OBJECTIVES_COMPLETED, SESSION_CURRENT_OBJECTIVE, SESSION_PLAYER_CLASS
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    
    flash.add_message(request, flash.INFO, "Nuova partita iniziata.")
    return redirect(reverse("ade:chat-ade"))

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
    return render(request, "ade/load_game.html", {"saved_games": saved_games, "app_name": "ade"})

def load_game_session(request, filename):
    """Carica una sessione di gioco da un file."""
    user_prefix = f"sessione_{request.user.username if request.user.is_authenticated else 'anonimo'}"
    if not filename.startswith(user_prefix):
        flash.add_message(request, flash.ERROR, "Accesso non autorizzato a questo salvataggio.")
        return redirect(reverse("ade:chat-ade"))

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
        request.session[SESSION_PLAYER_CLASS] = session_data.get("player_class", "")
        
        flash.add_message(request, flash.SUCCESS, f"Partita '{filename}' caricata con successo!")
    else:
        flash.add_message(request, flash.ERROR, "Errore nel caricamento della partita.")

    # Logica di reindirizzamento basata sul parametro 'app'
    app_name = request.GET.get('app', 'ade')
    if app_name == 'bmovie':
        return redirect(reverse("bmovie:chat"))
    else:
        return redirect(reverse("ade:chat-ade"))
    

# CORREZIONE 4: Debugging e logging migliorati
def debug_ai_response(response_message, tool_calls):
    """
    Funzione di debug per capire cosa sta succedendo con l'AI.
    """
    logger.info(f"AI Response Content: {response_message.content}")
    logger.info(f"AI Tool Calls: {len(tool_calls) if tool_calls else 0}")
    
    if tool_calls:
        for i, tool_call in enumerate(tool_calls):
            logger.info(f"Tool Call {i}: {tool_call.function.name} - Args: {tool_call.function.arguments}")
    
    return True
