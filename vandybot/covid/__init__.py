from discord import Embed
from discord.ext import commands

from ..helper import *

_dir = "vandybot/covid"


# Main Cog
class Covid(commands.Cog):
    URL = "https://www.vanderbilt.edu/coronavirus/covid19dashboard/"

    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

    @staticmethod
    def generate_embed(title, url, headers, rows):
        embed = Embed(title=title, url=url, color=0xD0021B)
        embed.set_thumbnail(url=f"{GITHUB_RAW}/{_dir}/thumbnail.png")
        for index, header in enumerate(headers):
            embed.add_field(name=header, value="\n".join(row[index] for row in rows))

        embed.set_footer(text="Spring semester testing data is not yet available.")
        return embed

    @staticmethod
    def sum_column(entries, column):
        return sum(int(entry[column].replace(",", "")) for entry in entries)

    async def get_data(self):
        response = await fetch(self._session, self.URL)
        soup = BeautifulSoup(response, "html.parser")
        rows = soup.find("table").find_all("tr")
        entries = [[entry.get_text() for entry in row.find_all("td")] for row in rows][1:][::-1]

        # Calculate total
        total = ["TOTAL", self.sum_column(entries, 1), self.sum_column(entries, 2)]
        total.append(f"{100 * total[2] / total[1]:.2f}%")
        total = list(map(bold, [total[0], f"{total[1]:,}", f"{total[2]:,}", str(total[3])]))
        entries.append(total)

        return [[entry[0], f"{entry[2]}/{entry[1]}", entry[3]] for entry in entries]

    async def startup(self):
        pass

    async def reset(self):
        pass

    @commands.command(name="covid",
                      brief="Gets current statistics on COVID-19 cases.",
                      help="Retrieves the statistics to-date for COVID-19 tests and positive cases among Vanderbilt "
                           "students, as well as an overall summary of the data.",
                      usage="")
    async def covid(self, ctx):
        data = await self.get_data()
        headers = tuple(map(underline, ("Week", "Test Results", "Positivity Rate")))
        embed = self.generate_embed(title="COVID-19 Dashboard", url=self.URL, headers=headers, rows=data)
        await ctx.send(embed=embed)
