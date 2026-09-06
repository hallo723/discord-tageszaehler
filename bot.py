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
# KONFIGURATION
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
# STANDARD-KONFIGURATION
# ============================================================

DEFAULT_CONFIG = {
    "channel_id": None,

    "running": False,
    "paused": False,

    # Mehrere Uhrzeiten möglich
    # Beispiel:
    # ["12:00", "18:00", "21:00"]
    "times": [
        "12:00"
    ],

    # Nächster Tag
    "day": 1,

    # Wie viel pro Nachricht erhöht wird
    "increment": 1,

    # Bereits ausgeführte Zeitpunkte
    #
    # Beispiel:
    # [
    #     "2026-09-06 12:00",
    #     "2026-09-06 18:00"
    # ]
    "sent_slots": []
}


# ============================================================
# CONFIG LADEN
# ============================================================

def load_config():
    if not CONFIG_FILE.exists():
        print(
            "Keine config.json gefunden."
        )

        print(
            "Standard-Konfiguration wird verwendet."
        )

        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            saved = json.load(file)

        config = DEFAULT_CONFIG.copy()
        config.update(saved)

        # Alte Config-Versionen absichern
        if not isinstance(
            config.get("times"),
            list
        ):
            config["times"] = ["12:00"]

        if not isinstance(
            config.get("sent_slots"),
            list
        ):
            config["sent_slots"] = []

        print(
            "config.json erfolgreich geladen."
        )

        return config

    except Exception as error:
        print(
            f"Fehler beim Laden der config.json: {error}"
        )

        print(
            "Standard-Konfiguration wird verwendet."
        )

        return DEFAULT_CONFIG.copy()


# ============================================================
# CONFIG SPEICHERN
# ============================================================

def save_config():
    try:
        with CONFIG_FILE.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                config,
                file,
                indent=2,
                ensure_ascii=False
            )

        return True

    except Exception as error:
        print(
            f"Fehler beim Speichern der config.json: {error}"
        )

        return False


config = load_config()


# ============================================================
# DISCORD
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
        try:
            synced = await self.tree.sync(
                guild=GUILD
            )

            print(
                f"{len(synced)} Slash-Befehle synchronisiert."
            )

        except Exception as error:
            print(
                f"Fehler beim Synchronisieren: {error}"
            )


bot = TageszaehlerBot()
tree = bot.tree


# ============================================================
# ZEIT-FUNKTIONEN
# ============================================================

def now():
    return datetime.now(TIMEZONE)


def current_time():
    return now().strftime("%H:%M")


def current_datetime():
    return now().strftime(
        "%Y-%m-%d %H:%M"
    )


# ============================================================
# UHRZEITEN
# ============================================================

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
    times = get_times()

    if not times:
        return "Keine"

    return ", ".join(times)


def validate_time(time_string):
    try:
        parts = time_string.strip().split(":")

        if len(parts) != 2:
            return None

        hour = int(parts[0])
        minute = int(parts[1])

        if not 0 <= hour <= 23:
            return None

        if not 0 <= minute <= 59:
            return None

        return f"{hour:02d}:{minute:02d}"

    except (ValueError, TypeError):
        return None


def parse_times(text):
    parts = text.split(",")

    result = []

    for part in parts:
        cleaned = part.strip()

        if not cleaned:
            continue

        valid = validate_time(cleaned)

        if valid is None:
            return None

        if valid not in result:
            result.append(valid)

    if not result:
        return None

    result.sort()

    return result


# ============================================================
# KANAL HOLEN
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

        if channel is not None:
            return channel

        channel = await bot.fetch_channel(
            int(channel_id)
        )

        return channel

    except Exception as error:
        print(
            "Zielkanal konnte nicht geladen werden:"
        )

        print(error)

        return None


# ============================================================
# INTERACTION ANTWORT
# ============================================================

async def answer(
    interaction: discord.Interaction,
    text: str,
    ephemeral: bool = False
):
    try:
        if interaction.response.is_done():

            await interaction.followup.send(
                text,
                ephemeral=ephemeral
            )

        else:

            await interaction.response.send_message(
                text,
                ephemeral=ephemeral
            )

    except Exception as error:
        print(
            f"Fehler bei Interaction-Antwort: {error}"
        )


# ============================================================
# SETUP
# ============================================================

