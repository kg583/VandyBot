import env_file
from discord import Activity, ActivityType, Embed
from discord.ext import commands

# Import cogs
from .helper import *

from vandybot.covid import Covid
from vandybot.dining import Dining
from vandybot.hours import Hours

PREFIX = "~"
bot = commands.Bot(command_prefix=commands.when_mentioned_or(PREFIX),
                   case_insensitive=True)

# Read tokens
tokens = env_file.get()
DEBUGGING = tokens.get("DEBUGGING", "False") == "True"
DEBUG_GUILD_ID = tokens.get("DEBUG_GUILD_ID", 0)


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    activity = "Type ~help for usage!" if not DEBUGGING else "Currently undergoing maintenance"
    await bot.change_presence(activity=Activity(type=ActivityType.playing, name=activity))


@bot.event
async def on_message(message):
    if message.author != bot.user:
        if not DEBUGGING or message.guild.id == DEBUG_GUILD_ID:
            await bot.process_commands(message)
        elif message.content.startswith(PREFIX):
            await message.channel.send("VandyBot is currently offline for maintenance. Please try again later.")


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


@bot.command(name="github",
             aliases=("code",),
             brief="VandyBot's GitHub repository.",
             help="Returns the link to VandyBot's GitHub repository.")
async def github(ctx):
    embed = Embed(title="VandyBot on GitHub", url=GITHUB_URL, color=DEFAULT_COLOR)
    embed.set_thumbnail(url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
    embed.add_field(name="VandyBot is Open Source!", value="Check out the code on GitHub.")

    await ctx.send(embed=embed)


@bot.command(name="ping",
             brief="Pings the VandyBot client.",
             help="Returns the current latency to the VandyBot client.")
async def ping(ctx):
    await ctx.send(f"~pong ({bot.latency * 1000:.3f}ms)")


def startup():
    print("VandyBot is starting up...")
    print(f"DEBUG MODE == {DEBUGGING}")

    # Establish cogs
    bot.add_cog(Covid(bot))
    bot.add_cog(Dining(bot))
    bot.add_cog(Hours(bot))


async def main():
    if "ASP_NET_SESSION_ID" in tokens:
        await bot.get_cog("Dining").get_cookie(default=tokens["ASP_NET_SESSION_ID"])

    # Start cogs
    for cog in bot.cogs:
        await bot.get_cog(cog).startup()

    # Connect
    print("VandyBot is connecting...")
    await bot.login(tokens["BOT_TOKEN"], bot=True)
    await bot.connect(reconnect=True)
