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
-   **Groq API**: Utilizzata per l'interazione con il modello AI.
-   **`python-decouple`**: Per la gestione delle variabili d'ambiente (es. `API_KEY`).
-   **`django-registration`**: Per la gestione della registrazione degli utenti.

Questo progetto offre un'interessante implementazione di giochi di ruolo testuali basati su IA, con la possibilità di espandere facilmente con nuovi temi e narrazioni.