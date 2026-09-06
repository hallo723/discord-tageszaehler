import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands


# ============================================================
# EINSTELLUNGEN
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN fehlt in Railway → Variables."
    )

GUILD_ID = 1533811509678047352
GUILD = discord.Object(id=GUILD_ID)

TIMEZONE = ZoneInfo("Europe/Berlin")
CONFIG_FILE = Path("config.json")


# ============================================================
# STANDARD CONFIG
# ============================================================

DEFAULT_CONFIG = {
    "channel_id": None,
    "running": False,
    "paused": False,

    # Mehrere Zeiten möglich
    # Beispiel:
    # 12:00, 18:00 und 21:00
    "times": [
        "12:00"
    ],

    "day": 1,
    "increment": 1,

    # Bereits gesendete Zeitpunkte
    "sent_slots": []
}


# ============================================================
# CONFIG LADEN
# ============================================================

def load_config():

    if not CONFIG_FILE.exists():

        print("Keine config.json gefunden.")
        print("Standardwerte werden verwendet.")

        return DEFAULT_CONFIG.copy()

    try:

        with CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            saved = json.load(file)

        config_data = DEFAULT_CONFIG.copy()
        config_data.update(saved)

        if not isinstance(
            config_data.get("times"),
            list
        ):
            config_data["times"] = ["12:00"]

        if not isinstance(
            config_data.get("sent_slots"),
            list
        ):
            config_data["sent_slots"] = []

        print("config.json geladen.")

        return config_data

    except Exception as error:

        print(
            f"Fehler beim Laden der config.json: {error}"
        )

        print(
            "Standardwerte werden verwendet."
        )

        return DEFAULT_CONFIG.copy()


# ============================================================
# CONFIG SPEICHERN
# ============================================================

config = load_config()


def save_config():

    try:

        with CONFIG_FILE.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                config,
                file,
                indent=4,
                ensure_ascii=False
            )

        return True

    except Exception as error:

        print(
            f"Fehler beim Speichern: {error}"
        )

        return False


# ============================================================
# DISCORD BOT
# ============================================================

intents = discord.Intents.default()

intents.message_content = True


class TageszaehlerBot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):

        print()
        print("=" * 60)
        print("SLASH COMMANDS WERDEN SYNCHRONISIERT")
        print("=" * 60)

        try:

            synced = await self.tree.sync(
                guild=GUILD
            )

            print(
                f"Server-Commands synchronisiert: {len(synced)}"
            )

            for command in synced:

                print(
                    f"  /{command.name}"
                )

        except Exception as error:

            print(
                "FEHLER BEIM SYNCHRONISIEREN:"
            )

            print(error)

        print("=" * 60)
        print()


bot = TageszaehlerBot()


# ============================================================
# ZEIT
# ============================================================

def get_now():

    return datetime.now(
        TIMEZONE
    )


def get_current_time():

    return get_now().strftime(
        "%H:%M"
    )


def get_current_slot():

    return get_now().strftime(
        "%Y-%m-%d %H:%M"
    )


# ============================================================
# ZEITEN
# ============================================================

def validate_time(value):

    try:

        parts = value.strip().split(":")

        if len(parts) != 2:
            return None

        hour = int(parts[0])
        minute = int(parts[1])

        if hour < 0 or hour > 23:
            return None

        if minute < 0 or minute > 59:
            return None

        return f"{hour:02d}:{minute:02d}"

    except ValueError:

        return None


def parse_times(value):

    result = []

    for part in value.split(","):

        part = part.strip()

        if not part:
            continue

        valid = validate_time(part)

        if valid is None:
            return None

        if valid not in result:

            result.append(valid)

    if not result:

        return None

    result.sort()

    return result


def get_times():

    times = config.get(
        "times",
        ["12:00"]
    )

    if not isinstance(
        times,
        list
    ):

        return ["12:00"]

    return times


def format_times():

    return ", ".join(
        get_times()
    )


# ============================================================
# ZIELKANAL
# ============================================================

async def get_target_channel():

    channel_id = config.get(
        "channel_id"
    )

    if not channel_id:

        return None

    try:

        channel = bot.get_channel(
            int(channel_id)
        )

        if channel:

            return channel

        return await bot.fetch_channel(
            int(channel_id)
        )

    except Exception as error:

        print(
            f"Fehler beim Laden des Kanals: {error}"
        )

        return None


