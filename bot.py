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
        "Setze die Umgebungsvariable DISCORD_TOKEN."
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
# DATEI FÜR DIE SPEICHERUNG
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
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)

            for key, value in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = value

            return data

        except Exception:
            print("config.json konnte nicht gelesen werden.")

    return DEFAULT_CONFIG.copy()


config = load_config()


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def current_time():
    return datetime.now(TIMEZONE)


def get_channel():
    channel_id = config.get("channel_id")

    if channel_id is None:
        return None

    return bot.get_channel(channel_id)


# =========================================================
# BOT ONLINE
# =========================================================

@bot.event
async def on_ready():

    print(f"{bot.user} ist online!")

    try:
        synced = await tree.sync(guild=GUILD)
        print(
            f"{len(synced)} Slash-Befehle "
            f"für Server {GUILD_ID} synchronisiert."
        )

    except Exception as error:
        print(f"Fehler beim Synchronisieren: {error}")

    if not counter_loop.is_running():
        counter_loop.start()


# =========================================================
# TÄGLICHER ZÄHLER
# =========================================================

@tasks.loop(seconds=15)
async def counter_loop():

    if not config["running"]:
        return

    if config["paused"]:
        return

    channel = get_channel()

    if channel is None:
        return

    now = current_time()

    today = now.strftime("%Y-%m-%d")

    target_time = now.replace(
        hour=config["hour"],
        minute=config["minute"],
        second=0,
        microsecond=0
    )

    # Die eingestellte Uhrzeit wurde noch nicht erreicht
    if now < target_time:
        return

    # Heute wurde bereits gezählt
    if config["last_run"] == today:
        return

    current_day = config["day"]

    try:

        await channel.send(
            f"📅 **Tag {current_day}**"
        )

        config["day"] += config["increment"]
        config["last_run"] = today

        save_config()

        print(
            f"Zähler ausgeführt: Tag {current_day} "
            f"am {today} um {now.strftime('%H:%M:%S')}"
        )

    except Exception as error:
        print(f"Fehler beim Senden: {error}")


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

    config["channel_id"] = interaction.channel.id
    config["running"] = False
    config["paused"] = False

    # Die eingestellte Uhrzeit bleibt erhalten!

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
# /TIME
# =========================================================

@tree.command(
    name="time",
    description="Ändert die tägliche Zählzeit.",
    guild=GUILD
)
@app_commands.describe(
    new_time="Uhrzeit im Format HH:MM, z.B. 18:30"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def time_command(
    interaction: discord.Interaction,
    new_time: str
):

    try:

        hour, minute = map(int, new_time.split(":"))

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError

        config["hour"] = hour
        config["minute"] = minute

        save_config()

        await interaction.response.send_message(
            f"⏰ **Uhrzeit geändert!**\n"
            f"Neue Zählzeit: **{hour:02d}:{minute:02d}**"
        )

    except ValueError:

        await interaction.response.send_message(
            "❌ Falsches Format.\n"
            "Benutze zum Beispiel `/time 18:30`"
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

    channel_obj = get_channel()

    if channel_obj:
        channel_text = channel_obj.mention

    await interaction.response.send_message(
        "⚙️ **ZÄHLER-STATUS**\n\n"
        f"Status: {status_text}\n"
        f"📅 Aktueller Wert: **{config['day']}**\n"
        f"📈 Erhöhung: **{config['increment']:+d}**\n"
        f"⏰ Uhrzeit: **{config['hour']:02d}:{config['minute']:02d}**\n"
        f"📢 Kanal: {channel_text}\n"
        "🌍 Zeitzone: **Europe/Berlin**"
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
    channel_id = config["channel_id"]

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

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ Dafür brauchst du die Berechtigung "
            "**Server verwalten**."
        )

    else:

        print(f"Slash-Command-Fehler: {error}")

        message = (
            "❌ Bei dem Befehl ist ein Fehler aufgetreten."
        )

    if interaction.response.is_done():

        await interaction.followup.send(message)

    else:

        await interaction.response.send_message(message)


# =========================================================
# BOT STARTEN
# =========================================================

bot.run(TOKEN)
