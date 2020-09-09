import dbl
from discord.ext import commands


class TopGG(commands.Cog):
    def __init__(self, bot, dbl_token):
        self.bot = bot
        self._token = dbl_token
        self._dbl = dbl.DBLClient(self.bot, self._token, autopost=True)

    @commands.Cog.listener()
    async def on_guild_post(self):
        print("Server count posted successfully")
