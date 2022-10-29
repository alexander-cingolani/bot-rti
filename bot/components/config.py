from telegram import User

DEBUG = True

TOKEN = "5117477612:AAHhyzwldY_kobkb5ayvXjz0AiwzfMsrL50"

REPORT_CHANNEL = -1001507443179
TEST_CHANNEL = -1001507443179
GROUP_CHAT = -781907821
DEVELOPER_CHAT = -781907821

ADMINS = [633997625, 383460444]
OWNER_ID = 633997625
OWNER = User(id=OWNER_ID, first_name="Alexander Cingolani", is_bot=False)
TEAM_LEADER_CHAT = -781907821


ADMIN_CHAT_COMMANDS = [
    ("lista_presenze", "Invia la lista presenze dell'evento di oggi.")
]
ADMIN_COMMANDS = [
    ("help", "Ricevi Informazioni sull'utilizzo del bot."),
    ("nuova_segnalazione", "Crea una nuova segnalazione."),
    ("segnalazioni", "Giudica le segnalazioni in coda."),
    ("salva_risultati", "Salva i risultati delle ultime gare."),
]
LEADER_COMMANDS = [
    ("help", "Ricevi Informazioni sull'utilizzo del bot."),
    ("nuova_segnalazione", "Crea una nuova segnalazione."),
]
PRIVATE_CHAT_COMMANDS = [("help", "Ricevi Informazioni sull'utilizzo del bot.")]

REASONS = [
    "{b} manca il punto di staccata spingendo {a} fuori pista.",
    "{b} non rispetta le bandiere blu nei confronti di {a}.",
    "{b} effettua cambi di traiettoria ripetuti sul rettilineo.",
    "{b} tampona {a} in curva facendogli perdere il controllo dell'auto",
]

if DEBUG:
    REPORT_CHANNEL = TEST_CHANNEL
    ADMINS = [OWNER_ID, 383460444]
