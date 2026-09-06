import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from discord import app_commands


# ============================================================
# KONFIGURATION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1533811509678047352
GUILD = discord.Object(id=GUILD_ID)

TIMEZONE = ZoneInfo("Europe/Berlin")

CONFIG_FILE = Path("config.json")


# ============================================================
# STANDARDWERTE
# ============================================================

DEFAULT_CONFIG = {
    "channel_id": None,
    "running": False,
    "paused": False,
    "times": ["12:00"],
    "day": 1,
    "increment": 1,
    "sent_slots": []
}


# ============================================================
# CONFIG LADEN
# ============================================================

def load_config():

    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        config = DEFAULT_CONFIG.copy()
        config.update(data)

        return config

    except Exception as error:

        print("Fehler beim Laden der Config:")
        print(error)

        return DEFAULT_CONFIG.copy()


config = load_config()


# ============================================================
# CONFIG SPEICHERN
# ============================================================

def save_config():

    try:

        with open(CONFIG_FILE, "w", encoding="utf-8") as file:

            json.dump(
                config,
                file,
                indent=4,
                ensure_ascii=False
            )

    except Exception as error:

        print("Fehler beim Speichern:")
        print(error)


# ============================================================
# ZEIT
# ============================================================

def now():

    return datetime.now(TIMEZONE)


def current_time():

    return now().strftime("%H:%M")


def current_date():

    return now().strftime("%Y-%m-%d")


# ============================================================
# UHRZEITEN PRÜFEN
# ============================================================

def parse_times(text):

    times = []

    for value in text.split(","):

        value = value.strip()

        try:

            hour, minute = value.split(":")

            hour = int(hour)
            minute = int(minute)

            if hour < 0 or hour > 23:
                return None

            if minute < 0 or minute > 59:
                return None

            formatted = f"{hour:02d}:{minute:02d}"

            if formatted not in times:
                times.append(formatted)

        except ValueError:

            return None

    if not times:
        return None

    times.sort()

    return times


# ============================================================
# BOT
# ============================================================

class TageszaehlerBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents
        )

        self.counter_task = None

    async def setup_hook(self):

        print()
        print("==========================================")
        print("SLASH COMMANDS")
        print("==========================================")

        try:

            # Alle Commands für diesen Server entfernen
            self.tree.clear_commands(
                guild=GUILD
            )

            # Commands direkt für diesen Server registrieren
            for command in COMMANDS:

                self.tree.add_command(
                    command,
                    guild=GUILD
                )

            synced = await self.tree.sync(
                guild=GUILD
            )

            print(
                f"{len(synced)} Slash-Commands synchronisiert."
            )

            for command in synced:

                print(
                    f"  /{command.name}"
                )

        except Exception as error:

            print("FEHLER BEIM SYNCHRONISIEREN:")
            print(error)

        print("==========================================")
        print()

        self.counter_task = asyncio.create_task(
            daily_counter()
        )


bot = TageszaehlerBot()


# ============================================================
# ZIELKANAL
# ============================================================

async def get_channel():

    channel_id = config.get("channel_id")

    if not channel_id:
        return None

    channel = bot.get_channel(
        int(channel_id)
    )

    if channel:
        return channel

    try:

        return await bot.fetch_channel(
            int(channel_id)
        )

    except Exception:

        return None


# ============================================================
# /SETUP
# ============================================================

