from ..helper import *

dining_url = "https://netnutrition.cbord.com/nn-prod/vucampusdining"
dining_header = {"Referer": dining_url}

library_url = "https://www.library.vanderbilt.edu/hours.php"

post_office_url = "https://www.vanderbilt.edu/mailservices/contact-us/locations-hours-services.php"

nil = datetime.time(0, 0)


class HoursError(Exception):
    def __init__(self, message):
        super().__init__(message)


class HoursNotFound(HoursError):
    def __init__(self, unit, message="The operating hours at {} could not be found."):
        super().__init__(message.format(unit))


class UnitNotFound(HoursError):
    def __init__(self, message="The requested facility could not be found or is not available."):
        super().__init__(message)


async def dining_hours(session, unit_oid):
    response = await post(session, f"{dining_url}/Unit/GetHoursOfOperationMarkup",
                          data={"unitOid": unit_oid},
                          headers=dining_header)
    soup = BeautifulSoup(response, "html.parser")
    blocks = [Day(time) if Day().is_day(time) else time for time in map(BeautifulSoup.get_text, soup.find_all("td"))]
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

    return hours, "Some facilities may be open to students between meal-serving periods."


async def dining_unit_oid(session, unit):
    response = await fetch(session, dining_url)
    soup = BeautifulSoup(response, "html.parser")
    units = {unit.get_text(): get_oid(unit) for unit in soup.find_all(class_="d-flex flex-wrap col-9 p-0")}
    try:
        return units[unit]
    except KeyError:
        raise UnitNotFound from None


def to_time(time):
    hour = time[:-2] + (":00" if ":" not in time else "")
    period = time[-2:].upper()
    return Time(hour + " " + period)


async def library_hours(session, library):
    response = await fetch(session, library_url)
    soup = BeautifulSoup(response, "html.parser")

    blocks = soup.find_all("table", class_="table hours-table")
    footers = {block.find("th").get_text(): block.find("td").get_text().split("  ")[0] for block in blocks}
    hours = {block.find("th").get_text(): {
        Day(day.get_text().strip()[:3]): [tuple(to_time(span) for span in time.get_text().strip().split("-"))]
        if time.get_text().strip().lower() != "closed" else ["Closed"]
        for day, time in zip(block.find_all("th")[1:], block.find_all("td")[1:])}
        for block in blocks}

    return hours[library], footers[library]
