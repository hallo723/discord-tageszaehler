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


DEFAULT_CONFIG = {
    "channel_id": None,

    "running": False,
    "paused": False,

    "hour": 12,
    "minute": 0,

    "day": 1,
    "increment": 1,

    # Speichert jetzt Datum + Uhrzeit
    # Beispiel: 2026-09-06 12:00
    "last_run": ""
}


# ============================================================
# CONFIG LADEN
# ============================================================

def load_config():

    if not CONFIG_FILE.exists():

        print(
            "Keine config.json vorhanden. "
            "Standardwerte werden verwendet."
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

        print(
            "config.json erfolgreich geladen."
        )

        return config

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
            f"FEHLER beim Speichern der config.json: {error}"
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

        await synchronize_commands()


bot = TageszaehlerBot()
tree = bot.tree


# ============================================================
# ZEIT
# ============================================================

def now():

    return datetime.now(TIMEZONE)


def current_time():

    return now().strftime("%H:%M")


def current_datetime():

    return now().strftime("%Y-%m-%d %H:%M")


def configured_time():

    return (
        f"{int(config['hour']):02d}:"
        f"{int(config['minute']):02d}"
    )


# ============================================================
# KANAL HOLEN
# ============================================================

async def get_target_channel():

    channel_id = config.get("channel_id")

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
            f"Fehler beim Antworten auf Interaction: {error}"
        )


# ============================================================
# SETUP
# ============================================================