@app_commands.command(
    name="setup",
    description="Richtet den Tageszähler ein."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def setup(interaction: discord.Interaction):

    config["channel_id"] = interaction.channel_id
    config["running"] = False
    config["paused"] = False
    config["times"] = ["12:00"]
    config["day"] = 1
    config["increment"] = 1
    config["sent_slots"] = []

    save_config()

    await interaction.response.send_message(
        "✅ **Tageszähler eingerichtet!**\n\n"
        f"📍 Kanal: <#{interaction.channel_id}>\n"
        "📅 Start: **Tag 1**\n"
        "⏰ Zeit: **12:00**\n"
        "➕ Schrittweite: **+1**\n\n"
        "Benutze `/start`."
    )


# ============================================================
# /START
# ============================================================

@app_commands.command(
    name="start",
    description="Startet den Tageszähler."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def start(interaction: discord.Interaction):

    if not config.get("channel_id"):

        await interaction.response.send_message(
            "❌ Erst `/setup` benutzen.",
            ephemeral=True
        )

        return

    config["running"] = True
    config["paused"] = False

    save_config()

    await interaction.response.send_message(
        "▶️ **Tageszähler gestartet!**\n\n"
        f"⏰ Zeiten: **{', '.join(config['times'])}**\n"
        f"📅 Nächster Tag: **{config['day']}**"
    )


# ============================================================
# /STOP
# ============================================================

@app_commands.command(
    name="stop",
    description="Stoppt den Tageszähler."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def stop(interaction: discord.Interaction):

    config["running"] = False
    config["paused"] = False

    save_config()

    await interaction.response.send_message(
        "⏹️ **Tageszähler gestoppt.**"
    )


# ============================================================
# /PAUSE
# ============================================================

@app_commands.command(
    name="pause",
    description="Pausiert den Tageszähler."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def pause(interaction: discord.Interaction):

    if not config["running"]:

        await interaction.response.send_message(
            "❌ Der Tageszähler läuft nicht.",
            ephemeral=True
        )

        return

    config["paused"] = True

    save_config()

    await interaction.response.send_message(
        "⏸️ **Tageszähler pausiert.**"
    )


# ============================================================
# /RESUME
# ============================================================

@app_commands.command(
    name="resume",
    description="Setzt den Tageszähler fort."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def resume(interaction: discord.Interaction):

    if not config["running"]:

        await interaction.response.send_message(
            "❌ Der Tageszähler ist gestoppt.",
            ephemeral=True
        )

        return

    config["paused"] = False

    save_config()

    await interaction.response.send_message(
        "▶️ **Tageszähler läuft wieder.**"
    )


# ============================================================
# /SETTIME
# ============================================================

@app_commands.command(
    name="settime",
    description="Setzt eine oder mehrere Uhrzeiten."
)
@app_commands.describe(
    uhrzeiten="Beispiel: 12:00 oder 12:00,18:00,21:00"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def settime(
    interaction: discord.Interaction,
    uhrzeiten: str
):

    times = parse_times(uhrzeiten)

    if times is None:

        await interaction.response.send_message(
            "❌ Falsche Uhrzeit.\n\n"
            "Beispiele:\n"
            "`/settime 12:00`\n"
            "`/settime 12:00,18:00`\n"
            "`/settime 12:00,18:00,21:00`",
            ephemeral=True
        )

        return

    config["times"] = times

    save_config()

    await interaction.response.send_message(
        "⏰ **Zeiten gespeichert!**\n\n"
        f"**{', '.join(times)}**"
    )


# ============================================================
# /SETDAY
# ============================================================

@app_commands.command(
    name="setday",
    description="Setzt die aktuelle Tagesnummer."
)
@app_commands.describe(
    tag="Zum Beispiel 1"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def setday(
    interaction: discord.Interaction,
    tag: int
):

    if tag < 0:

        await interaction.response.send_message(
            "❌ Der Tag darf nicht negativ sein.",
            ephemeral=True
        )

        return

    config["day"] = tag

    save_config()

    await interaction.response.send_message(
        f"📅 **Tag auf {tag} gesetzt.**"
    )


# ============================================================
# /ADD
# ============================================================

@app_commands.command(
    name="add",
    description="Setzt die Schrittweite."
)
@app_commands.describe(
    schritt="Zum Beispiel 1"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def add(
    interaction: discord.Interaction,
    schritt: int
):

    if schritt < 1:

        await interaction.response.send_message(
            "❌ Die Schrittweite muss mindestens 1 sein.",
            ephemeral=True
        )

        return

    config["increment"] = schritt

    save_config()

    await interaction.response.send_message(
        f"➕ **Schrittweite auf +{schritt} gesetzt.**"
    )


# ============================================================
# /CHANNEL
# ============================================================

@app_commands.command(
    name="channel",
    description="Setzt den aktuellen Kanal."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def channel(interaction: discord.Interaction):

    config["channel_id"] = interaction.channel_id

    save_config()

    await interaction.response.send_message(
        f"📍 Zielkanal: <#{interaction.channel_id}>"
    )


# ============================================================
# /STATUS
# ============================================================

@app_commands.command(
    name="status",
    description="Zeigt den Status."
)
async def status(interaction: discord.Interaction):

    if not config["running"]:
        status_text = "⏹️ Gestoppt"

    elif config["paused"]:
        status_text = "⏸️ Pausiert"

    else:
        status_text = "▶️ Läuft"

    channel_id = config.get("channel_id")

    channel_text = (
        f"<#{channel_id}>"
        if channel_id
        else "Nicht eingerichtet"
    )

    await interaction.response.send_message(

        "📊 **TAGESZÄHLER**\n\n"
        f"Status: **{status_text}**\n"
        f"📍 Kanal: {channel_text}\n"
        f"⏰ Zeiten: **{', '.join(config['times'])}**\n"
        f"📅 Nächster Tag: **{config['day']}**\n"
        f"➕ Schrittweite: **+{config['increment']}**\n"
        f"🕐 Bot-Zeit: **{current_time()}**\n"
        "🌍 Zeitzone: **Europe/Berlin**"
    )


# ============================================================
# /RESET
# ============================================================

@app_commands.command(
    name="reset",
    description="Setzt alles zurück."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def reset(interaction: discord.Interaction):

    config.clear()

    config.update(
        DEFAULT_CONFIG.copy()
    )

    save_config()

    await interaction.response.send_message(
        "♻️ **Tageszähler komplett zurückgesetzt.**\n\n"
        "Benutze `/setup`."
    )


# ============================================================
# /TEST
# ============================================================

@app_commands.command(
    name="test",
    description="Sendet eine Testnachricht."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def test(interaction: discord.Interaction):

    channel = await get_channel()

    if channel is None:

        await interaction.response.send_message(
            "❌ Kein Zielkanal eingerichtet.\n"
            "Benutze `/setup`.",
            ephemeral=True
        )

        return

    try:

        await channel.send(
            "🧪 **Tageszähler-Test erfolgreich!**"
        )

        await interaction.response.send_message(
            "✅ Testnachricht wurde gesendet."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Der Bot darf dort nicht schreiben.",
            ephemeral=True
        )


# ============================================================
# COMMAND-LISTE
# ============================================================

COMMANDS = [
    setup,
    start,
    stop,
    pause,
    resume,
    settime,
    setday,
    add,
    channel,
    status,
    reset,
    test
]


# ============================================================
# TAGESZÄHLER
# ============================================================

async def daily_counter():

    await bot.wait_until_ready()

    print("📅 Tageszähler gestartet.")

    while not bot.is_closed():

        try:

            if not config["running"]:
                await asyncio.sleep(5)
                continue

            if config["paused"]:
                await asyncio.sleep(5)
                continue

            channel = await get_channel()

            if channel is None:
                await asyncio.sleep(5)
                continue

            current = current_time()
            date = current_date()

            for scheduled_time in config["times"]:

                if current != scheduled_time:
                    continue

                slot = f"{date}_{scheduled_time}"

                if slot in config["sent_slots"]:
                    continue

                day = config["day"]
                increment = config["increment"]

                try:

                    await channel.send(
                        f"📅 **Tag {day}**"
                    )

                    config["day"] = day + increment

                    config["sent_slots"].append(slot)

                    # Nur die letzten 100 Slots speichern
                    config["sent_slots"] = (
                        config["sent_slots"][-100:]
                    )

                    save_config()

                    print(
                        f"✅ Tag {day} gesendet "
                        f"({scheduled_time})"
                    )

                except discord.Forbidden:

                    print(
                        "❌ Keine Berechtigung zum Schreiben."
                    )

                except discord.HTTPException as error:

                    print(
                        f"❌ Discord-Fehler: {error}"
                    )

            await asyncio.sleep(5)

        except Exception as error:

            print("❌ Fehler im Tageszähler:")
            print(error)

            await asyncio.sleep(10)


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print()
    print("==========================================")
    print("BOT ONLINE")
    print("==========================================")
    print(f"Bot: {bot.user}")
    print(f"Server-ID: {GUILD_ID}")
    print(f"Zeit: {current_time()}")
    print("Zeitzone: Europe/Berlin")
    print("==========================================")
    print()


# ============================================================
# FEHLER
# ============================================================

@bot.tree.error
async def on_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    print("COMMAND ERROR:")
    print(error)

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ Du brauchst die Berechtigung "
            "**Server verwalten**."
        )

    else:

        message = "❌ Beim Befehl ist ein Fehler aufgetreten."

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception:

        pass


# ============================================================
# START
# ============================================================

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN wurde nicht gefunden!"
    )


print("🤖 Bot wird gestartet...")

bot.run(TOKEN)
