import aiohttp
import asyncio
import copy
import datetime
import pickle

from bs4 import BeautifulSoup
from discord import Activity, ActivityType

# A nice grey
DEFAULT_COLOR = 0x9B9B9B
DEFAULT_TEXT = "Type ~help for usage!"

# GitHub directory
GITHUB_RAW = "https://raw.githubusercontent.com/kg583/VandyBot/master"
GITHUB_URL = "https://github.com/kg583/VandyBot"

# Max returns in a single command
MAX_RETURNS = 5

# Replace common separators with '-'
SEPS = str.maketrans({
                         " ": "-",
                         "_": "-"
                     })


# Markdown functions
def bold(string):
    return f"**{string}**"


def italics(string):
    return f"*{string}*"


def strikethrough(string):
    return f"~~{string}~~"


def underline(string):
    return f"__{string}__"


def code(string):
    return f"`{string}`"


async def fetch(session, url, params=None):
    async with session.get(url, params=params) as response:
        if response.status != 200:
            raise aiohttp.ClientConnectionError(f"Could not fetch from {url}.") from None
        text = await response.text()
        return text.encode().decode("unicode-escape")


def find_oid(element):
    return element.find("a")["onclick"].split("(")[1][:-2]


def first(iterable):
    try:
        return next(iter(iterable))
    except StopIteration:
        return None


def hours_reader(filename):
    return {Day(day): [tuple(map(Time, time.split(" - ")))]
            if " - " in time else ["Closed"]
            for day, time in reader(filename).items()}


async def jfetch(session, url, params=None):
    async with session.get(url, params=params) as response:
        if response.status != 200:
            raise aiohttp.ClientConnectionError(f"Could not fetch from {url}.") from None
        return await response.json()


def joiner(words):
    if len(words) > 2:
        return ", ".join(words[:-1]) + ", and " + str(words[-1])
    elif len(words) == 2:
        return " and ".join(words)
    elif len(words) == 1:
        return words[0]
    else:
        return ""


def parameterize(name, iterable):
    params = {}
    for index, item in enumerate(iterable):
        params.update({f"{name}[{index}]": item})
    return params


async def post(session, url, data=None, headers=None):
    async with session.post(url, data=data, headers=headers) as response:
        if response.status != 200:
            raise aiohttp.ClientConnectionError(f"Could not post to {url}.") from None
        text = await response.text()
        return text.encode().decode("unicode-escape")


def presence(text):
    return Activity(type=ActivityType.playing, name=text)


def reader(filename):
    entries = {}
    with open(f"{filename}.txt") as file:
        for line in file.readlines():
            # key: value
            entry = line.rstrip("\n").encode().decode("unicode_escape").split(": ")
            entries.update({entry[0]: entry[1]})
    return entries


def reduce(arg, mode="dining"):
    removals = {"dining": ["cafe", "center", "dining", "hall"]}
    arg = arg.lower().replace("'", "").translate(SEPS)
    for removal in removals[mode]:
        arg = arg.replace(removal, "")

    return arg


async def schedule(coro, times):
    times = [time_on(datetime.datetime.now(), time) for time in times]
    times.append(times[0] + datetime.timedelta(days=1))
    times_until = [time - datetime.datetime.now() for time in times]
    await asyncio.sleep(min(time_until for time_until in times_until if time_until.days >= 0).seconds)
    await coro()


def time_on(date, time):
    return datetime.datetime(*date.timetuple()[:3], time.hour, time.minute, time.second)


def to_time(time):
    hour = time[:-2] + (":00" if ":" not in time else "")
    period = time[-2:].upper()
    return Time(hour + " " + period)


# Slugs are lame
UNIT_NAMES = reader(f"vandybot/helper/dining")


def unit_name(unit):
    return UNIT_NAMES.get(unit, unit)


class TooManySelections(Exception):
    def __init__(self, max_count=MAX_RETURNS, message="You have requested more than {} selections in one command.\n"
                                                      "Please separate your requests and try again."):
        super().__init__(message.format(max_count))


class Day:
    DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
            "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat",
            "U", "M", "T", "W", "R", "F", "S")

    def __init__(self, day="Sunday"):
        day = day.capitalize()

        try:
            self.day = self.DAYS.index(day) % 7
        except ValueError:
            raise ValueError(f"{day} is not a valid day of the week.") from None

    def __hash__(self):
        return self.day

    def __int__(self):
        return self.day

    def __str__(self):
        return self.DAYS[self.day]

    def __copy__(self):
        return Day(self.DAYS[self.day])

    def __lt__(self, other):
        try:
            return self.relative_day < other.relative_day
        except AttributeError:
            return False

    def __le__(self, other):
        return self < other or self == other

    def __eq__(self, other):
        try:
            return int(self) == int(other)
        except ValueError:
            return False

    def __ge__(self, other):
        return self > other or self == other

    def __gt__(self, other):
        try:
            return self.relative_day > other.relative_day
        except AttributeError:
            return False

    def __add__(self, other):
        return Day(self.DAYS[(self.day + int(other)) % 7])

    def __iadd__(self, other):
        self.day += int(other)
        self.day %= 7
        return self

    def __sub__(self, other):
        return Day(self.DAYS[(self.day - int(other)) % 7])

    def __isub__(self, other):
        self.day -= int(other)
        self.day %= 7
        return self

    @property
    def is_today(self):
        return self == today()

    @property
    def is_tomorrow(self):
        return self == tomorrow()

    @property
    def relative_day(self):
        return (self.day - int(datetime.datetime.now().strftime("%w"))) % 7


now = datetime.datetime.now


def today():
    return Day(datetime.datetime.now().strftime("%A"))


def tomorrow():
    return today() + 1


week = tuple(map(Day, Day.DAYS[:7]))
weekend = (Day("Saturday"), Day("Sunday"))


class Time(datetime.time):
    MIN = datetime.time(0, 0)
    MAX = datetime.time(23, 59)

    def __new__(cls, time="12:00 AM"):
        split = time.split(":")
        return super().__new__(cls, (int(split[0]) % 12) + 12 * (time.split()[1].upper() == "PM"),
                               int(split[1].split()[0]))

    def __str__(self):
        return "{}:{} {}".format(self.hour % 12 + 12 * (self.hour % 12 == 0),
                                 str(self.minute).zfill(2),
                                 "AM" if self.hour < 12 else "PM")
