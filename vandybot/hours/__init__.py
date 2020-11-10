from discord import Embed
from discord.ext import commands

from ..helper import *
from . import hours

_dir = "vandybot/hours"


class Hours(commands.Cog):
    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

        self._dining = reader(f"{_dir}/dining")
        self._libraries = reader(f"{_dir}/libraries")

        # Swapped unit commands
        for loc in self._dining:
            command = commands.Command(self.hours_from_dining(loc),
                                       name=loc,
                                       help=f"Alias for ~hours {loc} and ~menu {loc}.",
                                       usage=f"hours [day=today]\n"
                                             f"~{loc} menu [day=today] [menu=next]\n"
                                             f"~{loc} menu [day] [meal=all]",
                                       hidden=True)
            command.after_invoke(self.hours_reset)
            self._bot.add_command(command)

        for loc in self._libraries:
            command = commands.Command(self.hours_from_library(loc),
                                       name=loc,
                                       help=f"Alias for ~hours {loc}.",
                                       usage=f"hours [day=today]\n",
                                       hidden=True)
            self._bot.add_command(command)

    @staticmethod
    def generate_embed(title, url, fields, footer, inline=False):
        embed = Embed(title=title, url=url, color=0x50E3C2)
        embed.set_thumbnail(url=f"{github_raw}/{_dir}/thumbnail.png")
        embed.set_footer(text=footer)
        for header, text in fields.items():
            embed.add_field(name=header, value=text, inline=inline)

        return embed

    async def reset(self):
        # Because POST requests are bad and should feel bad
        await self._session.post(hours.dining_url + "/Home/ResetSelections", headers=hours.dining_header)

    @commands.command(name="hours",
                      brief="Gets the operating hours for various on-campus facilities.",
                      help="Retrieves the operating hours on a given day for on-campus dining centers and libraries. "
                           "Arguments can be specified in any order.",
                      usage="location [day=today]\n"
                            "~hours list")
    async def hours(self, ctx, *args):
        if args and args[0] == "list":
            await ctx.send(embed=self.hours_list())
        else:
            locs, days = self.hours_parse(args)
            for loc in locs:
                if loc in self._libraries.values():
                    all_hours, footer = await hours.library_hours(self._session, loc)
                    url = hours.dining_url
                elif loc in self._dining.values():
                    unit_oid = await hours.dining_unit_oid(self._session, loc)
                    all_hours, footer = await hours.dining_hours(self._session, unit_oid)
                    url = hours.library_url
                else:
                    raise hours.UnitNotFound(loc)

                for day in days:
                    try:
                        loc_hours = all_hours[day]
                    except KeyError:
                        raise hours.HoursNotFound(loc)

                    if "Closed" in loc_hours:
                        fields = {f"Hours on {day}": "CLOSED"}
                    else:
                        fields = {f"Hours on {day}": "\n".join("{} to {}".format(*span) for span in loc_hours)}

                    embed = self.generate_embed(title=loc, url=url, fields=fields, footer=footer)
                    await ctx.send(embed=embed)

    def hours_from_dining(self, unit):
        async def dispatcher(ctx, hour_arg, *args):
            if hour_arg.lower() != "hours":
                if hour_arg.lower() != "menu":
                    raise commands.BadArgument(f"Scope not provided. Use `~{unit} menu` or `~{unit} hours`.")
                else:
                    # Yucky ew gross cross-cog call
                    await self._bot.get_cog("Dining").menu(ctx, unit, *args)
            else:
                await self.hours(ctx, unit, *args)

        return dispatcher

    def hours_from_library(self, unit):
        async def dispatcher(ctx, hour_arg, *args):
            if hour_arg.lower() != "hours":
                raise commands.BadArgument(f"Scope not provided. Use `~hours {unit}` or `~{unit} hours`.")
            else:
                await self.hours(ctx, unit, *args)

        return dispatcher

    def hours_list(self):
        embed = self.generate_embed(title="On-Campus Facilities", url=None,
                                    fields=reader(f"{_dir}/list"),
                                    footer="Posted hours may not reflect special events or unexpected closures.",
                                    inline=True)
        embed.add_field(name="Additional Arguments",
                        value="Up to five total selections may be requested at once\ne.g. `commons tomorrow monday`\n"
                              "Arguments can be specified with different separators\ne.g. `kissam_munchie`\n"
                              "To use spaces, wrap the entire name in quotes\ne.g. `\"biomedical library\"`\n"
                              "Alternative names are also permitted\n"
                              "e.g. `stevenson` for `science-and-engineering-library`",
                        inline=False)
        return embed

    def hours_parse(self, args):
        locs, days = [], []

        # Args can be in any order
        for arg in args:
            arg = arg.lower().replace("'", "").translate(seps)
            try:
                # Is a dining unit?
                locs.append(self._dining[arg])
            except KeyError:
                try:
                    # Is a library?
                    locs.append(self._libraries[arg])
                except KeyError:
                    # Is a day?
                    if arg == "today":
                        days.append(today())
                    elif arg == "tomorrow":
                        days.append(tomorrow())
                    else:
                        try:
                            days.append(Day(arg))
                        except ValueError:
                            if arg == "library":
                                # He he
                                raise commands.BadArgument("Which one, dumbass?") from None
                            else:
                                raise commands.BadArgument(f"Invalid argument provided: {arg}") from None

        if not locs:
            raise commands.BadArgument("No facility was provided.") from None
        if not days:
            days = [today()]

        if len(locs) * len(days) > max_returns:
            raise TooManySelections from None

        return locs, days

    @hours.after_invoke
    async def hours_reset(self, *_):
        await self.reset()
