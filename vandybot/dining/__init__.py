from discord import Embed
from discord.ext import commands

from ..helper import *

_dir = "vandybot/dining"


# Errors
class MenuError(Exception):
    def __init__(self, message):
        super().__init__(message)


class MenuNotFound(MenuError):
    def __init__(self, unit, message="No menu selections at {} could be found for the requested meal."):
        super().__init__(message.format(unit))


class UnitNotFound(MenuError):
    def __init__(self, unit, message="The dining facility of {} could not be found."):
        super().__init__(message.format(unit))


class MenuNotAvailable(MenuNotFound):
    def __init__(self, unit, message="The menu for {} is not yet available."):
        super().__init__(unit, message)


# Classes
class Meal:
    COLORS = {"Breakfast": 0xEABA38,
              "Lunch": 0xCC2537,
              "Dinner": 0x9013FE,
              "Brunch": 0xF16907,
              "Daily Offerings": 0x4A90E2}
    DEFAULT = "Daily Offerings"

    # Availability types
    ITEMS_NOT_FOUND = 0
    ITEMS_NOT_LISTED = 1
    ITEMS_AVAILABLE = 2
    HOURS_NOT_FOUND = 0
    CLOSED = 1
    HOURS_AVAILABLE = 2

    def __init__(self, name, day):
        self.name = name
        self.oid = 0
        self.color = self.COLORS.get(self.name, DEFAULT_COLOR)
        self.day = day

        self.opens = Time.MAX
        self.closes = Time.MAX
        self.hours_status = self.HOURS_NOT_FOUND

        self.items = {}
        self.items_status = self.ITEMS_NOT_FOUND

    def __str__(self):
        if self.day == today():
            return f"{self.name} Today"
        elif self.day == tomorrow():
            return f"{self.name} Tomorrow"
        else:
            return f"{self.name} on {self.day}"

    @property
    def status(self):
        if self.hours_status == self.HOURS_AVAILABLE and self.items_status != self.ITEMS_NOT_FOUND:
            if datetime.datetime.now().time() < self.opens and self.day == today() or \
                    datetime.datetime.now().time() > self.opens and self.day == tomorrow():
                return f"CLOSED until {self.opens}"
            elif datetime.datetime.now().time() > self.closes and self.day == today():
                return f"CLOSED since {self.closes}"
            elif self.opens <= datetime.datetime.now().time() <= self.closes and self.day == today():
                return f"OPEN until {self.closes}"
            else:
                return f"OPENS at {self.opens}"
        elif self.hours_status == self.HOURS_NOT_FOUND and self.items_status != self.ITEMS_NOT_FOUND:
            # This one shouldn't happen often
            if self.day == today():
                return "OPEN today"
            elif self.day == tomorrow():
                return "OPEN tomorrow"
            else:
                return f"OPEN on {self.day}"
        elif self.hours_status == self.CLOSED:
            # This one shouldn't happen often
            if self.day == today():
                return "CLOSED today"
            elif self.day == tomorrow():
                return "CLOSED tomorrow"
            else:
                return f"CLOSED on {self.day}"
        else:
            # This one shouldn't happen ever
            return "Unavailable"


