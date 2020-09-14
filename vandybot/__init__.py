import env_file
from discord import Activity, ActivityType, Embed
from discord.ext import commands

# Import cogs
from .helper import *
from vandybot.covid import Covid
from vandybot.dining import Dining


bot = commands.Bot(command_prefix=commands.when_mentioned_or("~"))


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    await bot.change_presence(activity=Activity(type=ActivityType.playing, name="Type ~help for usage!"))


@bot.event
async def on_message(message):
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

    await bot.start(token["BOT_TOKEN"])
