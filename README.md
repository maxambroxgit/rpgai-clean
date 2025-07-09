# Progetto RPG AI (Django)

Questo è un progetto Django che ospita una collezione di giochi di ruolo testuali (RPG) interattivi, ognuno con un tema e un Dungeon Master AI distinti. La logica di gioco principale è gestita tramite le sessioni di Django e i salvataggi su file JSON.

## Struttura del Progetto

Il progetto è organizzato in diverse applicazioni Django:

-   **`blamPunk`**: Un RPG testuale ambientato in un mondo ispirato a *Blame!* di Tsutomu Nihei. La narrazione è cupa, frammentata e gestita da un'IA. Include funzionalità di gioco come punti ferita (HP), inventario, obiettivi, livelli e statistiche del personaggio (Carisma, Prontezza, Cervello, Fegato). I progressi di gioco vengono salvati in file JSON all'interno della directory `blamPunk/saves`.

-   **`bmovie`**: Un altro RPG testuale, con un'ambientazione comica e surreale ispirata a *Zak McKracken*. Condivide una logica di gioco molto simile a `blamPunk`, ma con un `system_prompt` differente per adattarsi al tono umoristico e al black humor. I salvataggi di gioco per questa app sono gestiti nella directory `bzak/saves`.

-   **`bzak`**: Questa directory sembra essere utilizzata principalmente per i salvataggi di gioco dell'applicazione `bmovie` (`bzak/saves`), piuttosto che essere un'applicazione Django autonoma con modelli e viste proprie.

-   **`home`**: Probabilmente gestisce la pagina di atterraggio principale del sito o altre pagine informative generali.

-   **`users`**: Si occupa della gestione degli utenti, inclusi i processi di autenticazione e registrazione.

-   **`config`**: Contiene le configurazioni principali del progetto Django, come le impostazioni (`settings.py`) e il routing degli URL (`urls.py`).

-   **`static`**: Directory per i file statici del progetto (CSS, JavaScript, immagini).

-   **`templates`**: Contiene i template HTML globali utilizzati in tutto il progetto.

## Funzionalità Principali

Il cuore del progetto è l'interazione con un'intelligenza artificiale (tramite l'API Groq) che funge da Dungeon Master. Questa IA guida la narrazione, risponde agli input del giocatore e influenza lo stato del gioco.

Le funzionalità chiave includono:

-   **Gestione dello Stato del Gioco**: HP, inventario, obiettivi, statistiche del personaggio e livelli sono gestiti tramite le sessioni di Django.
-   **Interazione con l'IA**: Le conversazioni con l'IA guidano la storia e le decisioni del giocatore.
-   **Tiri di Abilità**: Il gioco supporta tiri di dadi (es. `d20`) per le prove di abilità, con modificatori basati sulle statistiche del personaggio.
-   **Parsing della Risposta dell'IA**: Il sistema analizza le risposte dell'IA per rilevare perdite di HP, nuovi obiettivi e oggetti raccolti, aggiornando di conseguenza lo stato del gioco.
-   **Salvataggio e Caricamento**: I progressi di gioco vengono automaticamente salvati in file JSON e possono essere caricati in seguito.

## Dipendenze Notabili

-   **Django**: Framework web Python.
-   **Open Router API**: Utilizzata per l'interazione con il modello AI.
-   **`python-decouple`**: Per la gestione delle variabili d'ambiente (es. `API_KEY`).
-   **`django-registration`**: Per la gestione della registrazione degli utenti.

Questo progetto offre un'interessante implementazione di giochi di ruolo testuali basati su IA, con la possibilità di espandere facilmente con nuovi temi e narrazioni.

## Aggiornamenti Recenti

### 2025-07-03

-   **Miglioramenti SEO e Social Sharing**: Aggiunti meta tag `description` e Open Graph (`og:title`, `og:description`, `og:image`, `og:url`, `og:type`) per ottimizzare la visibilità sui motori di ricerca e l'anteprima sui social media.
-   **Integrazione Logo**: Inserito il logo (`thedungeon-prova-logo.png`) e la thumbnail (`thedungeon-thumbnail.jpg`) nella home page e configurati i relativi percorsi statici.
-   **Aggiornamenti Testuali**: Modificati i testi nella home page per riflettere il nuovo branding (es. da "RPG AI" a "thedungeon", da "I Nostri Giochi" a "Le nostre ambientazioni").
-   **Refactoring URL blamPunk**: Allineato il nome della funzione di vista in `blamPunk/urls.py` (da `chat_V2` a `chat_view`).

### 2025-07-04

-   **Correzione Reindirizzamento Caricamento Partita**: Risolto il problema di reindirizzamento errato del link "Torna al Gioco" nella pagina di caricamento di `blamPunk`, assicurando che punti correttamente all'app `blamPunk`.
-   **Standardizzazione Logica Caricamento Partita**: Uniformata la logica delle viste `load_game_list` e `load_game_session` e dei relativi template per `blamPunk` e `bmovie`, garantendo il corretto passaggio e interpretazione del parametro `app` per i reindirizzamenti.
-   **Correzione Pulsante "Carica Partita"**: Sistemato il link del pulsante "Carica Partita" nella pagina di chat di `blamPunk`, ora indirizza correttamente alla pagina di caricamento di `blamPunk`.
-   **Link Homepage per Loghi**: Aggiunto un link alla homepage a tutte le istanze del logo `thedungeon-prova-logo.png` nei template HTML.
-   **Integrazione Metatag SEO**: Implementati i metatag SEO nei template di chat di `blamPunk` (`chat_dark.html`) e `bmovie` (`chat.html`) tramite un nuovo blocco `extra_head` in `base.html`, permettendo la personalizzazione dei metatag per ciascuna app.

### 2025-07-09

-   **Uniformità API AI**: Le applicazioni `bmovie` e `hackergame` sono state aggiornate per utilizzare l'API di Open Router, allineandosi all'implementazione già presente in `blamPunk`. Questo garantisce una gestione centralizzata e coerente delle interazioni con l'intelligenza artificiale per tutti i giochi.
