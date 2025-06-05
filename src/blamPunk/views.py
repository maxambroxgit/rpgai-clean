# blamPunk/views.py

from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import requests
import json, re, os, random
from django.contrib import messages as flash  # nuovo alias per Django flash
from decouple import config




API_KEY = config("API_KEY")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
LOG_FILE = "sessione_blame.json"
STARTING_HP = 20  # ✅ Questa riga è necessaria


system_prompt = (
    "Agisci come un Dungeon Master AI immerso in un mondo ispirato a *Blame!* di Tsutomu Nihei: "
    "strutture infinite, silenzio opprimente, creature biomeccaniche e città labirintiche. "
    "Narrazione frammentata, ruvida, nello stile di Chuck Palahniuk. "
    "Sei la voce che guida il giocatore. Mai spiegazioni fuori dal contesto narrativo. "
    "Non descrivere te stesso come un'AI. Il giocatore è l'unico umano conosciuto. "
    "Guida la storia un passo alla volta e, alla fine di ogni scena, chiedi: 'Cosa fai adesso?'."
)

@csrf_exempt
def chat(request):
    messages = request.session.get("blame_messages", [])
    if not messages:
        messages = [{"role": "system", "content": system_prompt}]

    if request.method == "POST":
        user_input = request.POST.get("user_input", "").strip()
        if user_input:
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
                request.session["blame_messages"] = messages

    return render(request, "blamPunk/chat.html", {"messages_log": messages})




@csrf_exempt
def reset_session(request):
    # Rimuove solo i dati di gioco, non l'intera sessione
    request.session.pop("blame_messages", None)
    request.session.pop("hp", None)
    return redirect(reverse("blamPunk:chat-dark"))  # o la view che desideri

@csrf_exempt
def chat_V2(request):
    messages = request.session.get("blame_messages")
    hp = request.session.get("hp")

    if not messages or not isinstance(hp, int):
        messages = [{"role": "system", "content": system_prompt}]
        hp = STARTING_HP
        stato_hp = f"[INFO] Il personaggio ha attualmente {hp} punti ferita."
        messages.append({"role": "user", "content": stato_hp})

    if request.method == "POST":
        user_input = request.POST.get("user_input", "").strip()

        if user_input.lower() == "quit":
            request.session["blame_messages"] = messages
            request.session["hp"] = hp
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

            # Unico blocco per parsing HP + aggiornamento log + flash
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

            request.session["blame_messages"] = messages
            request.session["hp"] = hp

            if hp <= 0:
                return render(request, "blamPunk/chat.html", {
                    "messages_log": messages,
                    "hp": hp,
                    "game_over": True
                })

    # Stato opzionale da passare alla sidebar
    game_state = {
        "hp": hp,
        "level": 1,
        "inventory": ["Chiave arrugginita", "Torcia rotta", "Radio muta"]
    }

    return render(request, "blamPunk/chat_dark.html", {
        "messages_log": messages,
        "hp": hp,
        "game_state": game_state,
        "username": request.user.username if request.user.is_authenticated else "User"
    })
