import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


NBT_URL = "https://www.nbt.tj/ru/"
OUTPUT = Path("api/rates.json")

CURRENCIES = {
    "USD": "Доллар",
    "EUR": "Евро",
    "RUB": "Рубль",
    "CNY": "Юань",
}


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def number(text):
    if text is None:
        return None

    text = clean_text(str(text))
    text = text.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except Exception:
        return None


def get_page():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
    }

    response = requests.get(
        NBT_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    response.encoding = response.apparent_encoding

    return response.text


def find_official_rates(soup):
    rates = {}

    text = soup.get_text(" ", strip=True)

    patterns = {
        "USD": r"USD\s*([0-9]+[.,][0-9]+)",
        "EUR": r"EUR\s*([0-9]+[.,][0-9]+)",
        "RUB": r"RUB\s*([0-9]+[.,][0-9]+)",
        "CNY": r"CNY\s*([0-9]+[.,][0-9]+)",
    }

    for code, pattern in patterns.items():
        match = re.search(pattern, text, re.I)

        if match:
            rates[code] = number(match.group(1))

    return rates


def find_bank_table(soup):
    """
    Ищем таблицу НБТ, содержащую курсы
    покупки/продажи финансовых организаций.
    """

    tables = soup.find_all("table")

    for table in tables:

        rows = table.find_all("tr")

        if len(rows) < 2:
            continue

        table_text = clean_text(table.get_text(" ")).lower()

        keywords = [
            "покуп",
            "прод",
            "usd",
            "eur",
            "rub",
            "cny"
        ]

        score = sum(1 for word in keywords if word in table_text)

        if score >= 3:
            return table

    return None


def parse_bank_table(table):
    banks = []

    if table is None:
        return banks

    rows = table.find_all("tr")

    for row in rows[1:]:

        cells = row.find_all(["td", "th"])

        values = [
            clean_text(cell.get_text(" "))
            for cell in cells
        ]

        values = [v for v in values if v]

        if not values:
            continue

        bank_name = values[0]

        if len(bank_name) < 2:
            continue

        lower_name = bank_name.lower()

        if any(
            x in lower_name
            for x in [
                "валют",
                "курс",
                "покуп",
                "продаж",
                "организац"
            ]
        ):
            continue

        bank = {
            "bank": bank_name,
            "USD": {
                "buy": None,
                "sell": None
            },
            "EUR": {
                "buy": None,
                "sell": None
            },
            "RUB": {
                "buy": None,
                "sell": None
            },
            "CNY": {
                "buy": None,
                "sell": None
            }
        }

        numbers = []

        for value in values[1:]:
            n = number(value)

            if n is not None:
                numbers.append(n)

        # НБТ может менять порядок колонок.
        # Сохраняем найденные значения, если структура
        # соответствует обычной схеме:
        #
        # USD buy/sell
        # EUR buy/sell
        # RUB buy/sell
        # CNY buy/sell

        if len(numbers) >= 8:

            bank["USD"]["buy"] = numbers[0]
            bank["USD"]["sell"] = numbers[1]

            bank["EUR"]["buy"] = numbers[2]
            bank["EUR"]["sell"] = numbers[3]

            bank["RUB"]["buy"] = numbers[4]
            bank["RUB"]["sell"] = numbers[5]

            bank["CNY"]["buy"] = numbers[6]
            bank["CNY"]["sell"] = numbers[7]

            banks.append(bank)

    return banks


def main():

    print("======================================")
    print(" SHTJK CURRENCY API")
    print(" Source: National Bank of Tajikistan")
    print("======================================")

    print("Downloading NBT...")

    html = get_page()

    soup = BeautifulSoup(html, "html.parser")

    print("NBT page loaded.")

    official = find_official_rates(soup)

    print("Official rates:")

    for code in CURRENCIES:

        value = official.get(code)

        print(
            f"  {code}: "
            f"{value if value is not None else 'NOT FOUND'}"
        )

    table = find_bank_table(soup)

    if table:
        print("Bank exchange-rate table found.")
        banks = parse_bank_table(table)
    else:
        print("WARNING: Bank table was not found.")
        banks = []

    print(f"Banks parsed: {len(banks)}")

    now = datetime.now(timezone.utc).isoformat()

    data = {
        "source": "НБТ",
        "source_url": NBT_URL,
        "updated": now,

        "official": {
            "USD": official.get("USD"),
            "EUR": official.get("EUR"),
            "RUB": official.get("RUB"),
            "CNY": official.get("CNY")
        },

        "banks": banks
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("--------------------------------------")
    print(f"Saved: {OUTPUT}")
    print(f"Banks: {len(banks)}")
    print("--------------------------------------")

    # ВАЖНО:
    # Если НБТ вообще не дал официальный курс
    # и банковскую таблицу, GitHub Action должен
    # завершиться ошибкой, а не записывать пустые данные.

    if not official and not banks:
        raise RuntimeError(
            "NBT data was not found. "
            "rates.json was not updated with fake data."
        )

    print("SUCCESS")


if __name__ == "__main__":
    main()