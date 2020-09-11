import env_file
from discord import Activity, ActivityType
from discord.ext import commands

# Import cogs
from vandybot.covid import Covid
from vandybot.dining import Dining


bot = commands.Bot(command_prefix=commands.when_mentioned_or("~"))


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    await bot.change_presence(activity=Activity(type=ActivityType.custom, name="Type ~help for usage!"))


@bot.event
async def on_message(message):
    await bot.process_commands(message)


async def main():
    # Establish cogs
    bot.add_cog(Dining(bot))
    bot.add_cog(Covid(bot))

    # Tokens
    token = env_file.get()

    await bot.start(token["BOT_TOKEN"])
