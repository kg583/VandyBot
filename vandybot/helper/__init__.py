import aiohttp
from bs4 import BeautifulSoup
import datetime

# A nice grey
DEFAULT_COLOR = 0x9B9B9B

# GitHub directory
github_raw = "https://raw.githubusercontent.com/kg583/VandyBot/master"
github_url = "https://github.com/kg583/VandyBot"

# Max returns in a single command
max_returns = 5

# Replace common separators with '-'
seps = str.maketrans({" ": "-",
                      "_": "-"})


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


def first(iterable):
    try:
        return next(iter(iterable))
    except StopIteration:
        return None


def get_oid(element):
    return element.find("a")["onclick"].split("(")[1][:-2]


async def jfetch(session, url, params=None):
    async with session.get(url, params=params) as response:
        if response.status != 200:
            raise aiohttp.ClientConnectionError(f"Could not fetch from {url}.") from None
        return await response.json()


def parameterize(name, iterable):
    params = {}
    for index, item in enumerate(iterable):
        params.update({f"{name}[{index}]": item})
    return params


async def post(session, url, data=None, headers=None):
    async with session.post(url, data=data, headers=headers) as response:
        if response.status != 200:
            raise aiohttp.ClientConnectionError(f"Could not fetch from {url}.") from None
        text = await response.text()
        return text.encode().decode("unicode-escape")


def reader(filename):
    entries = {}
    with open(f"{filename}.txt") as file:
        for line in file.readlines():
            # key: value
            entry = line.rstrip("\n").encode().decode("unicode_escape").split(": ")
            entries.update({entry[0]: entry[1]})
    return entries


class TooManySelections(Exception):
    def __init__(self, max_count=max_returns, message="You have requested more than {} selections in one command.\n"
                                                      "Please separate your requests and try again."):
        super().__init__(message.format(max_count))


class Day:
    def __init__(self, day="Sunday"):
        day = day.capitalize()
        self._days = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
                      "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

        try:
            self._day = self._days.index(day) % 7
        except ValueError:
            raise ValueError(f"{day} is not a valid day of the week.") from None

    def __hash__(self):
        return self._day

    def __int__(self):
        return self._day

    def __str__(self):
        return self._days[self._day]

    @property
    def day(self):
        return str(self)

    def is_day(self, day):
        return day in self._days

    def __eq__(self, other):
        return int(self) == int(other)

    def __ne__(self, other):
        return int(self) != int(other)

    def __add__(self, other):
        return Day(self._days[(self._day + int(other)) % 7])

    def __iadd__(self, other):
        self._day += int(other)
        self._day %= 7

    def __sub__(self, other):
        return Day(self._days[(self._day - int(other)) % 7])

    def __isub__(self, other):
        self._day -= int(other)
        self._day %= 7


def today():
    return Day(datetime.datetime.today().strftime("%A"))


def tomorrow():
    return today() + 1


weekend = (Day("Saturday"), Day("Sunday"))


class Time(datetime.time):
    def __new__(cls, time="12:00 AM"):
        split = time.split(":")
        return super().__new__(cls, (int(split[0]) % 12) + 12 * (time.split()[1].upper() == "PM"),
                               int(split[1].split()[0]))

    def __str__(self):
        return "{}:{} {}".format(self.hour % 12 + 12 * (self.hour % 12 == 0),
                                 str(self.minute).zfill(2),
                                 "AM" if self.hour < 12 else "PM")


now = datetime.datetime.today
