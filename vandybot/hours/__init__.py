from discord import Embed
from discord.ext import commands

from ..helper import *

_dir = "vandybot/hours"


# Errors
class HoursError(Exception):
    def __init__(self, message):
        super().__init__(message)


class HoursNotFound(HoursError):
    def __init__(self, unit, message="The operating hours at {} could not be found."):
        super().__init__(message.format(unit))


class UnitNotFound(HoursError):
    def __init__(self, unit, message="{} could not be found."):
        super().__init__(message.format(unit))


class UnitClosed(UnitNotFound):
    def __init__(self, unit, message="{} is currently closed.", reason=""):
        if reason:
            message = "{} is currently closed due to {}."
            super().__init__(unit, message.format("{}", reason))
        else:
            super().__init__(unit, message)


# Main Cog
class Hours(commands.Cog):
    # URL stuff
    BOOKSTORE_URL = "https://www.bkstr.com/vanderbiltstore/home"
    DINING_URL = "https://netnutrition.cbord.com/nn-prod/vucampusdining"
    DINING_HEADER = {"Referer": DINING_URL}
    LIBRARY_URL = "https://www.library.vanderbilt.edu/hours.php"
    POST_OFFICE_URL = "https://www.vanderbilt.edu/mailservices/contact-us/locations-hours-services.php"

    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()
        self._list = reader(f"{_dir}/list")

        self._bookstores = reader(f"{_dir}/bookstores")
        self._dining = reader(f"{_dir}/dining")
        self._libraries = reader(f"{_dir}/libraries")
        self._post_offices = reader(f"{_dir}/post_offices")

        self._loc_conditions = reader(f"{_dir}/loc_conditions")

        # I'd like to use this but POST requests make it dumb
        self._dining_oids = reader(f"{_dir}/dining_oids")

        self._bookstore_hours = hours_reader(f"{_dir}/bookstore_hours")
        self._post_office_hours = hours_reader(f"{_dir}/post_office_hours")

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
        embed.set_thumbnail(url=f"{GITHUB_RAW}/{_dir}/thumbnail.png")
        embed.set_footer(text=footer)
        for header, text in fields.items():
            embed.add_field(name=header, value=text, inline=inline)

        return embed

    async def get_dining_hours(self, unit: str):
        unit_oid = await self.get_dining_unit_oid(unit)
        response = await post(self._session, f"{self.DINING_URL}/Unit/GetHoursOfOperationMarkup",
                              data={"unitOid": unit_oid},
                              headers=self.DINING_HEADER)
        soup = BeautifulSoup(response, "html.parser")
        blocks = [Day(time) if time in Day.DAYS else time for time in map(BeautifulSoup.get_text, soup.find_all("td"))]
        index = 0
        hours = {}

        # Assign time blocks to meals
        while index < len(blocks):
            day = blocks[index]
            # Block elements are either Days or times
            if isinstance(day, Day):
                if blocks[index + 1].lower() == "closed":
                    # This whole section could be one itertools block if not for closures
                    hours.update({day: ["Closed"]})
                else:
                    hours.update({day: hours.get(day, []) + [(Time(blocks[index + 1]), Time(blocks[index + 2]))]})
                    index += 1

            index += 1

        return hours, "Dining areas may be open to students between listed meal times"

    async def get_dining_hours_dispatch(self, slug: str):
        return (await self.get_dining_hours(unit_name(slug)))[0]

    async def get_dining_unit_oid(self, loc: str):
        response = await fetch(self._session, self.DINING_URL)
        soup = BeautifulSoup(response, "html.parser")
        units = {unit.get_text(): find_oid(unit) for unit in soup.find_all(class_="d-flex flex-wrap col-9 p-0")}
        try:
            return units[loc]
        except KeyError:
            raise UnitNotFound(loc) from None

    async def get_library_hours(self, library: str):
        response = await fetch(self._session, self.LIBRARY_URL)
        soup = BeautifulSoup(response, "html.parser")

        blocks = soup.find_all("table", class_="table hours-table")
        footers = {block.find("th").get_text(): block.find("td").get_text().split("  ")[0] for block in blocks}
        hours = {block.find("th").get_text(): {
            Day(day.get_text().strip()[:3]): [tuple(to_time(span) for span in time.get_text().strip().split("-"))]
            if time.get_text().strip().lower() != "closed" else ["Closed"]
            for day, time in zip(block.find_all("th")[1:], block.find_all("td")[1:])}
            for block in blocks}

        return hours[library], footers[library]

    async def startup(self):
        print("Starting the Hours cog...")

    async def reset(self):
        # Because POST requests are bad and should feel bad
        await self._session.post(self.DINING_URL + "/Home/ResetSelections", headers=self.DINING_HEADER)

    @commands.command(name="hours",
                      brief="Gets the operating hours for various on-campus facilities",
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
                    all_hours, footer = await self.get_library_hours(loc)
                    url = self.DINING_URL
                elif loc in self._dining.values():
                    all_hours, footer = await self.get_dining_hours(loc)
                    url = self.LIBRARY_URL
                elif loc in self._post_offices.values():
                    all_hours = self._post_office_hours
                    footer = "Weekday hours extended to 5 PM for the first two weeks of the semester"
                    url = self.POST_OFFICE_URL
                elif loc in self._bookstores.values():
                    all_hours = self._bookstore_hours
                    footer = ""
                    url = self.BOOKSTORE_URL
                else:
                    raise UnitNotFound(loc)

                for day in days:
                    try:
                        loc_hours = all_hours[day]
                    except KeyError:
                        raise HoursNotFound(loc)

                    fields = {underline(f"Hours on {day}"): "CLOSED" if "Closed" in loc_hours else "\n".join(
                        "{} to {}".format(*span) for span in loc_hours)}
                    footer = self.hours_footer(loc, footer)
                    embed = self.generate_embed(title=loc, url=url, fields=fields, footer=footer)
                    await ctx.send(embed=embed)

    def hours_footer(self, loc: str, default: str):
        condition = self._loc_conditions.get(loc, "")
        if "Closed due to" == condition[:13]:
            raise UnitClosed(loc, reason=condition[14:])
        elif condition:
            return condition
        else:
            return default

    def hours_from_dining(self, unit: str):
        async def dispatcher(ctx, hour_arg: str, *args):
            if hour_arg.lower() != "hours":
                if hour_arg.lower() != "menu":
                    raise commands.BadArgument(f"Scope not provided. Use `~{unit} menu` or `~{unit} hours`.")
                else:
                    # Yucky ew gross cross-cog call
                    await self._bot.get_cog("Dining").menu(ctx, unit, *args)
            else:
                await self.hours(ctx, unit, *args)

        return dispatcher

    def hours_from_library(self, unit: str):
        async def dispatcher(ctx, hour_arg: str, *args):
            if hour_arg.lower() != "hours":
                raise commands.BadArgument(f"Scope not provided. Use `~hours {unit}` or `~{unit} hours`.")
            else:
                await self.hours(ctx, unit, *args)

        return dispatcher

    def hours_list(self):
        embed = self.generate_embed(title="On-Campus Facilities", url=None,
                                    fields=self._list,
                                    footer="Posted hours may not reflect special events or unexpected closures.",
                                    inline=True)
        embed.add_field(name="Additional Arguments",
                        value="Up to five total selections may be requested at once\ne.g. `commons tomorrow monday`\n"
                              "Arguments can be specified with different separators\ne.g. `post_office`\n"
                              "To use spaces, wrap the entire name in quotes\ne.g. `\"biomedical library\"`\n"
                              "Alternative names are also permitted\n"
                              "e.g. `stevenson` for `science-and-engineering-library`",
                        inline=False)
        return embed

    def hours_parse(self, args):
        locs, days = [], []

        # Args can be in any order
        for arg in args:
            arg = reduce(arg)
            try:
                # Is a dining unit?
                locs.append(self._dining[arg])
                continue
            except KeyError:
                pass

            try:
                # Is a library?
                locs.append(self._libraries[arg])
                continue
            except KeyError:
                pass

            try:
                # Is the post office?
                locs.append(self._post_offices[arg])
                continue
            except KeyError:
                pass

            try:
                # Is the bookstore?
                locs.append(self._bookstores[arg])
                continue
            except KeyError:
                pass

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
                        # Heh heh
                        raise commands.BadArgument("Which one, smartass?") from None
                    else:
                        raise commands.BadArgument(f"Invalid argument provided: {arg}") from None

        if not locs:
            raise commands.BadArgument("No facility was provided.") from None
        if not days:
            days = [today()]

        if len(locs) * len(days) > MAX_RETURNS:
            raise TooManySelections from None

        return locs, days

    @hours.after_invoke
    async def hours_reset(self, *_):
        await self.reset()
