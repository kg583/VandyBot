from ..helper import *

url = "https://www.vanderbilt.edu/coronavirus/covid19dashboard/"


async def get_data(session):
    response = await fetch(session, url)
    soup = BeautifulSoup(response, "html.parser")
    rows = soup.find("table").find_all("tr")
    entries = [[entry.get_text() for entry in row.find_all("td")] for row in rows][1:][::-1]

    # Calculate total
    total = ["TOTAL", sum_column(entries, 1), sum_column(entries, 2)]
    total.append(f"{100 * total[2] / total[1]:.2f}%")
    total = list(map(bold, [total[0], f"{total[1]:,}", f"{total[2]:,}", str(total[3])]))
    entries.append(total)

    return [[entry[0], f"{entry[2]}/{entry[1]}", entry[3]] for entry in entries]


def sum_column(entries, column):
    return sum(int(entry[column].replace(",", "")) for entry in entries)
