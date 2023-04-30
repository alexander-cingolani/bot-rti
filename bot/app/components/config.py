"""
This module contains configuration options for the bot, such as commands available
to different groups of users.
"""
import json
import os

from telegram import User

REPORT_CHANNEL = int(os.environ["REPORT_CHANNEL"])
TEST_CHANNEL = int(os.environ["TEST_CHANNEL"])
LATE_REPORT_CHAT = int(os.environ["LATE_REPORT_CHAT"])
GROUP_CHAT = int(os.environ["GROUP_CHAT"])
DEVELOPER_CHAT = int(os.environ["DEVELOPER_CHAT"])
TEAM_LEADER_CHAT = int(os.environ["TEAM_LEADER_CHAT"])
ADMINS = json.loads(os.environ["ADMINS"])
OWNER_ID = int(os.environ["OWNER_ID"])
OWNER = User(id=OWNER_ID, first_name="Alexander Cingolani", is_bot=False)

BASE_COMMANDS = (
    ("my_stats", "Le tue statistiche."),
    ("classifica_piloti", "Classifica piloti della tua categoria."),
    (
        "classifiche_piloti",
        "Classifiche piloti del campionato in corso.",
    ),
    ("classifica_costruttori", "Classifica costruttori del campionato in corso"),
    ("calendario", "Calendario della categoria a cui partecipi.")
    ("prossima_gara", "Info sulla tua prossima gara."),
    ("ultima_gara", "Risultati della tua scorsa gara."),
    ("ultime_gare", "Risultati delle ultime gare."),
    ("info_stats", "Formula e scopo di ciascuna statistica."),
    ("aiuto", "Ottieni assistenza sull'uso del bot."),
    ("registrami", "Registrati al bot."),
)

LEADER_ONLY_COMMANDS = (
    ("segnala", "Crea una nuova segnalazione."),
    (
        "segnalazione_ritardataria",
        "Segnala dopo il periodo consentito.",
    ),
)
LEADER_COMMANDS = BASE_COMMANDS + LEADER_ONLY_COMMANDS

ADMIN_ONLY_COMMANDS = (
    ("segnalazioni", "Giudica le segnalazioni in coda."),
    ("salva_risultati", "Salva i risultati delle ultime gare."),
    ("penalizza", "Applica una penalità per un'infrazione commessa da un pilota."),
)
ADMIN_COMMANDS = LEADER_COMMANDS + ADMIN_ONLY_COMMANDS

REASONS = (
    "{b} tampona {a} in curva facendolo uscire di pista.",
    "{b} non rispetta le bandiere blu nei confronti di {a}.",
    "{b} effettua cambi di traiettoria ripetuti sul rettilineo.",
)

FACTS = (
    "Collisione con vettura no.{a}.",
    "Bandiere blu non rispettate nei confronti della vettura no.{a}.",
)

INFRACTIONS = (
    "Finisce il carburante prima del traguardo.",
    "Taglio linea in ingresso ai box.",
    "Taglio linea in uscita dai box.",
)