@tree.command(
    name="setup",
    description="Richtet den Tageszähler in diesem Kanal ein."
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

    config["hour"] = 12
    config["minute"] = 0

    config["day"] = 1
    config["increment"] = 1

    config["last_run"] = ""

    save_config()

    await answer(
        interaction,

        "✅ **Tageszähler eingerichtet!**\n\n"

        f"📍 Kanal: <#{interaction.channel_id}>\n"

        "📅 Start: **Tag 1**\n"

        "⏰ Zeit: **12:00 Uhr**\n"

        "➕ Schrittweite: **+1**\n"

        "⏹️ Status: **gestoppt**\n\n"

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

            "❌ Noch kein Zielkanal eingerichtet.\n"
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

        f"⏰ Zeit: **{configured_time()} Uhr**\n"

        f"📅 Nächster Tag: **Tag {config['day']}**\n"

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

            "❌ Der Tageszähler läuft gerade nicht.",

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
    description="Setzt den pausierten Tageszähler fort."
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
    description="Setzt die tägliche Uhrzeit."
)
@app_commands.describe(
    uhrzeit="Format HH:MM, zum Beispiel 18:30"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def settime(
    interaction: discord.Interaction,
    uhrzeit: str
):

    try:

        parts = uhrzeit.strip().split(":")

        if len(parts) != 2:

            raise ValueError

        hour = int(parts[0])
        minute = int(parts[1])

        if not 0 <= hour <= 23:

            raise ValueError

        if not 0 <= minute <= 59:

            raise ValueError

    except ValueError:

        await answer(
            interaction,

            "❌ Ungültige Uhrzeit.\n\n"
            "Beispiel:\n"
            "`/settime 18:30`",

            ephemeral=True
        )

        return

    config["hour"] = hour
    config["minute"] = minute

    save_config()

    await answer(
        interaction,

        f"⏰ **Uhrzeit gespeichert: "
        f"{hour:02d}:{minute:02d} Uhr**\n\n"

        "Die Einstellung bleibt auch nach "
        "einem Neustart erhalten."
    )


# ============================================================
# SETDAY
# ============================================================

@tree.command(
    name="setday",
    description="Setzt den nächsten zu sendenden Tag."
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
    description="Setzt die Schrittweite des Tageszählers."
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

        f"➕ **Schrittweite gespeichert: +{schritt}**"
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
    description="Zeigt alle Einstellungen des Tageszählers."
)
async def status(
    interaction: discord.Interaction
):

    channel_id = config.get("channel_id")

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

    await answer(
        interaction,

        "📊 **TAGESZÄHLER STATUS**\n\n"

        f"Status: **{state}**\n"

        f"Kanal: {channel_text}\n"

        f"Uhrzeit: **{configured_time()} Uhr**\n"

        f"Nächster Tag: **{config['day']}**\n"

        f"Schrittweite: **+{config['increment']}**\n"

        f"Letzte Nachricht: "
        f"**{config['last_run'] or 'Noch keine'}**\n"

        "Zeitzone: **Europe/Berlin**\n"

        f"Aktuelle Bot-Zeit: **{current_time()} Uhr**"
    )


# ============================================================
# RESET
# ============================================================

@tree.command(
    name="reset",
    description="Setzt alle Einstellungen zurück."
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

        "♻️ **Alle Einstellungen wurden "
        "zurückgesetzt.**\n\n"

        "Benutze danach `/setup`."
    )


# ============================================================
# TEST
# ============================================================

@tree.command(
    name="test",
    description="Sendet sofort eine Testnachricht in den Zielkanal."
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
            "Der Bot kann Nachrichten in diesen Kanal senden."
        )

        await answer(
            interaction,

            f"✅ Testnachricht wurde in "
            f"<#{target.id}> gesendet."
        )

    except discord.Forbidden:

        await answer(
            interaction,

            "❌ Der Bot hat keine Berechtigung, "
            "in diesem Kanal zu schreiben.",

            ephemeral=True
        )

    except discord.HTTPException as error:

        print(
            f"Testnachricht Discord-Fehler: {error}"
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

    print("=" * 50)
    print("SLASH-COMMAND-FEHLER")
    print(
        f"Typ: {type(error).__name__}"
    )
    print(
        f"Fehler: {error}"
    )
    print("=" * 50)

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ Du brauchst die Berechtigung "
            "**Server verwalten**."
        )

    elif isinstance(
        error,
        app_commands.errors.CommandNotFound
    ):

        message = (
            "⚠️ Discord verwendet noch eine alte "
            "Command-Registrierung.\n"
            "Bitte Discord komplett neu laden."
        )

    else:

        message = (
            "❌ Beim Ausführen dieses Befehls ist "
            "ein Fehler aufgetreten."
        )

    await answer(
        interaction,
        message,
        ephemeral=True
    )


# ============================================================
# COMMAND-SYNCHRONISIERUNG
# ============================================================

async def synchronize_commands():

    print()
    print("=" * 55)
    print("SLASH-COMMAND-SYNCHRONISIERUNG")
    print("=" * 55)

    local_commands = list(
        tree.get_commands()
    )

    print(
        f"Aktuelle lokale Commands: "
        f"{len(local_commands)}"
    )

    for command in local_commands:

        print(
            f"  /{command.name}"
        )

    # --------------------------------------------------------
    # APPLICATION ID
    # --------------------------------------------------------

    try:

        app_info = await bot.application_info()

        print()
        print(
            f"BOT USER: {app_info.name}"
        )

        print(
            f"BOT USER ID: {app_info.id}"
        )

        print(
            f"APPLICATION ID: {app_info.id}"
        )

    except Exception as error:

        print(
            "Application-Info konnte nicht "
            f"geladen werden: {error}"
        )

    # --------------------------------------------------------
    # ALTE GLOBALE COMMANDS LÖSCHEN
    # --------------------------------------------------------

    try:

        tree.clear_commands(
            guild=None
        )

        await tree.sync()

        print(
            "Alte globale Commands dieses "
            "Bots wurden entfernt."
        )

    except Exception as error:

        print(
            "Fehler beim Entfernen globaler "
            f"Commands: {error}"
        )

    # --------------------------------------------------------
    # LOKALE COMMANDS WIEDERHERSTELLEN
    # --------------------------------------------------------

    for command in local_commands:

        tree.add_command(
            command,
            override=True
        )

    # --------------------------------------------------------
    # ALTE GUILD COMMANDS LÖSCHEN
    # --------------------------------------------------------

    try:

        tree.clear_commands(
            guild=GUILD
        )

        await tree.sync(
            guild=GUILD
        )

        print(
            f"Alte Guild-Commands für "
            f"{GUILD_ID} wurden entfernt."
        )

    except Exception as error:

        print(
            "Fehler beim Entfernen der "
            f"Guild-Commands: {error}"
        )

    # --------------------------------------------------------
    # AKTUELLE COMMANDS AUF SERVER KOPIEREN
    # --------------------------------------------------------

    tree.copy_global_to(
        guild=GUILD
    )

    synced = await tree.sync(
        guild=GUILD
    )

    print()
    print(
        f"{len(synced)} Slash-Befehle "
        f"für Server {GUILD_ID} synchronisiert:"
    )

    for command in synced:

        print(
            f"  /{command.name}"
        )

    print(
        "=" * 55
    )

    print()


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print("----------------------------------------")

    print(
        f"{bot.user} ist online!"
    )

    print(
        f"Bot-ID: {bot.user.id}"
    )

    print(
        f"Application-ID: {bot.application_id}"
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

    print("----------------------------------------")


# ============================================================
# TAGESZÄHLER
# ============================================================

async def daily_counter():

    await bot.wait_until_ready()

    print(
        "Tageszähler-Task gestartet."
    )

    while not bot.is_closed():

        try:

            current = now()

            # ------------------------------------------------
            # AKTUELLE MINUTE
            # ------------------------------------------------

            current_key = current.strftime(
                "%Y-%m-%d %H:%M"
            )

            # ------------------------------------------------
            # AKTUELLE UHRZEIT ALS MINUTEN
            # ------------------------------------------------

            current_minutes = (
                current.hour * 60
                + current.minute
            )

            # ------------------------------------------------
            # EINGESTELLTE UHRZEIT
            # ------------------------------------------------

            target_minutes = (
                int(config["hour"]) * 60
                + int(config["minute"])
            )

            # ------------------------------------------------
            # PRÜFEN
            # ------------------------------------------------

            should_send = (

                config["running"]

                and not config["paused"]

                and config.get("channel_id")

                # Wichtig:
                # Nicht dieselbe Minute zweimal senden.
                and config.get("last_run")
                != current_key

                # Sobald die eingestellte Uhrzeit
                # erreicht wurde, darf gesendet werden.
                and current_minutes
                >= target_minutes
            )

            if should_send:

                print()
                print("----------------------------------------")
                print(
                    "TAGESNACHRICHT WIRD GESENDET"
                )

                print(
                    f"Zeit: "
                    f"{current.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                print(
                    f"Tag: {config['day']}"
                )

                print(
                    f"Kanal: {config['channel_id']}"
                )

                print("----------------------------------------")

                target = await get_target_channel()

                if target is not None:

                    try:

                        day = int(
                            config["day"]
                        )

                        # ------------------------------------------------
                        # NACHRICHT SENDEN
                        # ------------------------------------------------

                        await target.send(
                            f"📅 **Tag {day}**"
                        )

                        # ------------------------------------------------
                        # NÄCHSTEN TAG BERECHNEN
                        # ------------------------------------------------

                        config["day"] = (
                            day
                            + int(config["increment"])
                        )

                        # ------------------------------------------------
                        # ZEITPUNKT SPEICHERN
                        # ------------------------------------------------

                        config["last_run"] = (
                            current_key
                        )

                        save_config()

                        print(
                            f"✅ Tag {day} "
                            "erfolgreich gesendet."
                        )

                        print(
                            f"➡️ Nächster Tag: "
                            f"{config['day']}"
                        )

                    except discord.Forbidden:

                        print(
                            "❌ Keine Berechtigung "
                            "zum Schreiben im Kanal."
                        )

                    except discord.HTTPException as error:

                        print(
                            f"❌ Discord-Fehler: {error}"
                        )

                else:

                    print(
                        "❌ Zielkanal nicht gefunden."
                    )

            # ------------------------------------------------
            # ALLE 5 SEKUNDEN PRÜFEN
            # ------------------------------------------------

            await asyncio.sleep(5)

        except asyncio.CancelledError:

            print(
                "Tageszähler-Task beendet."
            )

            break

        except Exception as error:

            print(
                f"FEHLER IM TAGESZÄHLER: {error}"
            )

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
            "Tageszähler-Task wurde gestartet."
        )


# ============================================================
# START
# ============================================================

print()
print(
    "Bot wird gestartet..."
)
print(
    "=" * 40
)

bot.run(TOKEN)
```
