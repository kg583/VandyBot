import env_file
from discord import Activity, ActivityType
from discord.ext import commands

# Import submodules
from vandybot.dining import Dining
from vandybot.topgg import TopGG


bot = commands.Bot(command_prefix=commands.when_mentioned_or("~"))


@bot.event
async def on_ready():
    print("VandyBot has connected. Awaiting command requests...")
    await bot.change_presence(activity=Activity(type=ActivityType.custom, name="Type ~help for usage!"))


@bot.event
async def on_message(message):
    await bot.process_commands(message)


async def main():
    bot.add_cog(Dining(bot))

    token = env_file.get()
    if 'DBL_TOKEN' in token:
        bot.add_cog(TopGG(bot, token['DBL_TOKEN']))

    await bot.start(token["BOT_TOKEN"])