@tree.command(
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

    await answer(
        interaction,

        "✅ **Tageszähler eingerichtet!**\n\n"
        f"📍 Kanal: <#{interaction.channel_id}>\n"
        "📅 Start: **Tag 1**\n"
        "⏰ Zeiten: **12:00 Uhr**\n"
        "➕ Schrittweite: **+1**\n"
        "⏹️ Status: **Gestoppt**\n\n"
        "Benutze `/start`, um ihn zu starten."
    )


# ============================================================
# START
# ============================================================

@tree.command(
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

        await answer(
            interaction,

            "❌ Kein Zielkanal eingerichtet.\n"
            "Benutze zuerst `/setup`.",

            ephemeral=True
        )

        return

    config["running"] = True
    config["paused"] = False

    save_config()

    await answer(
        interaction,

        "▶️ **Tageszähler gestartet!**\n\n"
        f"⏰ Zeiten: **{format_times()} Uhr**\n"
        f"📅 Nächster Tag: **{config['day']}**\n"
        f"📍 Kanal: <#{config['channel_id']}>"
    )


# ============================================================
# STOP
# ============================================================

@tree.command(
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

    await answer(
        interaction,

        "⏹️ **Tageszähler gestoppt.**"
    )


# ============================================================
# PAUSE
# ============================================================

@tree.command(
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

        await answer(
            interaction,

            "❌ Der Tageszähler läuft nicht.",

            ephemeral=True
        )

        return

    config["paused"] = True

    save_config()

    await answer(
        interaction,

        "⏸️ **Tageszähler pausiert.**"
    )


# ============================================================
# RESUME
# ============================================================

@tree.command(
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

        await answer(
            interaction,

            "❌ Der Tageszähler ist gestoppt.\n"
            "Benutze zuerst `/start`.",

            ephemeral=True
        )

        return

    config["paused"] = False

    save_config()

    await answer(
        interaction,

        "▶️ **Tageszähler läuft wieder.**"
    )


# ============================================================
# SETTIME
# ============================================================

@tree.command(
    name="settime",
    description="Setzt eine oder mehrere tägliche Uhrzeiten."
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

        await answer(
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

    save_config()

    await answer(
        interaction,

        "⏰ **Uhrzeiten gespeichert!**\n\n"
        f"📅 Zeiten: **{', '.join(times)} Uhr**\n\n"
        "Der Zähler kann jetzt mehrmals am selben "
        "Tag ausgeführt werden."
    )


# ============================================================
# SETDAY
# ============================================================

@tree.command(
    name="setday",
    description="Setzt den nächsten Tag."
)
@app_commands.describe(
    tag="Zum Beispiel 1 oder 100"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def setday(
    interaction: discord.Interaction,
    tag: int
):

    if tag < 0:

        await answer(
            interaction,

            "❌ Der Tag darf nicht negativ sein.",

            ephemeral=True
        )

        return

    config["day"] = tag

    save_config()

    await answer(
        interaction,

        f"📅 **Nächster Tag: {tag}**"
    )


# ============================================================
# ADD
# ============================================================

@tree.command(
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

        await answer(
            interaction,

            "❌ Die Schrittweite muss mindestens "
            "**1** sein.",

            ephemeral=True
        )

        return

    config["increment"] = schritt

    save_config()

    await answer(
        interaction,

        f"➕ **Schrittweite: +{schritt}**"
    )


# ============================================================
# CHANNEL
# ============================================================

@tree.command(
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

    await answer(
        interaction,

        f"📍 **Zielkanal geändert:** "
        f"<#{interaction.channel_id}>"
    )


# ============================================================
# STATUS
# ============================================================

@tree.command(
    name="status",
    description="Zeigt den Status des Tageszählers."
)
async def status(
    interaction: discord.Interaction
):

    channel_id = config.get(
        "channel_id"
    )

    if channel_id:
        channel_text = f"<#{channel_id}>"
    else:
        channel_text = "Nicht eingerichtet"

    if not config["running"]:
        state = "⏹️ Gestoppt"

    elif config["paused"]:
        state = "⏸️ Pausiert"

    else:
        state = "▶️ Läuft"

    sent_slots = config.get(
        "sent_slots",
        []
    )

    await answer(
        interaction,

        "📊 **TAGESZÄHLER STATUS**\n\n"

        f"Status: **{state}**\n"
        f"Kanal: {channel_text}\n"
        f"Zeiten: **{format_times()} Uhr**\n"
        f"Nächster Tag: **{config['day']}**\n"
        f"Schrittweite: **+{config['increment']}**\n"
        f"Ausgeführte Slots: **{len(sent_slots)}**\n"
        f"Zeitzone: **Europe/Berlin**\n"
        f"Aktuelle Bot-Zeit: **{current_time()} Uhr**"
    )


# ============================================================
# RESET
# ============================================================

@tree.command(
    name="reset",
    description="Setzt den Tageszähler komplett zurück."
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

    await answer(
        interaction,

        "♻️ **Tageszähler zurückgesetzt.**\n\n"
        "Benutze danach `/setup`."
    )


# ============================================================
# TEST
# ============================================================

@tree.command(
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

        await answer(
            interaction,

            "❌ Kein Zielkanal eingerichtet.\n"
            "Benutze zuerst `/setup`.",

            ephemeral=True
        )

        return

    try:

        await target.send(
            "🧪 **Testnachricht erfolgreich!**\n"
            "Der Tageszähler kann in diesen Kanal schreiben."
        )

        await answer(
            interaction,

            f"✅ Testnachricht wurde in "
            f"<#{target.id}> gesendet."
        )

    except discord.Forbidden:

        await answer(
            interaction,

            "❌ Der Bot darf in diesem Kanal "
            "keine Nachrichten senden.",

            ephemeral=True
        )

    except discord.HTTPException as error:

        print(
            f"Discord-Fehler bei Test: {error}"
        )

        await answer(
            interaction,

            "❌ Discord konnte die "
            "Testnachricht nicht senden.",

            ephemeral=True
        )


# ============================================================
# COMMAND-FEHLER
# ============================================================

@tree.error
async def command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    print(
        "=" * 50
    )

    print(
        "SLASH-COMMAND-FEHLER"
    )

    print(
        f"Typ: {type(error).__name__}"
    )

    print(
        f"Fehler: {error}"
    )

    print(
        "=" * 50
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
            "❌ Beim Ausführen dieses Befehls "
            "ist ein Fehler aufgetreten."
        )

    await answer(
        interaction,
        message,
        ephemeral=True
    )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print()
    print(
        "=" * 55
    )

    print(
        f"🤖 {bot.user} ist online!"
    )

    print(
        f"Bot-ID: {bot.user.id}"
    )

    print(
        f"Server-ID: {GUILD_ID}"
    )

    print(
        "Zeitzone: Europe/Berlin"
    )

    print(
        f"Aktuelle Zeit: {current_time()} Uhr"
    )

    print(
        f"Eingestellte Zeiten: {format_times()}"
    )

    print(
        "=" * 55
    )


# ============================================================
# TAGESZÄHLER
# ============================================================

async def daily_counter():

    await bot.wait_until_ready()

    print(
        "📅 Tageszähler-Task gestartet."
    )

    while not bot.is_closed():

        try:

            current = now()

            current_date = current.strftime(
                "%Y-%m-%d"
            )

            current_clock = current.strftime(
                "%H:%M"
            )

            current_slot = (
                f"{current_date} "
                f"{current_clock}"
            )

            # ------------------------------------------------
            # ALTE SLOTS AUFRÄUMEN
            # ------------------------------------------------

            sent_slots = config.get(
                "sent_slots",
                []
            )

            # Nur die letzten 100 Slots behalten
            if len(sent_slots) > 100:

                config["sent_slots"] = (
                    sent_slots[-100:]
                )

                save_config()

            # ------------------------------------------------
            # GRUNDPRÜFUNGEN
            # ------------------------------------------------

            if not config.get("running"):

                await asyncio.sleep(5)
                continue

            if config.get("paused"):

                await asyncio.sleep(5)
                continue

            if not config.get("channel_id"):

                await asyncio.sleep(5)
                continue

            # ------------------------------------------------
            # ALLE EINGESTELLTEN ZEITEN PRÜFEN
            # ------------------------------------------------

            for scheduled_time in get_times():

                if scheduled_time != current_clock:
                    continue

                # Diese Kombination aus Datum + Uhrzeit
                # wurde bereits ausgeführt.
                if current_slot in config.get(
                    "sent_slots",
                    []
                ):
                    continue

                print()
                print(
                    "----------------------------------------"
                )

                print(
                    "📅 TAGESNACHRICHT WIRD GESENDET"
                )

                print(
                    f"Zeit: "
                    f"{current.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                print(
                    f"Geplante Zeit: {scheduled_time}"
                )

                print(
                    f"Aktueller Tag: {config['day']}"
                )

                print(
                    f"Kanal: {config['channel_id']}"
                )

                print(
                    "----------------------------------------"
                )

                target = await get_target_channel()

                if target is None:

                    print(
                        "❌ Zielkanal wurde nicht gefunden."
                    )

                    continue

                try:

                    day = int(
                        config["day"]
                    )

                    # ----------------------------------------
                    # NACHRICHT SENDEN
                    # ----------------------------------------

                    await target.send(
                        f"📅 **Tag {day}**"
                    )

                    # ----------------------------------------
                    # TAG ERHÖHEN
                    # ----------------------------------------

                    config["day"] = (
                        day
                        + int(config["increment"])
                    )

                    # ----------------------------------------
                    # SLOT ALS AUSGEFÜHRT MARKIEREN
                    # ----------------------------------------

                    if current_slot not in config[
                        "sent_slots"
                    ]:

                        config[
                            "sent_slots"
                        ].append(
                            current_slot
                        )

                    save_config()

                    print(
                        f"✅ Tag {day} erfolgreich gesendet."
                    )

                    print(
                        f"➡️ Nächster Tag: "
                        f"{config['day']}"
                    )

                    print(
                        f"➡️ Slot: {current_slot}"
                    )

                except discord.Forbidden:

                    print(
                        "❌ Keine Berechtigung "
                        "zum Schreiben im Zielkanal."
                    )

                except discord.HTTPException as error:

                    print(
                        f"❌ Discord-Fehler: {error}"
                    )

            # ------------------------------------------------
            # ALLE 5 SEKUNDEN PRÜFEN
            # ------------------------------------------------

            await asyncio.sleep(5)

        except asyncio.CancelledError:

            print(
                "📅 Tageszähler-Task beendet."
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

        bot.daily_task = (
            asyncio.create_task(
                daily_counter()
            )
        )

        print(
            "📅 Tageszähler-Task wurde gestartet."
        )


# ============================================================
# BOT STARTEN
# ============================================================

print()
print(
    "🤖 Bot wird gestartet..."
)

print(
    "=" * 40
)

bot.run(TOKEN)
