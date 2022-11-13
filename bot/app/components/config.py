import json
import os

from telegram import User

DEBUG = bool(os.environ.get("DEBUG"))

REPORT_CHANNEL = int(os.environ.get("REPORT_CHANNEL"))
TEST_CHANNEL = int(os.environ.get("TEST_CHANNEL"))
GROUP_CHAT = int(os.environ.get("GROUP_CHAT"))
DEVELOPER_CHAT = int(os.environ.get("DEVELOPER_CHAT"))
TEAM_LEADER_CHAT = int(os.environ.get("TEAM_LEADER_CHAT"))
ADMINS = json.loads(os.environ.get("ADMINS"))

OWNER_ID = int(os.environ.get("OWNER_ID"))
OWNER = User(id=OWNER_ID, first_name="Alexander Cingolani", is_bot=False)


ADMIN_CHAT_COMMANDS = [
    ("lista_presenze", "Invia la lista presenze dell'evento di oggi.")
]
ADMIN_COMMANDS = [
    ("help", "Ricevi Informazioni sull'utilizzo del bot."),
    ("nuova_segnalazione", "Crea una nuova segnalazione."),
    ("segnalazioni", "Giudica le segnalazioni in coda."),
    ("salva_risultati", "Salva i risultati delle ultime gare."),
    ("penalizza", "Applica una penalità per un'infrazione commessa da un pilota."),
]

LEADER_COMMANDS = [
    ("help", "Ricevi Informazioni sull'utilizzo del bot."),
    ("nuova_segnalazione", "Crea una nuova segnalazione."),
]

PRIVATE_CHAT_COMMANDS = [("help", "Ricevi Informazioni sull'utilizzo del bot.")]

REASONS = [
    "{b} tampona {a} in curva facendolo uscire di pista.",
    "{b} non rispetta le bandiere blu nei confronti di {a}.",
    "{b} effettua cambi di traiettoria ripetuti sul rettilineo.",
]

FACTS = [
    "Collisione con vettura no.{a}.",
    "Bandiere blu non rispettate nei confronti della vettura no.{a}.",
    "Benzina esaurita prima del traguardo.",
]


INFRACTIONS = [
    "Finisce il carburante prima del traguardo.",
    "Taglio linea in ingresso ai box.",
    "Taglio linea in uscita dai box.",
]

if DEBUG:
    REPORT_CHANNEL = TEST_CHANNEL
    GROUP_CHAT = DEVELOPER_CHAT
    LATE_REPORT_CHAT = DEVELOPER_CHAT