# Main Cog
class Dining(commands.Cog):
    # URL stuff
    FOOD_TRUCK_URL = "https://campusdining.vanderbilt.edu/food-trucks/food-truck-menus/"
    MENU_URL = "https://netnutrition.cbord.com/nn-prod/vucampusdining"
    MENU_HEADER = {"Referer": MENU_URL}

    SCHEDULE = [Time("3:00 AM")]
    RETRY_DELAY = 300
    MAX_RETRIES = 6

    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

        self._units = reader(f"{_dir}/units")
        self._unit_oids = reader(f"{_dir}/unit_oids")

        self._food_trucks = reader(f"{_dir}/food_trucks")
        self._meals = reader(f"{_dir}/meals")

        self._list = reader(f"{_dir}/list")

        self._menu = {}
        self._retries = 0
        self._last_fetch = datetime.datetime.now()

    @staticmethod
    def generate_embed(title, url, color, fields, inline=False, max_len=256):
        embed = Embed(title=title, url=url, color=color)
        embed.set_thumbnail(url=f"{GITHUB_RAW}/{_dir}/thumbnail.jpg")
        for header, text in fields.items():
            if len(text) > max_len:
                splitter = text[:max_len].rfind(", ")
                text = text[:splitter] + ", ..."
            embed.add_field(name=header, value=text, inline=inline)

        return embed

    def find_next_meal(self, unit, start, name=None, relaxed=False):
        permitted = [Meal.ITEMS_AVAILABLE]
        if relaxed:
            # Second pass in case NetNutrition is truly delirious
            permitted.append([Meal.ITEMS_NOT_LISTED])

        day = start
        if day == today():
            options = list(self._menu[unit][day].values()) if name is None else [self._menu[unit][day][name]]
            next_meal = first(meal for meal in sorted(options, key=lambda meal: meal.closes)
                              if meal.items_status in permitted and meal.closes > datetime.datetime.now().time())
            if next_meal is not None:
                return next_meal
            day += 1

        while day != today():
            options = list(self._menu[unit][day].values()) if name is None else [self._menu[unit][day][name]]
            next_meal = first(meal for meal in sorted(options, key=lambda meal: meal.opens)
                              if meal.items_status in permitted)
            if next_meal is not None:
                return next_meal
            day += 1

        if not relaxed:
            return self.find_next_meal(unit, start, name=name, relaxed=True)

        # No one's around to help
        raise MenuNotFound(unit) from None

    async def get_cookie(self, default=""):
        cookies = {"CBORD.netnutrition2": "NNexternalID=vucampusdining",
                   "ASP.NET_SessionId": default}
        async with self._session.get(self.MENU_URL, params={"Access-Control-Allow-Credentials": "true"}) as response:
            if response.status != 200:
                raise aiohttp.ClientConnectionError(f"Could not fetch cookie from {self.MENU_URL}.") from None

            try:
                cookies["ASP.NET_SessionId"] = response.cookies["ASP.NET_SessionId"].coded_value
            except KeyError:
                pass

            # Make new session with session cookie
            if cookies["ASP.NET_SessionId"]:
                await self._session.close()
                self._session = aiohttp.ClientSession(cookies=cookies)

    async def get_food_truck_menu(self, unit):
        response = await fetch(self._session, self.FOOD_TRUCK_URL)
        soup = BeautifulSoup(response, "html.parser")
        food_trucks = {food_truck.get_text(): food_truck.find("a") for food_truck in soup.find_all("h4")}

        # Food trucks are special
        try:
            menu = food_trucks[unit]
            if menu is None:
                raise MenuNotAvailable(unit) from None
            return menu["href"]
        except KeyError:
            raise UnitNotFound(unit) from None

    async def get_items(self, meal):
        response = await post(self._session, f"{self.MENU_URL}/Menu/SelectMenu",
                              data={"menuOid": meal.oid},
                              headers=self.MENU_HEADER)
        soup = BeautifulSoup(response, "html.parser")
        items = {}

        # I don't think this default is ever used but just in case
        current_item = "General Items"
        for item in soup.find_all(class_=lambda c: c in ["cbo_nn_itemHover", "cbo_nn_itemGroupRow"]):
            if item["class"][0] == "cbo_nn_itemGroupRow":
                current_item = item.get_text()
                if current_item == "None":
                    # Sometimes headers just aren't labeled and it makes me sad
                    current_item = meal.name
            else:
                items.update({current_item: items.get(current_item, []) + [item.get_text()]})

        return OrderedDict(sorted(items.items()))

    async def get_menu(self):
        # Create blank menu
        menu = {unit: OrderedDict() for unit in self._units.values()}
        await self.get_cookie()

        # Go through the units
        try:
            for unit in set(self._units.values()):
                menu[unit] = await self.get_unit_menu(unit)

            # Success check
            if not self._menu or menu:
                self._menu = menu
                self._retries = 0
                self._last_fetch = datetime.datetime.now()

                # Schedule the next fetch
                self._bot.loop.create_task(schedule(self.get_menu, self.SCHEDULE))
                return

        except aiohttp.ClientConnectionError:
            # Need to restart the fetch
            pass

        # Fetch failed for some reason
        if self._retries < self.MAX_RETRIES:
            await asyncio.sleep(self.RETRY_DELAY)
            self._retries += 1
            await self.get_menu()

    async def get_unit_menu(self, unit):
        unit_oid = self._unit_oids[unit]
        unit_menu = OrderedDict([(Day(day), OrderedDict([(meal, Meal(meal, day))
                                                         for meal in self._meals.values()]))
                                 for day in Day.DAYS[:7]])

        response = await post(self._session, f"{self.MENU_URL}/Unit/SelectUnitFromUnitsList",
                              data={"unitOid": unit_oid},
                              headers=self.MENU_HEADER)
        soup = BeautifulSoup(response, "html.parser")
        blocks = soup.find_all(class_="card-block")

        # Menu without times
        try:
            for day_soup in blocks:
                day = Day(day_soup.find("header").get_text().split(",")[0])
                for meal_soup in day_soup.find_all(class_="cbo_nn_menuLinkCell pr-3 pb-3"):
                    meal = Meal(meal_soup.get_text(), day)
                    meal.oid = find_oid(meal_soup)
                    meal.items = await self.get_items(meal)
                    meal.items_status = Meal.ITEMS_AVAILABLE if meal.items else Meal.ITEMS_NOT_LISTED
                    unit_menu[day][meal.name] = meal

            # Get the times
            response = await post(self._session, f"{self.MENU_URL}/Unit/GetHoursOfOperationMarkup",
                                  data={"unitOid": unit_oid},
                                  headers=self.MENU_HEADER)
            soup = BeautifulSoup(response, "html.parser")
            unit_hours = {Day(day): [] for day in Day.DAYS[:7]}

            # This default should never be used but just in case
            day = Day("Monday")
            for block in map(BeautifulSoup.get_text, soup.find_all("td")):
                try:
                    # Is a day
                    day = Day(block)
                    unit_hours[day].append([])
                except ValueError:
                    try:
                        # Is a time
                        unit_hours[day][-1].append(Time(block))
                    except ValueError:
                        # Is a closed
                        unit_hours[day][-1].append(block)

            # Match the times
            for day in unit_menu:
                meals = unit_menu[day]
                need_hours = [meal for name, meal in meals.items()
                              if meal.items_status != Meal.ITEMS_NOT_FOUND and meal.name != Meal.DEFAULT]
                need_hours = need_hours if need_hours else [unit_menu[day][Meal.DEFAULT]]

                hour_index = 0
                hour_max = len(unit_hours[day])
                for meal in need_hours:
                    if len(need_hours) <= hour_max or \
                            len(need_hours) > hour_max and meal.items_status == Meal.ITEMS_AVAILABLE:
                        # There are enough hours to go around
                        try:
                            meal.opens, meal.closes = unit_hours[day][hour_index][:2]
                            meal.hours_status = Meal.HOURS_AVAILABLE
                            hour_index += 1
                        except ValueError:
                            # Is a closed
                            meal.hours_status = Meal.CLOSED

                    if hour_index >= hour_max:
                        break

                # Set Daily Offerings hours
                if need_hours:
                    default = unit_menu[day][Meal.DEFAULT]
                    default.opens = min(meal.opens for meal in need_hours)
                    default.closes = max(meal.closes for meal in need_hours)

        except AttributeError:
            # No menus are available
            pass

        await self.reset()
        return unit_menu

    async def startup(self):
        await self.get_menu()

    async def reset(self):
        # Because POST requests are bad and should feel bad
        await self._session.post(self.MENU_URL + "/Home/ResetSelections", headers=self.MENU_HEADER)

    @commands.command(name="menu",
                      brief="Gets menus from on-campus dining locations.",
                      help="Retrieves the menu for a given date and meal from on-campus dining locations. "
                           "Arguments can be specified in any order.\n"
                           "Multiple arguments can be provided so long as the total return "
                           f"does not exceed {MAX_RETURNS} menus.",
                      usage="[location] [day=today] [meal=next]\n"
                            "~menu [location] [day] [meal=all]\n"
                            "~menu list")
    async def menu(self, ctx, *args):
        if args and args[0] == "list":
            await ctx.send(embed=self.menu_list)
        else:
            units, days, meals = self.menu_parse(args)

            for unit in units:
                # Food trucks are special
                if unit in self._food_trucks.values():
                    menu_img = await self.get_food_truck_menu(unit)
                    embed = Embed(title=unit, url=self.FOOD_TRUCK_URL, color=0x7ED321)
                    embed.set_image(url=menu_img)
                    embed.set_footer(text="Food trucks are available on campus on a rotating schedule")
                    await ctx.send(embed=embed)
                else:
                    for day in days:
                        if "all" in meals:
                            meals = [name for name, meal in self._menu[unit][day]
                                     if meal.items_status == Meal.ITEMS_AVAILABLE]

                        for meal in meals:
                            if meal == "next":
                                meal = self.find_next_meal(unit, day)
                            else:
                                meal = self._menu[unit][day][meal]

                            if meal.items_status == Meal.ITEMS_NOT_FOUND:
                                # Find next instance of that meal if possible
                                meal = self.find_next_meal(unit, day, meal.name)

                            embed = self.menu_dispatch(unit, meal)
                            await ctx.send(embed=embed)

    def menu_dispatch(self, unit, meal):
        if meal.items_status == Meal.ITEMS_NOT_LISTED:
            items = {"No Items Listed": "Please try again later."}
        else:
            items = meal.items

        fields = OrderedDict({str(meal): meal.status})
        fields.update({header: ", ".join(text) for header, text in items.items()})
        embed = self.generate_embed(title=unit, url=self.MENU_URL, color=meal.color, fields=fields)
        embed.set_footer(text=self._last_fetch.strftime("Last updated on %b %d at %I:%M %p"))

        return embed

    @property
    def menu_list(self):
        embed = self.generate_embed(title="On-Campus Dining Locations", url=self.MENU_URL, color=DEFAULT_COLOR,
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
            arg = arg.lower().replace("'", "").translate(SEPS)
            try:
                # Is a unit?
                units.append(self._units[arg])
                continue
            except KeyError:
                pass

            try:
                # Is a food truck?
                units.append(self._food_trucks[arg])
                continue
            except KeyError:
                pass

            try:
                # Is a meal?
                if arg in ["all", "next"]:
                    meals = [arg]
                elif meals != ["all"]:
                    meals.append(self._meals[arg])
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

        if len(units) * len(days) * len(meals) > MAX_RETURNS:
            raise TooManySelections from None

        return units, days, meals
