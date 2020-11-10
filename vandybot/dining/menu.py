from ..helper import *

food_truck_url = "https://campusdining.vanderbilt.edu/food-trucks/food-truck-menus/"
url = "https://netnutrition.cbord.com/nn-prod/vucampusdining"
header = {"Referer": url}

nil = datetime.time(0, 0)


class MenuError(Exception):
    def __init__(self, message):
        super().__init__(message)


class MenuNotFound(MenuError):
    def __init__(self, unit, message="No menu selections at {} could be found for the requested meal."):
        super().__init__(message.format(unit))


class UnitNotFound(MenuError):
    def __init__(self, message="The requested facility could not be found."):
        super().__init__(message)


class MenuNotAvailable(MenuNotFound):
    def __init__(self, unit, message="The menu for {} is not yet available."):
        super().__init__(unit, message)


async def food_truck_menu(session, unit):
    response = await fetch(session, food_truck_url)
    soup = BeautifulSoup(response, "html.parser")
    food_trucks = {food_truck.get_text(): food_truck.find("a") for food_truck in soup.find_all("h4")}

    # Food trucks are special
    try:
        menu = food_trucks[unit]
        if menu is None:
            raise MenuNotAvailable(unit) from None
        return menu["href"]
    except KeyError:
        raise UnitNotFound from None


async def get_hours(session, unit_oid, menu):
    response = await post(session, f"{url}/Unit/GetHoursOfOperationMarkup",
                          data={"unitOid": unit_oid},
                          headers=header)
    soup = BeautifulSoup(response, "html.parser")
    blocks = [Day(time) if Day().is_day(time) else time for time in map(BeautifulSoup.get_text, soup.find_all("td"))]
    index, counters = 0, {}
    hours = {}

    # Assign time blocks to meals
    while index < len(blocks):
        day = blocks[index]
        # Block elements are either Days or times
        if isinstance(day, Day):
            # Just in case days don't appear in order
            counters[day] = counters.get(day, -1) + 1

            if day in menu:
                # Map times to Times
                begin, end = Time(blocks[index + 1]), Time(blocks[index + 2])
                meal = list(menu[day].keys())[counters[day]]

                # Empty menus are usually weekend breakfast
                if day.day in ("Saturday", "Sunday") and meal == "Breakfast":
                    counters[day] += 1
                    meal = "Brunch"

                if day in hours:
                    hours[day].update({meal: (begin, end)})
                else:
                    hours.update({day: {meal: (begin, end)}})

                # Daily Offering hours span the day
                if "Daily Offerings" in hours[day]:
                    hours[day].update({"Daily Offerings": (min(begin, hours[day]["Daily Offerings"][0]),
                                                           max(hours[day]["Daily Offerings"][1], end))})
                else:
                    hours[day].update({"Daily Offerings": (begin, end)})

                index += 1

            elif blocks[index + 1] == "Closed":
                # This whole section could be one itertools block if not for closures
                hours.update({day: {"Closed": (nil, nil)}})

        index += 1

    return hours


async def get_items(session, menu_today, meal):
    meal_oid = menu_today[meal]
    response = await post(session, f"{url}/Menu/SelectMenu",
                          data={"menuOid": meal_oid},
                          headers=header)
    soup = BeautifulSoup(response, "html.parser")
    items = {}

    # I don't think this default is ever used but just in case
    current_item = "General Items"
    for item in soup.find_all(class_=lambda c: c in ["cbo_nn_itemHover", "cbo_nn_itemGroupRow"]):
        if item["class"][0] == "cbo_nn_itemGroupRow":
            current_item = item.get_text()
            if current_item == "None":
                # Sometimes headers just aren't labeled and it makes me sad
                current_item = meal
        else:
            items.update({current_item: items.get(current_item, []) + [item.get_text()]})

    return dict(sorted(items.items()))


async def get_menu(session, unit_oid):
    response = await post(session, f"{url}/Unit/SelectUnitFromUnitsList",
                          data={"unitOid": unit_oid},
                          headers=header)
    soup = BeautifulSoup(response, "html.parser")
    return {Day(day.find("header").get_text().split(",")[0]): {meal.get_text(): get_oid(meal)
                                                               for meal in
                                                               day.find_all(class_="cbo_nn_menuLinkCell pr-3 pb-3")}
            for day in soup.find_all(class_="card-block")}


async def get_unit_oid(session, unit):
    response = await fetch(session, url)
    soup = BeautifulSoup(response, "html.parser")
    units = {unit.get_text(): get_oid(unit) for unit in soup.find_all(class_="d-flex flex-wrap col-9 p-0")}
    try:
        return units[unit]
    except KeyError:
        raise UnitNotFound from None


def next_meal(hours, day):
    if day in hours:
        meals = hours[day]
        if day == today():
            # Check for something right now
            current_meals = sorted([meal for meal in meals if meals[meal][0] <= now().time() <= meals[meal][1]],
                                   key=lambda meal: meal == "Daily Offerings")
            if not current_meals or current_meals[0] == "Daily Offerings":
                # Check for something later today
                future_meals = [meal for meal in meals if now().time() < meals[meal][0]]
                if not future_meals:
                    if "Daily Offerings" in current_meals:
                        # Daily Offerings if possible
                        return "Daily Offerings", day
                    # Otherwise look to tomorrow
                    return list(hours[day + 1].keys())[0], day + 1

                current_meals = future_meals

            return current_meals[0], day
        elif day == tomorrow() and not any(now().time() <= block[1] for block in
                                           hours[today()].values()):
            # Check for tomorrow morning if it's late
            return list(meals.keys())[0], day

    # If all else fails...
    return "all", day
