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
        self._list = reader(f"{_dir}/list")

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
    def generate_embed(title, url, color, fields, inline=False, max_len=256):
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
                        unit_menu = await menu.get_menu(self._session, unit_oid, unit)
                        unit_hours = await menu.get_hours(self._session, unit_oid, unit_menu)
                        if meals == ["next"]:
                            # Next should not error out
                            meal, day = menu.next_meal(unit_hours, day)
                            try:
                                embed = await self.menu_dispatch(unit_menu, unit_hours, unit, day, meal)
                            except menu.MenuNotAvailable:
                                embed = await self.menu_dispatch(unit_menu, unit_hours, unit, day, "all")

                            await ctx.send(embed=embed)
                        else:
                            if meals == ["all"]:
                                meals = unit_menu[day]
                            for meal in meals:
                                embed = await self.menu_dispatch(unit_menu, unit_hours, unit, day, meal)
                                await ctx.send(embed=embed)

                await self.reset()

    async def menu_dispatch(self, unit_menu, unit_hours, unit, day, meal):
        if day not in unit_menu:
            raise menu.MenuNotFound(unit) from None
        elif meal not in unit_menu[day]:
            # Quality of life parse
            meal = {"Breakfast": "Brunch", "Brunch": "Breakfast"}.get(meal, meal)

        items = await menu.get_items(self._session, unit_menu[day], unit, meal)
        if not items:
            raise menu.MenuNotAvailable(unit) from None

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

    def menu_list(self):
        embed = self.generate_embed(title="On-Campus Dining Locations", url=menu.url, color=DEFAULT_COLOR,
                                    fields=self._list, inline=True)
        embed.add_field(name="Additional Arguments",
                        value="Up to five total selections may be requested at once\ne.g. `rand ebi lunch dinner`\n"
                              "Arguments can be specified with different separators\ne.g. `local_java`\n"
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
                units.append(self._units[arg])
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
    async def menu_reset(self, *_):
        await self.reset()
