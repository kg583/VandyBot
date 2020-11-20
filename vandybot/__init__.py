import env_file
from discord import Activity, ActivityType, Embed
from discord.ext import commands

# Import cogs
from . import debug
from .helper import *

from vandybot.covid import Covid
from vandybot.dining import Dining
from vandybot.hours import Hours

bot = commands.Bot(command_prefix=commands.when_mentioned_or("~"),
                   case_insensitive=True)


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    activity = "Type ~help for usage!" if not debug.debugging else "Currently undergoing maintenance"
    await bot.change_presence(activity=Activity(type=ActivityType.playing, name=activity))


@bot.event
async def on_message(message):
    if message.author != bot.user and (not debug.debugging or message.guild.id == debug.guild):
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


@bot.command(name="github",
             aliases=("code",),
             brief="VandyBot's GitHub repository.",
             help="Returns the link to VandyBot's GitHub repository.")
async def github(ctx):
    embed = Embed(title="VandyBot on GitHub", url=github_url, color=DEFAULT_COLOR)
    embed.set_thumbnail(url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
    embed.add_field(name="VandyBot is Open Source!", value="Check out the code on GitHub.")

    await ctx.send(embed=embed)


@bot.command(name="ping",
             brief="Pings the VandyBot client.",
             help="Returns the current latency to the VandyBot client.")
async def ping(ctx):
    await ctx.send(f"~pong ({bot.latency * 1000:.3f}ms)")


async def main():
    # Establish cogs
    bot.add_cog(Covid(bot))
    bot.add_cog(Dining(bot))
    bot.add_cog(Hours(bot))

    # Tokens
    token = env_file.get()
    if "DEBUGGING" in token:
        debug.debugging = token["DEBUGGING"] == "True"
        print(f"DEBUG MODE == {debug.debugging}")
    if "DEBUG_GUILD_ID" in token:
        debug.guild = int(token["DEBUG_GUILD_ID"])

    await bot.start(token["BOT_TOKEN"])
