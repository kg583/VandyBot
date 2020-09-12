from collections import OrderedDict
from discord import Embed
from discord.ext import commands

from ..helper import *
from . import menu

_dir = "vandybot/dining"


class Dining(commands.Cog):
    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

        self._units = reader(f"{_dir}/units")
        self._food_trucks = reader(f"{_dir}/food_trucks")
        self._meals = reader(f"{_dir}/meals")

    @staticmethod
    def color(meal):
        colors = {"Breakfast": 0xEABA38,
                  "Lunch": 0xCC2537,
                  "Dinner": 0x9013FE,
                  "Brunch": 0xF16907,
                  "Daily Offerings": 0x4A90E2}
        return colors.get(meal, DEFAULT_COLOR)

    @staticmethod
    def generate_embed(title, url, color, fields, max_len=500):
        embed = Embed(title=title, url=url, color=color)
        embed.set_thumbnail(url=f"{github}/{_dir}/thumbnail.jpg")
        for header, text in fields.items():
            if len(text) > max_len:
                splitter = text[max_len:].find(", ")
                text = text[:splitter + max_len] + ", ..."
            embed.add_field(name=header, value=text, inline=False)

        return embed

    async def reset(self):
        # Because POST requests are bad and should feel bad
        await self._session.post(menu.url + "/Home/ResetSelections", headers=menu.header)

    @commands.command(name="menu",
                      brief="Gets menus from on-campus dining locations.",
                      help="Retrieves the menu for a given date and meal from on-campus dining locations. "
                           "Arguments can be specified in any order.",
                      usage="location [day=today] [meal=next]\n"
                            "~menu location day [meal=all]\n")
    async def menu(self, ctx, *args):
        unit, day, meal = self.menu_parse(args)

        # Food trucks are special
        if unit in self._food_trucks.values():
            menu_img = await menu.food_truck_menu(self._session, unit)
            embed = Embed(title=unit, url=menu.food_truck_url, color=0x7ED321)
            embed.set_image(url=menu_img)
            await ctx.send(embed=embed)
        else:
            unit_oid = await menu.get_unit_oid(self._session, unit)
            unit_menu = await menu.get_menu(self._session, unit_oid)
            unit_hours = await menu.get_hours(self._session, unit_oid, unit_menu)

            if meal == "next":
                meal, day = menu.next_meal(unit_hours, day)

            meals = [meal] if meal != "all" else unit_menu[day]

            # The dispatch is mainly to make the "all" argument less request-intensive
            for meal in meals:
                embed = await self.menu_dispatch(unit_menu, unit_hours, unit, day, meal)
                await ctx.send(embed=embed)

    async def menu_dispatch(self, unit_menu, unit_hours, unit, day, meal):
        # Quality of life parse
        if meal not in unit_menu[day]:
            meal = {"Breakfast": "Brunch", "Brunch": "Breakfast"}.get(meal, meal)

        items = await menu.select(self._session, unit_menu, unit, day, meal)

        if day == today():
            meal_str = f"{meal} Today"
        elif day == tomorrow():
            meal_str = f"{meal} Tomorrow"
        else:
            meal_str = f"{meal} on {day}"

        block = unit_hours[day][meal]
        if now().time() < block[0] and day == today() or day == tomorrow():
            time_str = f"CLOSED until {block[0]}"
        elif now().time() > block[1] and day == today():
            time_str = f"CLOSED since {block[1]}"
        elif block[0] <= now().time() <= block[1] and day == today():
            time_str = f"OPEN until {block[1]}"
        else:
            time_str = f"OPENS at {block[0]}"

        fields = OrderedDict({meal_str: time_str})
        fields.update({header: ", ".join(text) for header, text in items.items()})
        embed = self.generate_embed(title=unit, url=menu.url, color=self.color(meal), fields=fields)

        return embed

    @menu.error
    async def menu_error(self, ctx, error):
        embed = self.generate_embed(title="Something went wrong", url=None, color=DEFAULT_COLOR,
                                    fields={type(error).__name__: str(error)})
        await ctx.send(embed=embed)

    def menu_parse(self, args):
        unit, day, meal = None, today(), "next"

        # Args can be in any order
        for arg in args:
            arg = arg.lower().replace("'", "").translate(seps)
            try:
                # Is a unit?
                unit = self._units[arg]
            except KeyError:
                try:
                    # Is a food truck?
                    unit = self._food_trucks[arg]
                except KeyError:
                    try:
                        # Is a meal?
                        if arg in ["all", "next"]:
                            meal = arg
                        else:
                            meal = self._meals[arg]
                    except KeyError:
                        # Is a day?
                        if arg == "today":
                            day = today()
                        elif arg == "tomorrow":
                            day = tomorrow()
                        else:
                            try:
                                day = Day(arg)
                            except ValueError:
                                raise commands.BadArgument(f"Invalid argument provided: {arg}") from None

            if unit is None:
                raise commands.BadArgument("No dining facility was provided.") from None
        return unit, day, meal

    @menu.after_invoke
    async def menu_reset(self, _):
        await self.reset()

    @commands.command(name="hours",
                      brief="Gets the operating hours for on-campus dining locations.",
                      help="Retrieves the operating hours on a given day for on-campus dining locations. "
                           "Arguments can be specified in any order.",
                      usage="location [day=today]")
    async def hours(self, ctx, *args):
        unit, day = self.hours_parse(args)

        unit_oid = await menu.get_unit_oid(self._session, unit)
        unit_menu = await menu.get_menu(self._session, unit_oid)
        unit_hours = await menu.get_hours(self._session, unit_oid, unit_menu)

        try:
            hours = unit_hours[day]
        except KeyError:
            raise menu.HoursNotFound(unit)

        if day in unit_menu:
            fields = {f"Hours on {day}": "\n".join("{}: {} to {}".format(meal, *hours[meal])
                                                   for meal in unit_menu[day] if meal != "Daily Offerings")}
        else:
            fields = {f"Hours on {day}": "CLOSED"}

        embed = self.generate_embed(title=unit, url=menu.url, color=0x4A90E2, fields=fields)
        await ctx.send(embed=embed)

    @hours.error
    async def hours_error(self, ctx, error):
        embed = self.generate_embed(title="Something went wrong", url=None, color=DEFAULT_COLOR,
                                    fields={type(error).__name__: str(error)})
        await ctx.send(embed=embed)

    def hours_parse(self, args):
        unit, day = None, today()

        # Args can be in any order
        for arg in args:
            arg = arg.lower().replace("'", "").translate(seps)
            try:
                # Is a unit?
                unit = self._units[arg]
            except KeyError:
                try:
                    # Is a food truck? Too bad.
                    unit = self._food_trucks[arg]
                    raise menu.HoursNotAvailable from None
                except KeyError:
                    # Is a day?
                    if arg == "today":
                        day = today()
                    elif arg == "tomorrow":
                        day = tomorrow()
                    else:
                        try:
                            day = Day(arg)
                        except ValueError:
                            raise commands.BadArgument(f"Invalid argument provided: {arg}") from None

            if unit is None:
                raise commands.BadArgument("No dining facility was provided.") from None
        return unit, day

    @hours.after_invoke
    async def hours_reset(self, _):
        await self.reset()
