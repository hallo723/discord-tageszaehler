import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks
from discord import app_commands


# =========================================================
# DISCORD TOKEN
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN wurde nicht gefunden. "
        "Setze die Umgebungsvariable DISCORD_TOKEN in Railway."
    )


# =========================================================
# SERVER
# =========================================================

GUILD_ID = 1533811509678047352
GUILD = discord.Object(id=GUILD_ID)


# =========================================================
# ZEITZONE
# =========================================================

TIMEZONE = ZoneInfo("Europe/Berlin")


# =========================================================
# CONFIG-DATEI
# =========================================================

CONFIG_FILE = Path("config.json")

DEFAULT_CONFIG = {
    "channel_id": None,
    "running": False,
    "paused": False,
    "hour": 12,
    "minute": 0,
    "day": 1,
    "increment": 1,
    "last_run": ""
}


def load_config():
    """
    Lädt die gespeicherte Konfiguration.

    Falls keine Datei existiert oder sie beschädigt ist,
    werden die Standardwerte verwendet.
    """

    if not CONFIG_FILE.exists():
        print("Keine config.json gefunden. Standardwerte werden verwendet.")
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("config.json enthält kein Objekt.")

        # Fehlende Werte ergänzen
        for key, value in DEFAULT_CONFIG.items():
            if key not in data:
                data[key] = value

        return data

    except Exception as error:
        print(f"Fehler beim Laden von config.json: {error}")
        print("Standardwerte werden verwendet.")

        return DEFAULT_CONFIG.copy()


config = load_config()


def save_config():
    """
    Speichert die aktuelle Konfiguration.
    """

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

    except Exception as error:
        print(f"Fehler beim Speichern von config.json: {error}")


# =========================================================
# DISCORD CLIENT
# =========================================================

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def current_time():
    """
    Gibt die aktuelle Zeit in Europe/Berlin zurück.
    """

    return datetime.now(TIMEZONE)


def today_string():
    """
    Gibt das heutige Datum als YYYY-MM-DD zurück.
    """

    return current_time().strftime("%Y-%m-%d")


def configured_time():
    """
    Gibt die konfigurierte Uhrzeit zurück.
    """

    return (
        config["hour"],
        config["minute"]
    )


async def get_counter_channel():
    """
    Holt den konfigurierten Discord-Kanal.

    Zuerst wird der lokale Cache geprüft.
    Falls der Kanal dort nicht vorhanden ist,
    wird versucht, ihn direkt von Discord abzurufen.
    """

    channel_id = config.get("channel_id")

    if channel_id is None:
        return None

    channel = bot.get_channel(channel_id)

    if channel is not None:
        return channel

    try:
        channel = await bot.fetch_channel(channel_id)
        return channel

    except Exception as error:
        print(
            f"Zähler-Kanal {channel_id} konnte nicht geladen werden: "
            f"{error}"
        )

        return None


def get_today_target_time():
    """
    Erstellt den heutigen Zeitpunkt, an dem gezählt werden soll.
    """

    now = current_time()

    return now.replace(
        hour=config["hour"],
        minute=config["minute"],
        second=0,
        microsecond=0
    )


# =========================================================
# BOT SETUP
# =========================================================

async def sync_commands():
    """
    Synchronisiert die Slash-Commands ausschließlich
    mit unserem Server.
    """

    try:
        synced = await tree.sync(guild=GUILD)

        print(
            f"{len(synced)} Slash-Befehle "
            f"für Server {GUILD_ID} synchronisiert."
        )

        for command in synced:
            print(f"  /{command.name}")

    except Exception as error:
        print(f"Fehler beim Synchronisieren: {error}")


@bot.event
async def on_ready():

    print("----------------------------------------")
    print(f"{bot.user} ist online!")
    print(f"Server-ID: {GUILD_ID}")
    print("----------------------------------------")

    if not counter_loop.is_running():
        counter_loop.start()


@bot.event
async def setup_hook():

    await sync_commands()


# =========================================================
# TÄGLICHER ZÄHLER
# =========================================================

@tasks.loop(seconds=15)
async def counter_loop():

    # Zähler läuft nicht
    if not config["running"]:
        return

    # Zähler wurde pausiert
    if config["paused"]:
        return

    now = current_time()

    today = now.strftime("%Y-%m-%d")

    target_time = get_today_target_time()

    # Die eingestellte Uhrzeit wurde heute
    # noch nicht erreicht.
    if now < target_time:
        return

    # Heute wurde bereits gezählt.
    if config["last_run"] == today:
        return

    channel = await get_counter_channel()

    if channel is None:
        print(
            "Zähler konnte nicht ausgeführt werden: "
            "Kein gültiger Kanal festgelegt."
        )
        return

    current_day = config["day"]

    try:

        await channel.send(
            f"📅 **Tag {current_day}**"
        )

        # Erst NACH erfolgreichem Senden speichern.
        config["day"] += config["increment"]
        config["last_run"] = today

        save_config()

        print(
            f"Zähler ausgeführt: "
            f"Tag {current_day} | "
            f"Datum {today} | "
            f"Zeit {now.strftime('%H:%M:%S')}"
        )

    except discord.Forbidden:

        print(
            "FEHLER: Der Bot darf in den Zähler-Kanal "
            "nicht schreiben."
        )

    except discord.NotFound:

        print(
            "FEHLER: Der Zähler-Kanal existiert nicht mehr."
        )

    except Exception as error:

        print(
            f"Fehler beim Senden des Zählers: {error}"
        )


