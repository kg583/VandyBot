from discord import Embed
from discord.ext import commands

from ..helper import *
from . import covid

_dir = "vandybot/covid"


class Covid(commands.Cog):
    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

    @staticmethod
    def generate_embed(title, url, headers, rows):
        embed = Embed(title=title, url=url, color=0xD0021B)
        embed.set_thumbnail(url=f"{github_raw}/{_dir}/thumbnail.png")
        for index, header in enumerate(headers):
            embed.add_field(name=header, value="\n".join(row[index] for row in rows))

        return embed

    @commands.command(name="covid",
                      brief="Gets current statistics on COVID-19 cases.",
                      help="Retrieves the statistics to-date for COVID-19 tests and positive cases among Vanderbilt "
                           "students, as well as an overall summary of the data.",
                      usage="")
    async def covid(self, ctx):
        data = await covid.get_data(self._session)
        embed = self.generate_embed(title="COVID-19 Dashboard", url=covid.url,
                                    headers=("Week", "Test Results", "Positivity Rate"), rows=data)
        await ctx.send(embed=embed)
