from discord import Embed
from discord.ext import commands

from ..helper import *

_dir = "vandybot/dining"


# Errors
class MenuError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class MenuNotFound(MenuError):
    def __init__(self, unit, message="No menu selections at {} could be found for the requested meal."):
        super().__init__(message.format(unit_name(unit)))


class UnitNotFound(MenuError):
    def __init__(self, unit, message="The dining facility of {} could not be found."):
        super().__init__(message.format(unit_name(unit)))


class MenuNotAvailable(MenuNotFound):
    def __init__(self, unit, message="The menu for {} is not yet available."):
        super().__init__(unit, message)


class UnitClosed(UnitNotFound):
    def __init__(self, unit, message="{} is currently closed.", reason=""):
        if reason:
            message = "{} is currently closed due to {}."
            super().__init__(unit, message.format("{}", reason))
        else:
            super().__init__(unit, message)


class Meal:
    COLORS = {
        "breakfast": 0xEABA38,
        "lunch": 0xCC2537,
        "dinner": 0x9013FE,
        "brunch": 0xF16907,
        "daily-offerings": 0x4A90E2
    }
    ORDER = ["breakfast", "brunch", "lunch", "dinner", "daily-offerings"]
    DEFAULT = "daily-offerings"

    # Fake enum
    ITEMS_NOT_FOUND = 0
    ITEMS_NOT_LISTED = 1
    ITEMS_AVAILABLE = 2

    HOURS_NOT_FOUND = 0
    CLOSED = 1
    HOURS_AVAILABLE = 2

    def __init__(self, slug: str, day: Day):
        self.slug = slug
        self.name = " ".join(map(str.capitalize, slug.split("-")))
        self.color = self.COLORS.get(self.slug, DEFAULT_COLOR)
        self.day = day

        self.opens = Time.MAX
        self.closes = Time.MAX
        self.hours_status = self.HOURS_NOT_FOUND

        self.items = {}
        self.items_status = self.ITEMS_NOT_FOUND

    def __lt__(self, other):
        return self.ORDER.index(self.slug) < self.ORDER.index(other.slug)

    def __str__(self):
        if self.day.is_today:
            return f"{self.name} Today"
        elif self.day.is_tomorrow:
            return f"{self.name} Tomorrow"
        else:
            return f"{self.name} on {self.day}"

    @property
    def status(self):
        text = "Unavailable"
        if self.hours_status == self.HOURS_AVAILABLE and self.items_status != self.ITEMS_NOT_FOUND:
            if now().time() < self.opens and self.day.is_today or \
                    now().time() > self.opens and self.day.is_tomorrow:
                text = f"CLOSED until {self.opens}"
            elif now().time() > self.closes and self.day.is_today:
                text = f"CLOSED since {self.closes}"
            elif self.opens <= now().time() <= self.closes and self.day.is_today:
                text = f"OPEN until {self.closes}"
            else:
                text = f"OPENS at {self.opens}"
        elif self.hours_status == self.HOURS_NOT_FOUND and self.items_status != self.ITEMS_NOT_FOUND:
            # This one shouldn't happen often
            if self.day.is_today:
                text = "OPEN today"
            elif self.day.is_tomorrow:
                text = "OPEN tomorrow"
            else:
                text = f"OPEN on {self.day}"
        elif self.hours_status == self.CLOSED:
            # This one shouldn't happen ever
            if self.day.is_today:
                text = "CLOSED today"
            elif self.day.is_tomorrow:
                text = "CLOSED tomorrow"
            else:
                text = f"CLOSED on {self.day}"

        return text


class Stations:
    DEFAULT = "General Items"

    def __init__(self):
        self.names = {None: Stations.DEFAULT}
        self.items = {None: []}

    def __getitem__(self, item):
        return self.items.get(item, [])

    def __iter__(self):
        for key in self.names:
            if key is not None or self.items[key]:
                yield self.names[key], self.items[key]

    def __setitem__(self, key, value):
        if key not in self.names.keys():
            self.names.update({key: value})
        else:
            self.items.update({key: value})