# =========================================================
# /SETUP
# =========================================================

@tree.command(
    name="setup",
    description="Richtet den täglichen Zähler in diesem Kanal ein.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def setup(interaction: discord.Interaction):

    if interaction.channel is None:
        await interaction.response.send_message(
            "❌ Dieser Befehl kann hier nicht verwendet werden."
        )
        return

    config["channel_id"] = interaction.channel.id
    config["running"] = False
    config["paused"] = False
    config["day"] = 1
    config["increment"] = 1
    config["last_run"] = ""

    save_config()

    await interaction.response.send_message(
        "⚙️ **Zähler eingerichtet!**\n\n"
        f"📢 Kanal: {interaction.channel.mention}\n"
        "🔢 Startwert: **1**\n"
        "📈 Erhöhung: **+1**\n"
        f"⏰ Uhrzeit: **{config['hour']:02d}:{config['minute']:02d}**\n"
        "📅 Intervall: **jeden Tag**\n\n"
        "Benutze `/start`, um den Zähler zu starten."
    )


# =========================================================
# /START
# =========================================================

@tree.command(
    name="start",
    description="Startet den täglichen Zähler.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def start(interaction: discord.Interaction):

    if config["channel_id"] is None:

        await interaction.response.send_message(
            "❌ Zuerst `/setup` ausführen."
        )
        return

    now = current_time()
    target = get_today_target_time()
    today = today_string()

    config["running"] = True
    config["paused"] = False

    # Wenn der Bot erst NACH der heutigen Zählzeit
    # gestartet wird, zählt er nicht sofort.
    #
    # Der nächste Lauf ist dann morgen.
    if now >= target and config["last_run"] != today:
        config["last_run"] = today

    save_config()

    await interaction.response.send_message(
        "🟢 **Zähler gestartet!**\n"
        f"⏰ Zählzeitpunkt: "
        f"**{config['hour']:02d}:{config['minute']:02d}**"
    )


# =========================================================
# /STOP
# =========================================================

@tree.command(
    name="stop",
    description="Stoppt den täglichen Zähler.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def stop(interaction: discord.Interaction):

    config["running"] = False
    config["paused"] = False

    save_config()

    await interaction.response.send_message(
        "🔴 **Zähler gestoppt.**"
    )


# =========================================================
# /PAUSE
# =========================================================

@tree.command(
    name="pause",
    description="Pausiert den täglichen Zähler.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def pause(interaction: discord.Interaction):

    if not config["running"]:

        await interaction.response.send_message(
            "ℹ️ Der Zähler läuft momentan nicht."
        )
        return

    config["paused"] = True

    save_config()

    await interaction.response.send_message(
        "⏸️ **Zähler pausiert.**"
    )


# =========================================================
# /RESUME
# =========================================================

@tree.command(
    name="resume",
    description="Setzt den Zähler fort.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def resume(interaction: discord.Interaction):

    config["paused"] = False
    config["running"] = True

    save_config()

    await interaction.response.send_message(
        "▶️ **Zähler fortgesetzt.**"
    )


# =========================================================
# /SETTIME
# =========================================================

@tree.command(
    name="settime",
    description="Ändert die tägliche Zählzeit.",
    guild=GUILD
)
@app_commands.describe(
    new_time="Uhrzeit im Format HH:MM, z.B. 18:30"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def settime(
    interaction: discord.Interaction,
    new_time: str
):

    try:

        parts = new_time.strip().split(":")

        if len(parts) != 2:
            raise ValueError

        hour = int(parts[0])
        minute = int(parts[1])

        if not (0 <= hour <= 23):
            raise ValueError

        if not (0 <= minute <= 59):
            raise ValueError

        config["hour"] = hour
        config["minute"] = minute

        save_config()

        await interaction.response.send_message(
            "⏰ **Uhrzeit geändert!**\n"
            f"Neue Zählzeit: **{hour:02d}:{minute:02d}**"
        )

    except ValueError:

        await interaction.response.send_message(
            "❌ **Falsches Format.**\n"
            "Benutze zum Beispiel: `/settime 18:30`"
        )


# =========================================================
# /SETDAY
# =========================================================

@tree.command(
    name="setday",
    description="Setzt den aktuellen Tag/Zählerwert.",
    guild=GUILD
)
@app_commands.describe(
    number="Der neue Startwert"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def setday(
    interaction: discord.Interaction,
    number: int
):

    if number < 0:

        await interaction.response.send_message(
            "❌ Die Zahl darf nicht negativ sein."
        )
        return

    config["day"] = number

    save_config()

    await interaction.response.send_message(
        f"🔢 Der Zähler steht jetzt auf **Tag {number}**."
    )


# =========================================================
# /ADD
# =========================================================

@tree.command(
    name="add",
    description="Ändert die tägliche Erhöhung.",
    guild=GUILD
)
@app_commands.describe(
    number="Erhöhung, z.B. 1 oder 2"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def add(
    interaction: discord.Interaction,
    number: int
):

    if number == 0:

        await interaction.response.send_message(
            "❌ Die Erhöhung darf nicht 0 sein."
        )
        return

    config["increment"] = number

    save_config()

    await interaction.response.send_message(
        f"📈 Die Erhöhung wurde auf **{number:+d}** gesetzt."
    )


# =========================================================
# /CHANNEL
# =========================================================

@tree.command(
    name="channel",
    description="Legt diesen Kanal als Zähler-Kanal fest.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def channel(interaction: discord.Interaction):

    if interaction.channel is None:

        await interaction.response.send_message(
            "❌ Dieser Befehl kann hier nicht verwendet werden."
        )
        return

    config["channel_id"] = interaction.channel.id

    save_config()

    await interaction.response.send_message(
        f"📢 Dieser Kanal ({interaction.channel.mention}) "
        "ist jetzt der Zähler-Kanal."
    )


# =========================================================
# /STATUS
# =========================================================

@tree.command(
    name="status",
    description="Zeigt den aktuellen Zähler-Status.",
    guild=GUILD
)
async def status(interaction: discord.Interaction):

    if config["running"]:

        if config["paused"]:
            status_text = "⏸️ Pausiert"
        else:
            status_text = "🟢 Aktiv"

    else:

        status_text = "🔴 Gestoppt"

    channel_text = "Nicht festgelegt"

    channel_obj = await get_counter_channel()

    if channel_obj:

        channel_text = channel_obj.mention

    await interaction.response.send_message(
        "⚙️ **ZÄHLER-STATUS**\n\n"
        f"Status: {status_text}\n"
        f"📅 Aktueller Wert: **{config['day']}**\n"
        f"📈 Erhöhung: **{config['increment']:+d}**\n"
        f"⏰ Uhrzeit: **{config['hour']:02d}:{config['minute']:02d}**\n"
        f"📢 Kanal: {channel_text}\n"
        "🌍 Zeitzone: **Europe/Berlin**\n"
        f"📆 Letzter Lauf: "
        f"**{config['last_run'] or 'Noch keiner'}**"
    )


# =========================================================
# /RESET
# =========================================================

@tree.command(
    name="reset",
    description="Setzt den Zähler zurück.",
    guild=GUILD
)
@app_commands.checks.has_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction):

    # Kanal behalten
    channel_id = config.get("channel_id")

    config.clear()
    config.update(DEFAULT_CONFIG.copy())

    config["channel_id"] = channel_id

    save_config()

    await interaction.response.send_message(
        "♻️ **Zähler zurückgesetzt.**\n\n"
        "🔢 Startwert: **1**\n"
        "📈 Erhöhung: **+1**\n"
        "⏰ Uhrzeit: **12:00**"
    )


# =========================================================
# FEHLERBEHANDLUNG
# =========================================================

@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error
):

    print("----------------------------------------")
    print("SLASH-COMMAND-FEHLER")
    print(f"Fehlertyp: {type(error).__name__}")
    print(f"Fehler: {error}")

    original_error = getattr(error, "original", None)

    if original_error is not None:
        print(f"Ursprünglicher Fehler: {type(original_error).__name__}")
        print(f"Details: {original_error}")

    print("----------------------------------------")

    # Keine Berechtigung
    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ Dafür brauchst du die Berechtigung "
            "**Server verwalten**."
        )

    # Command wurde von Discord geschickt,
    # ist aber lokal nicht vorhanden.
    elif isinstance(
        error,
        app_commands.errors.CommandNotFound
    ):

        message = (
            "❌ Dieser Slash-Befehl ist veraltet. "
            "Bitte Discord einmal komplett neu laden "
            "und den Befehl erneut auswählen."
        )

    else:

        message = (
            "❌ Bei dem Befehl ist ein Fehler aufgetreten.\n"
            "Schau bitte in die Railway-Logs."
        )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(message)

        else:

            await interaction.response.send_message(message)

    except Exception as send_error:

        print(
            f"Fehler beim Senden der Fehlermeldung: "
            f"{send_error}"
        )


# =========================================================
# BOT STARTEN
# =========================================================

print("Bot wird gestartet...")

bot.run(TOKEN)
