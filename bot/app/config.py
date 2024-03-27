"""
This module contains configuration options for the bot, such as commands available
to different groups of users.
"""

import os
from datetime import time
from decimal import Decimal

PARTICIPANT_LIST_OPENING = time(7)
PARTICIPATION_LIST_REMINDER = time(19)
REPORT_WINDOW_OPENING = time(0)
PARTICIPANTS_LIST_CLOSURE = time(hour=21, minute=45)
REPORT_WINDOW_CLOSURE = time(hour=23, minute=59, second=59)

# Driver Permission IDs
MANAGE_RESULTS = 3
MANAGE_PENALTIES = 4

# Team Permission IDs
FILE_REPORT = 3

# Fixed chats
REPORT_CHANNEL = int(os.environ["REPORT_CHANNEL"])
TEST_CHANNEL = int(os.environ["TEST_CHANNEL"])
LATE_REPORT_CHAT = int(os.environ["LATE_REPORT_CHAT"])
GROUP_CHAT = int(os.environ["GROUP_CHAT"])
DEVELOPER_CHAT = int(os.environ["DEVELOPER_CHAT"])
TEAM_LEADER_CHAT = int(os.environ["TEAM_LEADER_CHAT"])

GROUP_COMMANDS = (
    ("my_stats", "Le tue statistiche."),
    ("classifica_piloti", "Classifica piloti della tua categoria."),
    (
        "classifiche_piloti",
        "Classifiche piloti del campionato in corso.",
    ),
    ("classifica_costruttori", "Classifica costruttori del campionato in corso"),
    ("calendario", "Calendario della categoria a cui partecipi."),
    ("prossima_gara", "Info sulla tua prossima gara."),
    ("ultima_gara", "Risultati della tua scorsa gara."),
    ("ultime_gare", "Risultati delle ultime gare."),
    ("aiuto", "Ottieni assistenza sull'uso del bot."),
)

BASE_COMMANDS = (
    ("my_stats", "Le tue statistiche."),
    ("classifica_piloti", "Classifica piloti della tua categoria."),
    (
        "classifiche_piloti",
        "Classifiche piloti del campionato in corso.",
    ),
    ("classifica_costruttori", "Classifica costruttori del campionato in corso"),
    ("calendario", "Calendario della categoria a cui partecipi."),
    ("prossima_gara", "Info sulla tua prossima gara."),
    ("ultima_gara", "Risultati della tua scorsa gara."),
    ("ultime_gare", "Risultati delle ultime gare."),
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


MU = Decimal(25)
K = Decimal(3)
SIGMA = MU / K
