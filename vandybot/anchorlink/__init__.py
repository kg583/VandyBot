from discord import Embed
from discord.ext import commands

from ..helper import *

_dir = "vandybot/anchorlink"


# Errors
class EventError(Exception):
    def __init__(self, message):
        super().__init__(message)


# Main Cog
class AnchorLink(commands.Cog):
    EVENT_URL = "https://anchorlink.vanderbilt.edu/api/discovery/event/search"
    IMG_URL = "https://se-infra-imageserver2.azureedge.net/clink/images/"

    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

        self._category_ids = reader(f"{_dir}/category_ids")

    @staticmethod
    def generate_embed(title, url, color, fields, inline=False, max_len=500):
        embed = Embed(title=title, url=url, color=color)
        embed.set_thumbnail(url=f"{github_raw}/{_dir}/thumbnail.jpeg")
        for header, text in fields.items():
            if len(text) > max_len:
                splitter = text[max_len:].find(", ")
                text = text[:splitter + max_len] + ", ..."
            embed.add_field(name=header, value=text, inline=inline)

        return embed

    async def get_events(self, take=10, query="", ends_after=now(), starts_before=None,
                         is_online="", themes=None, category_ids=None, perks=None):
        # Set GET params
        params = {"query": query,
                  "take": take,
                  "endsAfter": ends_after.isoformat(timespec="seconds"),
                  "startsBefore": starts_before.isoformat(timespec="seconds") if starts_before is not None else "",
                  "isOnline": str(is_online).lower()}

        # Iterable parameters
        if themes is not None:
            params.update(parameterize("themes", themes))
        if category_ids is not None:
            params.update(parameterize("categoryIds", category_ids))
        if perks is not None:
            params.update(parameterize("benefitNames", perks))

        data = await jfetch(self._session, self.EVENT_URL, params=params)
        return data["@odata.count"], data["@search.facets"], data["value"]

    async def startup(self):
        pass

    async def reset(self):
        pass

    @commands.command(name="events")
    async def events(self, ctx, *args):
        pass
