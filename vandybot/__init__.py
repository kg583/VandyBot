import env_file
from discord import Embed
from discord.ext import commands

from .helper import *

# Import cogs
from vandybot.dining import Dining
from vandybot.hours import Hours

PREFIX = "~"
bot = commands.Bot(command_prefix=commands.when_mentioned_or(PREFIX),
                   case_insensitive=True)

# Read tokens
tokens = env_file.get()
DEBUGGING = tokens.get("DEBUGGING", "False") == "True"
DEBUG_GUILD_ID = int(tokens.get("DEBUG_GUILD_ID", "0"))

TOKEN = tokens.get("BOT_TOKEN")
if DEBUGGING:
    TOKEN = tokens.get("DEBUG_BOT_TOKEN", TOKEN)


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    text = DEFAULT_TEXT if not DEBUGGING else "Currently undergoing maintenance"
    await bot.change_presence(activity=presence(text))


@bot.event
async def on_message(message):
    if not message.author.bot:
        if not DEBUGGING or message.guild.id == DEBUG_GUILD_ID:
            await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    embed = Embed(title="Something went wrong", color=DEFAULT_COLOR)
    if not isinstance(error, commands.CommandNotFound):
        if isinstance(error, commands.CommandInvokeError):
            name, value = str(error).split(":", maxsplit=2)[1:]
        else:
            name, value = type(error).__name__, str(error)

        embed.add_field(name=name, value=value)
        await ctx.send(embed=embed)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id != bot.user.id:
        for cog in map(bot.get_cog, bot.cogs):
            if cog.cached(payload.message_id):
                await cog.on_raw_reaction_add(payload)


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id != bot.user.id:
        for cog in map(bot.get_cog, bot.cogs):
            if cog.cached(payload.message_id):
                await cog.on_raw_reaction_remove(payload)


@bot.command(name="github",
             aliases=("code",),
             brief="VandyBot's GitHub repository",
             help="Returns the link to VandyBot's GitHub repository.")
async def github(ctx):
    embed = Embed(title="VandyBot on GitHub", url=GITHUB_URL, color=DEFAULT_COLOR)
    embed.set_thumbnail(url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
    embed.add_field(name="VandyBot is Open Source!", value="Check out the code on GitHub.")

    await ctx.send(embed=embed)


@bot.command(name="ping",
             brief="Pings the VandyBot client",
             help="Returns the current latency to the VandyBot client.")
async def ping(ctx):
    await ctx.send(f"~pong ({bot.latency * 1000:.3f}ms)")


def startup():
    print("VandyBot is starting up...")
    print(f"DEBUG MODE == {DEBUGGING}\n")

    # Establish cogs
    bot.add_cog(Dining(bot))
    bot.add_cog(Hours(bot))


async def main():
    # Start cogs
    for cog in map(bot.get_cog, bot.cogs):
        await cog.startup()
        print()

    # Connect
    print("VandyBot is connecting...")
    await bot.login(TOKEN, bot=True)
    await bot.connect(reconnect=True)
