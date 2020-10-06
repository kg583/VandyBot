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

        self._hours_units = reader(f"{_dir}/hours_units")
        self._menu_units = reader(f"{_dir}/menu_units")
        self._food_trucks = reader(f"{_dir}/food_trucks")
        self._meals = reader(f"{_dir}/meals")

        # Swapped unit commands
        for unit in self._menu_units:
            command = commands.Command(self.menu_from_unit(unit),
                                       name=unit,
                                       help=f"Alias for ~menu {unit}.",
                                       usage=f"menu [day=today] [meal=next]\n"
                                             f"~{unit} menu [location] [day] [meal=all]",
                                       hidden=True)
            command.after_invoke(self.menu_reset)
            self._bot.add_command(command)

    @staticmethod
    def color(meal):
        colors = {"Breakfast": 0xEABA38,
                  "Lunch": 0xCC2537,
                  "Dinner": 0x9013FE,
                  "Brunch": 0xF16907,
                  "Daily Offerings": 0x4A90E2}
        return colors.get(meal, DEFAULT_COLOR)

    @staticmethod
    def generate_embed(title, url, color, fields, inline=False, max_len=500):
        embed = Embed(title=title, url=url, color=color)
        embed.set_thumbnail(url=f"{github_raw}/{_dir}/thumbnail.jpg")
        for header, text in fields.items():
            if len(text) > max_len:
                splitter = text[max_len:].find(", ")
                text = text[:splitter + max_len] + ", ..."
            embed.add_field(name=header, value=text, inline=inline)

        return embed

    async def reset(self):
        # Because POST requests are bad and should feel bad
        await self._session.post(menu.url + "/Home/ResetSelections", headers=menu.header)

    @commands.command(name="menu",
                      brief="Gets menus from on-campus dining locations.",
                      help="Retrieves the menu for a given date and meal from on-campus dining locations. "
                           "Arguments can be specified in any order.\n"
                           "Multiple arguments can be provided so long as the total return does not exceed 5 menus.",
                      usage="[location] [day=today] [meal=next]\n"
                            "~menu [location] [day] [meal=all]\n"
                            "~menu list")
    async def menu(self, ctx, *args):
        if args and args[0] == "list":
            await ctx.send(embed=self.menu_list())
        else:
            units, days, meals = self.menu_parse(args)

            for unit in units:
                # Food trucks are special
                if unit in self._food_trucks.values():
                    menu_img = await menu.food_truck_menu(self._session, unit)
                    embed = Embed(title=unit, url=menu.food_truck_url, color=0x7ED321)
                    embed.set_image(url=menu_img)
                    await ctx.send(embed=embed)
                else:
                    unit_oid = await menu.get_unit_oid(self._session, unit)
                    for day in days:
                        unit_menu = await menu.get_menu(self._session, unit_oid)
                        unit_hours = await menu.get_hours(self._session, unit_oid, unit_menu)
                        if meals == ["next"]:
                            # I feel like this should be separate for some reason
                            meal, day = menu.next_meal(unit_hours, day)
                            embed = await self.menu_dispatch(unit_menu, unit_hours, unit, day, meal)
                            await ctx.send(embed=embed)
                        else:
                            if meals == ["all"]:
                                meals = unit_menu[day]
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

        diff = set(unit_menu[day].keys()) - set(unit_hours[day].keys())
        if diff.issubset(set("Daily Offerings")):
            block = unit_hours[day][meal]
            if now().time() < block[0] and day == today() or day == tomorrow():
                time_str = f"CLOSED until {block[0]}"
            elif now().time() > block[1] and day == today():
                time_str = f"CLOSED since {block[1]}"
            elif block[0] <= now().time() <= block[1] and day == today():
                time_str = f"OPEN until {block[1]}"
            else:
                time_str = f"OPENS at {block[0]}"
        else:
            # NetNutrition added a non-existent meal for some reason
            if day == today():
                time_str = "Available today"
            elif day == tomorrow():
                time_str = "Available tomorrow"
            else:
                time_str = f"Available on {day}"

        fields = OrderedDict({meal_str: time_str})
        fields.update({header: ", ".join(text) for header, text in items.items()})
        embed = self.generate_embed(title=unit, url=menu.url, color=self.color(meal), fields=fields)

        return embed

    def menu_from_unit(self, unit):
        async def dispatcher(ctx, menu_arg, *args):
            if menu_arg.lower() != "menu":
                raise commands.BadArgument(f"Menu scope not provided. Use `~menu {unit}` or `~{unit} menu`.")
            else:
                await self.menu(ctx, unit, *args)

        return dispatcher

    def menu_list(self):
        embed = self.generate_embed(title="On-Campus Dining Locations", url=menu.url, color=DEFAULT_COLOR,
                                    fields=reader(f"{_dir}/menu_list"), inline=True)
        embed.add_field(name="Additional Arguments",
                        value="Arguments can be specified with different separators\ne.g. `local_java`\n"
                              "To use spaces, wrap the entire name in quotes\ne.g. `\"commons munchie\"`\n"
                              "Alternative names are also permitted\ne.g. `kitchen` for `kissam`",
                        inline=False)
        return embed

    def menu_parse(self, args):
        units, days, meals = [], [], []

        # Args can be in any order
        for arg in args:
            arg = arg.lower().replace("'", "").translate(seps)
            try:
                # Is a unit?
                units.append(self._menu_units[arg])
            except KeyError:
                try:
                    # Is a food truck?
                    units.append(self._food_trucks[arg])
                except KeyError:
                    try:
                        # Is a meal?
                        if arg in ["all", "next"]:
                            meals = [arg]
                        elif meals != ["all"]:
                            meals.append(self._meals[arg])
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
                                try:
                                    # Is a unit with hours but no menu?
                                    raise menu.MenuNotAvailable(self._hours_units[arg])
                                except KeyError:
                                    raise commands.BadArgument(f"Invalid argument provided: {arg}") from None

        if not units:
            raise commands.BadArgument("No dining facility was provided.") from None
        if not days:
            days = [today()]
        if not meals:
            if days == [today()]:
                meals = ["next"]
            else:
                meals = ["all"]

        if len(units) * len(days) * len(meals) > max_returns:
            raise TooManySelections from None

        return units, days, meals

    @menu.after_invoke
    async def menu_reset(self, *args):
        await self.reset()

    @commands.command(name="hours",
                      brief="Gets the operating hours for on-campus dining locations.",
                      help="Retrieves the operating hours on a given day for on-campus dining locations. "
                           "Arguments can be specified in any order.",
                      usage="location [day=today]\n"
                            "~hours list")
    async def hours(self, ctx, *args):
        if args and args[0] == "list":
            await ctx.send(embed=self.hours_list())
        else:
            unit, day = self.hours_parse(args)

            unit_oid = await menu.get_unit_oid(self._session, unit)
            unit_menu = await menu.get_menu(self._session, unit_oid)
            unit_hours = await menu.get_hours(self._session, unit_oid, unit_menu)

            try:
                hours = unit_hours[day]
            except KeyError:
                raise menu.HoursNotFound(unit)

            if day in unit_menu:
                try:
                    fields = {f"Hours on {day}": "\n".join("{}: {} to {}".format(meal, *hours[meal])
                                                           for meal in unit_menu[day] if meal != "Daily Offerings")}
                except KeyError:
                    # NetNutrition added a non-existent meal for some reason
                    fields = {f"Hours on {day}": "Unavailable due to a NetNutrition error.\n"
                                                 "Check the website for current operating hours."}
            else:
                if "Closed" in hours:
                    fields = {f"Hours on {day}": "CLOSED"}
                else:
                    fields = {f"Hours on {day}": "{} to {}".format(*hours["Open"])}

            embed = self.generate_embed(title=unit, url=menu.url, color=0x4A90E2, fields=fields)
            await ctx.send(embed=embed)

    def hours_list(self):
        embed = self.generate_embed(title="On-Campus Dining Locations", url=menu.url, color=DEFAULT_COLOR,
                                    fields=reader(f"{_dir}/hours_list"), inline=True)
        embed.add_field(name="Additional Arguments",
                        value="Arguments can be specified with different separators\ne.g. `local_java`\n"
                              "To use spaces, wrap the entire name in quotes\ne.g. `\"commons munchie\"`\n"
                              "Alternative names are also permitted\ne.g. `kitchen` for `kissam`",
                        inline=False)
        return embed

    def hours_parse(self, args):
        unit, day = None, today()

        # Args can be in any order
        for arg in args:
            arg = arg.lower().replace("'", "").translate(seps)
            try:
                # Is a unit?
                unit = self._hours_units[arg]
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
    async def hours_reset(self, *args):
        await self.reset()
