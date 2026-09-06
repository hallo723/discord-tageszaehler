import os
import json
from pathlib import Path
from datetime import datetime
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
        "Setze die Variable in Railway."
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
# KONFIGURATION
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
    if not CONFIG_FILE.exists():
        print("Keine config.json vorhanden. Standardwerte werden verwendet.")
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("config.json ist ungültig.")

        for key, value in DEFAULT_CONFIG.items():
            if key not in data:
                data[key] = value

        return data

    except Exception as error:
        print(f"Fehler beim Laden von config.json: {error}")
        return DEFAULT_CONFIG.copy()


config = load_config()


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

    except Exception as error:
        print(f"Fehler beim Speichern von config.json: {error}")


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def now_berlin():
    return datetime.now(TIMEZONE)


def today():
    return now_berlin().strftime("%Y-%m-%d")


async def get_counter_channel():
    channel_id = config.get("channel_id")

    if channel_id is None:
        return None

    # Erst Cache versuchen
    channel = bot.get_channel(channel_id)

    if channel is not None:
        return channel

    # Falls nicht im Cache, direkt von Discord holen
    try:
        return await bot.fetch_channel(channel_id)

    except Exception as error:
        print(f"Zähler-Kanal konnte nicht geladen werden: {error}")
        return None


def get_target_time():
    now = now_berlin()

    return now.replace(
        hour=config["hour"],
        minute=config["minute"],
        second=0,
        microsecond=0
    )


# =========================================================
# SLASH-COMMANDS SAUBER SYNCHRONISIEREN
# =========================================================

async def sync_commands_clean():

    print("========================================")
    print("SLASH-COMMAND-SYNCHRONISIERUNG")
    print("========================================")

    try:

        # Aktuelle lokale Guild-Commands merken
        current_commands = tree.get_commands(guild=GUILD)

        print(
            f"Aktuelle lokale Commands: "
            f"{len(current_commands)}"
        )

        for command in current_commands:
            print(f"  /{command.name}")

        # -------------------------------------------------
        # 1. Lokale Guild-Commands entfernen
        # -------------------------------------------------

        tree.clear_commands(guild=GUILD)

        print("Lokale Guild-Commands entfernt.")

        # -------------------------------------------------
        # 2. Discord ebenfalls leeren
        # -------------------------------------------------

        cleared = await tree.sync(guild=GUILD)

        print(
            f"Discord-Guild-Commands geleert: "
            f"{len(cleared)}"
        )

        # -------------------------------------------------
        # 3. Aktuelle Commands wieder hinzufügen
        # -------------------------------------------------

        for command in current_commands:
            tree.add_command(
                command,
                guild=GUILD,
                override=True
            )

        print("Aktuelle Commands wieder hinzugefügt.")

        # -------------------------------------------------
        # 4. Neue Commands synchronisieren
        # -------------------------------------------------

        synced = await tree.sync(guild=GUILD)

        print(
            f"{len(synced)} Slash-Befehle "
            f"für Server {GUILD_ID} synchronisiert."
        )

        print("Aktuelle Commands:")

        for command in synced:
            print(f"  /{command.name}")

        print("========================================")

    except Exception as error:

        print("FEHLER BEI DER COMMAND-SYNCHRONISIERUNG")
        print(f"Typ: {type(error).__name__}")
        print(f"Fehler: {error}")
        print("========================================")


# =========================================================
# BOT START
# =========================================================

@bot.event
async def setup_hook():

    await sync_commands_clean()


@bot.event
async def on_ready():

    print("----------------------------------------")
    print(f"{bot.user} ist online!")
    print(f"Server-ID: {GUILD_ID}")
    print("----------------------------------------")

    if not counter_loop.is_running():
        counter_loop.start()


# =========================================================
# TÄGLICHER ZÄHLER
# =========================================================

@tasks.loop(seconds=15)
async def counter_loop():

    # Nicht gestartet
    if not config["running"]:
        return

    # Pausiert
    if config["paused"]:
        return

    now = now_berlin()

    today_date = now.strftime("%Y-%m-%d")

    target = get_target_time()

    # Uhrzeit noch nicht erreicht
    if now < target:
        return

    # Heute bereits ausgeführt
    if config["last_run"] == today_date:
        return

    channel = await get_counter_channel()

    if channel is None:
        print(
            "Zähler kann nicht ausgeführt werden: "
            "Kein Kanal festgelegt."
        )
        return

    current_day = config["day"]

    try:

        await channel.send(
            f"📅 **Tag {current_day}**"
        )

        # Nur nach erfolgreichem Senden erhöhen
        config["day"] += config["increment"]
        config["last_run"] = today_date

        save_config()

        print(
            f"Zähler ausgeführt: "
            f"Tag {current_day} | "
            f"{today_date} | "
            f"{now.strftime('%H:%M:%S')}"
        )

    except discord.Forbidden:

        print(
            "❌ Der Bot hat keine Berechtigung, "
            "in den Zähler-Kanal zu schreiben."
        )

    except discord.NotFound:

        print(
            "❌ Der Zähler-Kanal wurde nicht gefunden."
        )

    except Exception as error:

        print(
            f"❌ Fehler beim Senden: "
            f"{type(error).__name__}: {error}"
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

    config["running"] = True
    config["paused"] = False

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

        if hour < 0 or hour > 23:
            raise ValueError

        if minute < 0 or minute > 59:
            raise ValueError

        config["hour"] = hour
        config["minute"] = minute

        # Wichtig:
        # Die Uhrzeitänderung soll gespeichert werden,
        # ohne den Zähler zurückzusetzen.
        save_config()

        await interaction.response.send_message(
            "⏰ **Uhrzeit geändert!**\n"
            f"Neue Zählzeit: **{hour:02d}:{minute:02d}**"
        )

    except ValueError:

        await interaction.response.send_message(
            "❌ **Falsches Format.**\n"
            "Benutze zum Beispiel:\n"
            "`/settime 18:30`"
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

    if channel_obj is not None:
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
    print(f"Typ: {type(error).__name__}")
    print(f"Fehler: {error}")

    original = getattr(error, "original", None)

    if original is not None:
        print(f"Original-Typ: {type(original).__name__}")
        print(f"Original-Fehler: {original}")

    print("----------------------------------------")

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ Dafür brauchst du die Berechtigung "
            "**Server verwalten**."
        )

    else:

        message = (
            "❌ Bei diesem Befehl ist ein Fehler aufgetreten."
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
