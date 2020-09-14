import env_file
from discord import Activity, ActivityType, Embed
from discord.ext import commands

# Import cogs
from . import debug
from .helper import *

from vandybot.covid import Covid
from vandybot.dining import Dining

bot = commands.Bot(command_prefix=commands.when_mentioned_or("~"))


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    activity = "Type ~help for usage!" if not debug.debugging else "Currently undergoing maintenance."
    await bot.change_presence(activity=Activity(type=ActivityType.playing, name=activity))


@bot.event
async def on_message(message):
    if not debug.debugging or message.guild.id == debug.guild:
        await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    embed = Embed(title="Something went wrong", color=DEFAULT_COLOR)
    if isinstance(error, commands.CommandInvokeError):
        name, value = str(error).split(":", maxsplit=3)[1:]
    else:
        name, value = type(error).__name__, str(error)

    embed.add_field(name=name, value=value)
    await ctx.send(embed=embed)


async def main():
    # Establish cogs
    bot.add_cog(Dining(bot))
    bot.add_cog(Covid(bot))

    # Tokens
    token = env_file.get()
    if "DEBUGGING" in token:
        debug.debugging = bool(token["DEBUGGING"])
    if "DEBUG_GUILD_ID" in token:
        debug.guild = int(token["DEBUG_GUILD_ID"])

    await bot.start(token["BOT_TOKEN"])