# Main Cog
class Dining(commands.Cog):
    # URL stuff
    FOOD_TRUCK_URL = "https://campusdining.vanderbilt.edu/food-trucks/food-truck-menus/"
    MENU_URL = "https://vanderbilt.nutrislice.com"

    SCHEDULE = [Time("4:20 AM")]
    RETRY_DELAY = 600
    MAX_RETRIES = 3

    MIN_MENU_AGE = 80000
    MIN_SINCE = 3600

    def __init__(self, bot):
        self._bot = bot
        self._session = aiohttp.ClientSession()

        self._unit_slugs = reader(f"{_dir}/units")
        self._unit_set = set(self._unit_slugs.values())
        self._unit_conditions = reader(f"{_dir}/unit_conditions")

        self._food_trucks = reader(f"{_dir}/food_trucks")
        self._meal_slugs = reader(f"{_dir}/meals")
        self._meal_set = set(self._meal_slugs.values())

        self._list = reader(f"{_dir}/list")

        self._menu = {}
        self._retries = 0
        self._timestamp = now()

    @staticmethod
    def generate_embed(title, url, color, fields, inline=False, max_len=240):
        embed = Embed(title=title, url=url, color=color)
        embed.set_thumbnail(url=f"{GITHUB_RAW}/{_dir}/thumbnail.jpg")
        for header, text in fields.items():
            if len(text) > max_len:
                splitter = text[:max_len].rfind(", ")
                text = text[:splitter] + ", ..."
            embed.add_field(name=header, value=text, inline=inline)

        return embed

    def find_next_meal(self, unit_slug: str, start: Day, meal_slug: str = None, relaxed=False):
        permitted = [Meal.ITEMS_AVAILABLE]
        if relaxed:
            # Second pass in case NutriSlice is truly delirious
            permitted.append(Meal.ITEMS_NOT_LISTED)

        # Fake shallow copy
        day = copy.copy(start)
        if day.is_today:
            options = list(self._menu[unit_slug][day].values())\
                if meal_slug is None else [self._menu[unit_slug][day][meal_slug]]
            next_meal = first(meal for meal in sorted(options, key=lambda meal: (meal.closes, meal))
                              if meal.items_status in permitted and meal.closes > now().time())
            if next_meal is not None:
                return next_meal
            day += 1

        while not day.is_today:
            options = list(self._menu[unit_slug][day].values())\
                if meal_slug is None else [self._menu[unit_slug][day][meal_slug]]
            next_meal = first(meal for meal in sorted(options, key=lambda meal: (meal.opens, meal))
                              if meal.items_status in permitted)
            if next_meal is not None:
                return next_meal
            day += 1

        if not relaxed:
            return self.find_next_meal(unit_slug, start, meal_slug=meal_slug, relaxed=True)

        # No one's around to help
        raise MenuNotFound(unit_slug) from None

    async def get_food_truck_menu(self, unit_slug: str):
        response = await fetch(self._session, self.FOOD_TRUCK_URL)
        soup = BeautifulSoup(response, "html.parser")
        food_trucks = {food_truck.get_text(): food_truck.find("a") for food_truck in soup.find_all("h4")}

        # Food trucks are special
        try:
            menu = food_trucks[unit_slug]
            if menu is None:
                raise MenuNotAvailable(unit_slug) from None
            return menu["href"]
        except KeyError:
            raise UnitNotFound(unit_slug) from None

    @staticmethod
    def get_item_name(item: dict):
        return item["name"].replace(" - Placeholder", "").replace(" - placeholder", "")

    async def get_menu(self):
        # Create blank menu
        menu = {unit_slug:
                {day:
                 {meal_slug: Meal(meal_slug, day) for meal_slug in self._meal_set}
                 for day in week}
                for unit_slug in self._unit_set}

        # Go through the units
        try:
            for unit in await jfetch(self._session, f"{self.MENU_URL}/menu/api/schools"):
                unit_slug = unit["slug"]
                if unit_slug not in self._unit_set:
                    print(f"Missing unit option: {unit_slug}")
                    continue

                unit_menu = menu[unit_slug]
                unit_hours = await self._bot.get_cog("Hours").get_dining_hours_dispatch(unit_slug)
                for meal in unit["active_menu_types"]:
                    meal_slug = meal["slug"]
                    if meal_slug not in self._meal_set:
                        print(f"Missing meal option: {meal_slug}")

                    year, month, day, *_ = datetime.date.today().timetuple()
                    url = f"/menu/api/weeks/school/{unit_slug}/menu-type/{meal_slug}/{year}/{month}/{day}/"
                    next_url = f"/menu/api/weeks/school/{unit_slug}/menu-type/{meal_slug}/{year}/{month}/{day + 7}/"
                    in_week = False

                    for listing in (await jfetch(self._session, f"{self.MENU_URL}{url}"))["days"] +\
                                   (await jfetch(self._session, f"{self.MENU_URL}{next_url}"))["days"]:
                        day = Day(datetime.date.fromisoformat(listing["date"]).strftime("%A"))
                        if day.is_today:
                            in_week = not in_week

                        if in_week:
                            stations = Stations()

                            for item in listing["menu_items"]:
                                station_id = item["station_id"]
                                if item["is_station_header"]:
                                    stations[station_id] = item["text"]
                                else:
                                    stations[station_id] += [item["food"]]

                            current = unit_menu[day][meal_slug]
                            current.items = dict(stations)
                            if current.items:
                                current.items_status = Meal.ITEMS_AVAILABLE
                            elif listing["has_unpublished_menus"]:
                                current.items_status = Meal.ITEMS_NOT_LISTED
                            else:
                                current.items_status = Meal.ITEMS_NOT_FOUND

                for day in week:
                    need_hours = sorted([meal for meal in unit_menu[day].values() if
                                         meal.items_status != Meal.ITEMS_NOT_FOUND and
                                         meal.slug != Meal.DEFAULT])
                    need_hours = need_hours if need_hours else [unit_menu[day][Meal.DEFAULT]]

                    hour_index = 0
                    hour_max = len(unit_hours[day])
                    for current in need_hours:
                        if len(need_hours) <= hour_max or \
                                len(need_hours) > hour_max and current.items_status == Meal.ITEMS_AVAILABLE:
                            # There are enough hours to go around
                            try:
                                current.opens, current.closes = unit_hours[day][hour_index]
                                current.hours_status = Meal.HOURS_AVAILABLE
                                hour_index += 1
                            except ValueError:
                                # Is a closed
                                current.hours_status = Meal.CLOSED

                        if hour_index >= hour_max:
                            break

                    # Set Daily Offerings hours
                    if need_hours:
                        default = unit_menu[day][Meal.DEFAULT]
                        default.opens = min(meal.opens for meal in need_hours)
                        default.closes = max(meal.closes for meal in need_hours)
                        default.hours_status = Meal.HOURS_AVAILABLE

        except aiohttp.ClientConnectionError:
            # Need to restart the fetch
            print("VandyBot could not access the NutriSlice API server.")
            await self.retry()
            return

        # Success check
        if not self._menu or menu:
            self._menu = menu
            self._timestamp = now()

            self._menu["Retries"] = self._retries
            self._menu["Timestamp"] = self._timestamp
            self._retries = 0

            # Save new menu
            with open(f"{_dir}/menu.pickle", "wb") as menu_pickle:
                pickle.dump(self._menu, menu_pickle)

            # Schedule the next fetch
            self._bot.loop.create_task(schedule(self.get_menu, self.SCHEDULE))
        else:
            await self.retry()

    async def retry(self):
        # Fetch failed for some reason
        if self._retries < self.MAX_RETRIES or not self._menu:
            # Can keep trying
            print(f"Trying again in {self.RETRY_DELAY} seconds...")
            await asyncio.sleep(self.RETRY_DELAY)
            self._retries += 1
            await self.get_menu()
        elif self._retries >= self.MAX_RETRIES:
            # Give up, use the old one
            with open(f"{_dir}/menu.pickle") as menu_pickle:
                self._menu = pickle.load(menu_pickle)

            self._retries = 0
            self._timestamp = self._menu["Timestamp"]
            print(f"Retries failed. Using cached menu from {self._timestamp}.")

    async def startup(self):
        print("Starting the Dining cog...")
        await self.get_menu()

    @commands.command(name="menu",
                      brief="Gets menus from on-campus dining locations",
                      help="Retrieves the menu for a given date and meal from on-campus dining locations. "
                           "Arguments can be specified in any order.\n"
                           "Multiple arguments can be provided so long as the total return "
                           f"does not exceed {MAX_RETURNS} menus.",
                      usage="[location] [day=today] [meal=next]\n"
                            "~menu [location] [day] list\n"
                            "~menu [location] list\n"
                            "~menu list")
    async def menu(self, ctx, *args):
        unit_slugs, days, meal_slugs = self.menu_parse(args)

        for unit_slug in unit_slugs:
            if unit_slug == "list":
                # Largest listing
                embed = self.menu_list()
                await ctx.send(embed=embed)
            elif unit_slug in self._food_trucks.values():
                # Food trucks are special
                menu_img = await self.get_food_truck_menu(unit_slug)
                embed = Embed(title=unit_slug, url=self.FOOD_TRUCK_URL, color=0x7ED321)
                embed.set_image(url=menu_img)
                embed.set_footer(text="Food trucks are available on campus on a rotating schedule")
                await ctx.send(embed=embed)
            else:
                for day in days:
                    if day == "list":
                        embed = self.menu_list(unit_slug)
                        await ctx.send(embed=embed)
                    else:
                        for meal_slug in meal_slugs:
                            if meal_slug == "list":
                                embed = self.menu_list(unit_slug, day)
                            else:
                                if meal_slug == "next":
                                    meal = self.find_next_meal(unit_slug, day)
                                else:
                                    meal = self._menu[unit_slug][day][meal_slug]

                                closing = time_on(datetime.date.today(), meal.closes)
                                if meal.items_status == Meal.ITEMS_NOT_FOUND or \
                                        (now() - closing).seconds > self.MIN_SINCE:
                                    # Find next instance of that meal if possible
                                    meal = self.find_next_meal(unit_slug, day, meal.slug)

                                embed = self.menu_dispatch(unit_slug, meal)

                            await ctx.send(embed=embed)

                    await asyncio.sleep(1)

    def menu_dispatch(self, unit_slug: str, meal: Meal):
        if meal.items_status == Meal.ITEMS_NOT_LISTED:
            items = {"No Items Listed": "Please try again later."}
        else:
            items = meal.items

        fields = {underline(str(meal)): meal.status}
        fields.update({header: ", ".join(map(self.get_item_name, text)) for header, text in items.items()})
        embed = self.generate_embed(title=unit_name(unit_slug), url=self.MENU_URL, color=meal.color,
                                    fields=fields)
        embed.set_footer(text=self.menu_footer(unit_slug))

        return embed

    def menu_footer(self, unit_slug: str):
        condition = self._unit_conditions.get(unit_slug, "")
        if "Closed due to" == condition[:13]:
            raise UnitClosed(unit_slug, reason=condition[14:])
        elif condition:
            return condition
        else:
            return self._timestamp.strftime("Last updated on %b %d at %I:%M %p")

    def menu_list(self, unit_slug: str = None, day: Day = None):
        if unit_slug is None and day is None:
            # The master listing
            embed = self.generate_embed(title="On-Campus Dining Locations", url=self.MENU_URL, color=DEFAULT_COLOR,
                                        fields=self._list, inline=True)
            embed.add_field(name="Additional Arguments",
                            value="Up to five total selections may be requested at once\ne.g. `rand ebi lunch dinner`\n"
                                  "Arguments can be specified with different separators\ne.g. `local_java`\n"
                                  "To use spaces, wrap the entire name in quotes\ne.g. `\"commons munchie\"`\n"
                                  "Alternative names are also permitted\ne.g. `kitchen` for `kissam`",
                            inline=False)
        elif day is None:
            # The week's listing
            unit_menu = self._menu[unit_slug]
            fields = {underline(day):
                      "\n".join(map(lambda m: m.name, sorted(meal for name in names
                                    if (meal := unit_menu[day][name]).items_status == Meal.ITEMS_AVAILABLE)))
                      for day, names in sorted(unit_menu.items()) if any(meal.items_status == Meal.ITEMS_AVAILABLE
                                                                         for name, meal in unit_menu[day].items())}
            if not fields:
                raise MenuNotFound(unit_slug)

            embed = self.generate_embed(title=unit_name(unit_slug), url=self.MENU_URL, color=DEFAULT_COLOR,
                                        fields=fields, inline=True)
            embed.set_footer(text=self.menu_footer(unit_slug))
        else:
            # The day's listing
            fields = {str(meal): ", ".join(item for item in meal.items.keys())
                      for meal in sorted(self._menu[unit_slug][day].values())
                      if meal.items_status == Meal.ITEMS_AVAILABLE}
            if not fields:
                raise MenuNotFound(unit_slug)

            embed = self.generate_embed(title=unit_name(unit_slug), url=self.MENU_URL, color=DEFAULT_COLOR,
                                        fields=fields)
            embed.set_footer(text=self.menu_footer(unit_slug))

        return embed

    def menu_parse(self, args):
        # Dicts to remove duplicates
        unit_slugs, days, meal_slugs, listing = {}, {}, {}, False

        # Args can be in any order
        for arg in args:
            arg = self.reduce(arg)
            try:
                # Is a unit?
                unit_slugs.update({self._unit_slugs[arg]: 0})
                continue
            except KeyError:
                pass

            try:
                # Is a food truck?
                unit_slugs.update({self._food_trucks[arg]: 0})
                continue
            except KeyError:
                pass

            try:
                # Is a meal or a listing request?
                if arg == "next":
                    meal_slugs = {arg: 0}
                elif arg == "list":
                    listing = True
                else:
                    meal_slugs.update({self._meal_slugs[arg]: 0})
                continue
            except KeyError:
                pass

            # Is a day?
            if arg == "today":
                days.update({today(): 0})
            elif arg == "tomorrow":
                days.update({tomorrow(): 0})
            else:
                try:
                    days.update({Day(arg): 0})
                except ValueError:
                    raise commands.BadArgument(f"Invalid argument provided: {arg}") from None

        if not listing:
            if not unit_slugs:
                raise commands.BadArgument("No dining facility was provided.") from None
            if not days:
                days = [today()]
            if not meal_slugs:
                if days == [today()]:
                    meal_slugs = ["next"]
                else:
                    meal_slugs = ["list"]
        else:
            if not unit_slugs:
                unit_slugs = ["list"]
            elif not days:
                days = ["list"]
            elif not meal_slugs:
                meal_slugs = ["list"]

        if len(unit_slugs) * min(len(days), 1) * min(len(meal_slugs), 1) > MAX_RETURNS:
            raise TooManySelections from None

        return unit_slugs, days, meal_slugs

    @staticmethod
    def reduce(arg):
        return arg.lower().replace("'", "").translate(SEPS). \
            replace("-hall", "").replace("-center", "").replace("-dining", "")