# ============================================================
# INTERACTION ANTWORT
# ============================================================

async def reply(
    interaction,
    message,
    ephemeral=False
):

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=ephemeral
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=ephemeral
            )

    except Exception as error:

        print(
            f"Antwortfehler: {error}"
        )


# ============================================================
# /SETUP
# ============================================================

@bot.tree.command(
    name="setup",
    description="Richtet den Tageszähler ein."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def setup(
    interaction: discord.Interaction
):

    config["channel_id"] = interaction.channel_id

    config["running"] = False
    config["paused"] = False

    config["times"] = [
        "12:00"
    ]

    config["day"] = 1
    config["increment"] = 1

    config["sent_slots"] = []

    save_config()

    await reply(
        interaction,

        "✅ **Tageszähler eingerichtet!**\n\n"
        f"📍 Kanal: <#{interaction.channel_id}>\n"
        "📅 Start: **Tag 1**\n"
        "⏰ Zeit: **12:00 Uhr**\n"
        "➕ Schrittweite: **+1**\n"
        "⏹️ Status: **Gestoppt**\n\n"
        "Benutze `/start`."
    )


# ============================================================
# /START
# ============================================================

@bot.tree.command(
    name="start",
    description="Startet den Tageszähler."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def start(
    interaction: discord.Interaction
):

    if not config.get("channel_id"):

        await reply(
            interaction,

            "❌ Kein Kanal eingerichtet.\n"
            "Benutze zuerst `/setup`.",

            ephemeral=True
        )

        return

    config["running"] = True
    config["paused"] = False

    save_config()

    await reply(
        interaction,

        "▶️ **Tageszähler gestartet!**\n\n"
        f"⏰ Zeiten: **{format_times()}**\n"
        f"📅 Nächster Tag: **{config['day']}**\n"
        f"📍 Kanal: <#{config['channel_id']}>"
    )


# ============================================================
# /STOP
# ============================================================

@bot.tree.command(
    name="stop",
    description="Stoppt den Tageszähler."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def stop(
    interaction: discord.Interaction
):

    config["running"] = False
    config["paused"] = False

    save_config()

    await reply(
        interaction,
        "⏹️ **Tageszähler gestoppt.**"
    )


# ============================================================
# /PAUSE
# ============================================================

@bot.tree.command(
    name="pause",
    description="Pausiert den Tageszähler."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def pause(
    interaction: discord.Interaction
):

    if not config["running"]:

        await reply(
            interaction,
            "❌ Der Tageszähler läuft nicht.",
            ephemeral=True
        )

        return

    config["paused"] = True

    save_config()

    await reply(
        interaction,
        "⏸️ **Tageszähler pausiert.**"
    )


# ============================================================
# /RESUME
# ============================================================

@bot.tree.command(
    name="resume",
    description="Setzt den Tageszähler fort."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def resume(
    interaction: discord.Interaction
):

    if not config["running"]:

        await reply(
            interaction,
            "❌ Der Tageszähler ist gestoppt.",
            ephemeral=True
        )

        return

    config["paused"] = False

    save_config()

    await reply(
        interaction,
        "▶️ **Tageszähler läuft wieder.**"
    )


# ============================================================
# /SETTIME
# ============================================================

@bot.tree.command(
    name="settime",
    description="Setzt eine oder mehrere Uhrzeiten."
)
@app_commands.describe(
    uhrzeiten="Zum Beispiel 12:00,18:00,21:00"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def settime(
    interaction: discord.Interaction,
    uhrzeiten: str
):

    times = parse_times(
        uhrzeiten
    )

    if times is None:

        await reply(
            interaction,

            "❌ Ungültige Uhrzeit.\n\n"
            "Beispiele:\n"
            "`/settime 12:00`\n"
            "`/settime 12:00,18:00`\n"
            "`/settime 12:00,18:00,21:00`",

            ephemeral=True
        )

        return

    config["times"] = times

    # Alte Slots entfernen,
    # damit neue Zeiten sofort verwendet werden.
    config["sent_slots"] = []

    save_config()

    await reply(
        interaction,

        "⏰ **Uhrzeiten gespeichert!**\n\n"
        f"Zeiten: **{', '.join(times)}**\n\n"
        "Der Tageszähler kann jetzt "
        "**mehrmals am selben Tag** zählen."
    )


# ============================================================
# /SETDAY
# ============================================================

@bot.tree.command(
    name="setday",
    description="Setzt den nächsten Tag."
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

        await reply(
            interaction,
            "❌ Der Tag darf nicht negativ sein.",
            ephemeral=True
        )

        return

    config["day"] = tag

    save_config()

    await reply(
        interaction,
        f"📅 **Nächster Tag: {tag}**"
    )


# ============================================================
# /ADD
# ============================================================

@bot.tree.command(
    name="add",
    description="Setzt die Schrittweite."
)
@app_commands.describe(
    schritt="Zum Beispiel 1 oder 2"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def add(
    interaction: discord.Interaction,
    schritt: int
):

    if schritt < 1:

        await reply(
            interaction,

            "❌ Die Schrittweite muss mindestens "
            "**1** sein.",

            ephemeral=True
        )

        return

    config["increment"] = schritt

    save_config()

    await reply(
        interaction,
        f"➕ **Schrittweite: +{schritt}**"
    )


# ============================================================
# /CHANNEL
# ============================================================

@bot.tree.command(
    name="channel",
    description="Setzt diesen Kanal als Zielkanal."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def channel(
    interaction: discord.Interaction
):

    config["channel_id"] = interaction.channel_id

    save_config()

    await reply(
        interaction,

        f"📍 **Zielkanal gesetzt:** "
        f"<#{interaction.channel_id}>"
    )


# ============================================================
# /STATUS
# ============================================================

@bot.tree.command(
    name="status",
    description="Zeigt den Status des Tageszählers."
)
async def status(
    interaction: discord.Interaction
):

    if not config["running"]:

        state = "⏹️ Gestoppt"

    elif config["paused"]:

        state = "⏸️ Pausiert"

    else:

        state = "▶️ Läuft"

    channel_id = config.get(
        "channel_id"
    )

    if channel_id:

        channel_text = f"<#{channel_id}>"

    else:

        channel_text = "Nicht eingerichtet"

    await reply(
        interaction,

        "📊 **TAGESZÄHLER STATUS**\n\n"

        f"Status: **{state}**\n"
        f"Kanal: {channel_text}\n"
        f"Zeiten: **{format_times()}**\n"
        f"Nächster Tag: **{config['day']}**\n"
        f"Schrittweite: **+{config['increment']}**\n"
        f"Zeitzone: **Europe/Berlin**\n"
        f"Bot-Zeit: **{get_current_time()}**"
    )


# ============================================================
# /RESET
# ============================================================

@bot.tree.command(
    name="reset",
    description="Setzt den Tageszähler zurück."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def reset(
    interaction: discord.Interaction
):

    config.clear()

    config.update(
        DEFAULT_CONFIG.copy()
    )

    save_config()

    await reply(
        interaction,

        "♻️ **Tageszähler zurückgesetzt.**\n\n"
        "Benutze danach `/setup`."
    )


# ============================================================
# /TEST
# ============================================================

@bot.tree.command(
    name="test",
    description="Sendet sofort eine Testnachricht."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def test(
    interaction: discord.Interaction
):

    target = await get_target_channel()

    if target is None:

        await reply(
            interaction,

            "❌ Kein Zielkanal eingerichtet.\n"
            "Benutze zuerst `/setup`.",

            ephemeral=True
        )

        return

    try:

        await target.send(
            "🧪 **Testnachricht erfolgreich!**\n"
            "Der Tageszähler kann Nachrichten senden."
        )

        await reply(
            interaction,

            f"✅ Testnachricht in "
            f"<#{target.id}> gesendet."
        )

    except discord.Forbidden:

        await reply(
            interaction,

            "❌ Der Bot hat keine Berechtigung, "
            "in diesem Kanal zu schreiben.",

            ephemeral=True
        )

    except discord.HTTPException as error:

        print(
            f"Discord-Fehler: {error}"
        )

        await reply(
            interaction,

            "❌ Discord konnte die Nachricht "
            "nicht senden.",

            ephemeral=True
        )


# ============================================================
# COMMAND FEHLER
# ============================================================

@bot.tree.error
async def command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    print()
    print(
        "SLASH COMMAND FEHLER"
    )
    print(
        type(error).__name__
    )
    print(
        error
    )

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ Du brauchst die Berechtigung "
            "**Server verwalten**."
        )

    else:

        message = (
            "❌ Beim Ausführen des Befehls "
            "ist ein Fehler aufgetreten."
        )

    await reply(
        interaction,
        message,
        ephemeral=True
    )


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print()
    print("=" * 60)

    print(
        f"🤖 Bot online: {bot.user}"
    )

    print(
        f"🆔 Bot-ID: {bot.user.id}"
    )

    print(
        f"🏠 Server-ID: {GUILD_ID}"
    )

    print(
        f"🕐 Bot-Zeit: {get_current_time()}"
    )

    print(
        f"⏰ Zeiten: {format_times()}"
    )

    print(
        "🌍 Zeitzone: Europe/Berlin"
    )

    print("=" * 60)
    print()


# ============================================================
# TAGESZÄHLER
# ============================================================

async def daily_counter():

    await bot.wait_until_ready()

    print(
        "📅 Tageszähler gestartet."
    )

    while not bot.is_closed():

        try:

            if not config.get("running"):

                await asyncio.sleep(5)
                continue

            if config.get("paused"):

                await asyncio.sleep(5)
                continue

            if not config.get("channel_id"):

                await asyncio.sleep(5)
                continue

            current_time = get_current_time()
            current_slot = get_current_slot()

            sent_slots = config.get(
                "sent_slots",
                []
            )

            # ------------------------------------------------
            # ZEITEN DURCHGEHEN
            # ------------------------------------------------

            for scheduled_time in get_times():

                if scheduled_time != current_time:

                    continue

                # ------------------------------------------------
                # DIESE ZEIT HEUTE SCHON GESENDET?
                # ------------------------------------------------

                if current_slot in sent_slots:

                    continue

                print()
                print(
                    "=" * 50
                )

                print(
                    "📅 TAGESNACHRICHT WIRD GESENDET"
                )

                print(
                    f"Zeit: {current_slot}"
                )

                print(
                    f"Tag: {config['day']}"
                )

                print(
                    f"Kanal: {config['channel_id']}"
                )

                print(
                    "=" * 50
                )

                target = await get_target_channel()

                if target is None:

                    print(
                        "❌ Zielkanal nicht gefunden."
                    )

                    continue

                try:

                    day = int(
                        config["day"]
                    )

                    increment = int(
                        config["increment"]
                    )

                    # ------------------------------------------------
                    # NACHRICHT
                    # ------------------------------------------------

                    await target.send(
                        f"📅 **Tag {day}**"
                    )

                    # ------------------------------------------------
                    # TAG ERHÖHEN
                    # ------------------------------------------------

                    config["day"] = (
                        day + increment
                    )

                    # ------------------------------------------------
                    # SLOT SPEICHERN
                    # ------------------------------------------------

                    config.setdefault(
                        "sent_slots",
                        []
                    )

                    config["sent_slots"].append(
                        current_slot
                    )

                    # ------------------------------------------------
                    # NUR DIE LETZTEN 100 AUFBEWAHREN
                    # ------------------------------------------------

                    config["sent_slots"] = (
                        config["sent_slots"][-100:]
                    )

                    save_config()

                    print(
                        f"✅ Tag {day} gesendet."
                    )

                    print(
                        f"➡️ Nächster Tag: "
                        f"{config['day']}"
                    )

                except discord.Forbidden:

                    print(
                        "❌ Keine Berechtigung "
                        "zum Schreiben."
                    )

                except discord.HTTPException as error:

                    print(
                        f"❌ Discord-Fehler: {error}"
                    )

            await asyncio.sleep(5)

        except asyncio.CancelledError:

            print(
                "📅 Tageszähler beendet."
            )

            break

        except Exception as error:

            print(
                "❌ FEHLER IM TAGESZÄHLER:"
            )

            print(error)

            await asyncio.sleep(10)


# ============================================================
# TASK STARTEN
# ============================================================

@bot.event
async def on_connect():

    if not hasattr(
        bot,
        "daily_task"
    ):

        bot.daily_task = asyncio.create_task(
            daily_counter()
        )

        print(
            "📅 Tageszähler-Task wurde gestartet."
        )


# ============================================================
# BOT STARTEN
# ============================================================

print()
print(
    "🤖 BOT WIRD GESTARTET..."
)
print(
    "=" * 40
)

bot.run(TOKEN)
