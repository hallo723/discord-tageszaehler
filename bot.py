import os
import discord
from discord.ext import commands, tasks
from datetime import datetime
from pathlib import Path
import json

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
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# BOT ONLINE
# =========================================================

@bot.event
async def on_ready():
    print(f"{bot.user} ist online!")

    if not counter_loop.is_running():
        counter_loop.start()


# =========================================================
# TÄGLICHER ZÄHLER
# =========================================================

@tasks.loop(seconds=30)
async def counter_loop():

    if not config["running"]:
        return

    if config["paused"]:
        return

    now = datetime.now()

    if now.hour != config["hour"]:
        return

    if now.minute != config["minute"]:
        return

    today = now.strftime("%Y-%m-%d")

    if config["last_run"] == today:
        return

    channel_id = config["channel_id"]

    if channel_id is None:
        return

    channel = bot.get_channel(channel_id)

    if channel is None:
        return

    current_day = config["day"]

    try:
        await channel.send(f"📅 **Tag {current_day}**")

        config["day"] += config["increment"]
        config["last_run"] = today

        save_config()

    except Exception as error:
        print(f"Fehler beim Senden: {error}")


# =========================================================
# SETUP
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup(ctx):

    config["channel_id"] = ctx.channel.id
    config["running"] = False
    config["paused"] = False
    config["hour"] = 12
    config["minute"] = 0
    config["day"] = 1
    config["increment"] = 1
    config["last_run"] = ""

    save_config()

    await ctx.send(
        "⚙️ **Zähler eingerichtet!**\n\n"
        f"📢 Kanal: {ctx.channel.mention}\n"
        "🔢 Startwert: **1**\n"
        "📈 Erhöhung: **+1**\n"
        "⏰ Uhrzeit: **12:00**\n"
        "📅 Intervall: **jeden Tag**\n\n"
        "Benutze `!start`, um den Zähler zu starten."
    )


# =========================================================
# START
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def start(ctx):

    config["running"] = True
    config["paused"] = False

    save_config()

    await ctx.send(
        "🟢 **Zähler gestartet!**\n"
        f"⏰ Zählzeitpunkt: "
        f"**{config['hour']:02d}:{config['minute']:02d}**"
    )


# =========================================================
# STOP
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def stop(ctx):

    config["running"] = False

    save_config()

    await ctx.send("🔴 **Zähler gestoppt.**")


# =========================================================
# PAUSE
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def pause(ctx):

    config["paused"] = True

    save_config()

    await ctx.send("⏸️ **Zähler pausiert.**")


# =========================================================
# RESUME
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def resume(ctx):

    config["paused"] = False
    config["running"] = True

    save_config()

    await ctx.send("▶️ **Zähler fortgesetzt.**")


# =========================================================
# UHRZEIT ÄNDERN
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def time(ctx, new_time: str):

    try:
        hour, minute = map(int, new_time.split(":"))

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError

        config["hour"] = hour
        config["minute"] = minute

        save_config()

        await ctx.send(
            f"⏰ Uhrzeit geändert auf **{hour:02d}:{minute:02d}**."
        )

    except ValueError:
        await ctx.send(
            "❌ Falsches Format.\n"
            "Benutze z. B. `!time 18:30`"
        )


# =========================================================
# TAG SETZEN
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setday(ctx, number: int):

    if number < 0:
        await ctx.send("❌ Die Zahl darf nicht negativ sein.")
        return

    config["day"] = number

    save_config()

    await ctx.send(
        f"🔢 Der Zähler steht jetzt auf **Tag {number}**."
    )


# =========================================================
# ERHÖHUNG ÄNDERN
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def add(ctx, number: int):

    if number == 0:
        await ctx.send("❌ Die Erhöhung darf nicht 0 sein.")
        return

    config["increment"] = number

    save_config()

    await ctx.send(
        f"📈 Die Erhöhung wurde auf **{number:+d}** gesetzt."
    )


# =========================================================
# KANAL SETZEN
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def channel(ctx):

    config["channel_id"] = ctx.channel.id

    save_config()

    await ctx.send(
        f"📢 Dieser Kanal ({ctx.channel.mention}) "
        "ist jetzt der Zähler-Kanal."
    )


# =========================================================
# STATUS
# =========================================================

@bot.command()
async def status(ctx):

    if config["running"]:
        if config["paused"]:
            status_text = "⏸️ Pausiert"
        else:
            status_text = "🟢 Aktiv"
    else:
        status_text = "🔴 Gestoppt"

    channel = "Nicht festgelegt"

    if config["channel_id"]:
        channel_obj = bot.get_channel(config["channel_id"])

        if channel_obj:
            channel = channel_obj.mention

    await ctx.send(
        "⚙️ **ZÄHLER-STATUS**\n\n"
        f"Status: {status_text}\n"
        f"📅 Aktueller Wert: **{config['day']}**\n"
        f"📈 Erhöhung: **{config['increment']:+d}**\n"
        f"⏰ Uhrzeit: **{config['hour']:02d}:{config['minute']:02d}**\n"
        f"📢 Kanal: {channel}"
    )


# =========================================================
# RESET
# =========================================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def reset(ctx):

    config["running"] = False
    config["paused"] = False
    config["hour"] = 12
    config["minute"] = 0
    config["day"] = 1
    config["increment"] = 1
    config["last_run"] = ""

    save_config()

    await ctx.send(
        "♻️ **Zähler zurückgesetzt.**\n"
        "Startwert: 1\n"
        "Uhrzeit: 12:00\n"
        "Erhöhung: +1"
    )


# =========================================================
# FEHLERBEHANDLUNG
# =========================================================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ Dafür brauchst du die Berechtigung "
            "**Server verwalten**."
        )

    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Es fehlt ein Argument."
        )

    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            "❌ Ungültiger Wert."
        )

    elif isinstance(error, commands.CommandNotFound):
        pass

    else:
        print(f"Fehler: {error}")


# =========================================================
# BOT STARTEN
# =========================================================

bot.run(TOKEN)