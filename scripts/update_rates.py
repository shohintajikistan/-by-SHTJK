# -*- coding: utf-8 -*-

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


NBT_BANKS_URL = "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"
NBT_OFFICIAL_URL = "https://nbt.tj/ru/kurs/kurs.php"

OUTPUT_FILE = Path("api/rates.json")

CURRENCIES = ["USD", "EUR", "RUB", "CNY"]


BANKS = [
    {
        "name": "Алиф Банк",
        "aliases": ["алиф банк", "алиф"]
    },
    {
        "name": "Амонатбанк",
        "aliases": ["амонатбанк", "амонат банк"]
    },
    {
        "name": "Банк Арванд",
        "aliases": ["банк арванд", "арванд"]
    },
    {
        "name": "Банк Эсхата",
        "aliases": ["банк эсхата", "эсхата"]
    },
    {
        "name": "ФИНКА",
        "aliases": ["финка"]
    },
    {
        "name": "Инвестиционно-Кредитный Банк Таджикистан",
        "aliases": [
            "инвестиционно-кредитный банк таджикистан",
            "инвестиционно кредитный банк таджикистан",
            "икбт"
        ]
    },
    {
        "name": "Актив Банк",
        "aliases": ["актив банк", "актив"]
    },
    {
        "name": "Хумо",
        "aliases": ["хумо"]
    },
    {
        "name": "Имон Интернешнл",
        "aliases": [
            "имон интернешнл",
            "имон"
        ]
    },
    {
        "name": "Международный банк Таджикистана",
        "aliases": [
            "международный банк таджикистана",
            "международный банк"
        ]
    },
    {
        "name": "Ориёнбанк",
        "aliases": [
            "ориёнбанк",
            "ориенбанк",
            "ориёнбонк",
            "ориенбонк"
        ]
    },
    {
        "name": "Саноатсодиротбонк",
        "aliases": [
            "саноатсодиротбонк",
            "саноат содиротбонк"
        ]
    },
    {
        "name": "Тавхидбанк",
        "aliases": [
            "тавхидбанк",
            "тавхид банк"
        ]
    },
    {
        "name": "Спитамен Банк",
        "aliases": [
            "спитамен банк",
            "спитаменбанк"
        ]
    },
    {
        "name": "Фридом Банк Таджикистан",
        "aliases": [
            "фридом банк таджикистан",
            "фридом банк",
            "фридом"
        ]
    },
    {
        "name": "Васл Банк",
        "aliases": [
            "васл банк",
            "васл"
        ]
    },
    {
        "name": "Душанбе Сити",
        "aliases": [
            "душанбе сити",
            "dushanbe city"
        ]
    }
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9"
}


def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()

    text = text.replace("ё", "е")

    text = text.replace("оао", "")
    text = text.replace("зао", "")
    text = text.replace("ооо", "")
    text = text.replace("гуп", "")
    text = text.replace("мдо", "")
    text = text.replace("ло лс", "")
    text = text.replace('"', "")
    text = text.replace("«", "")
    text = text.replace("»", "")

    text = re.sub(r"[^a-zа-я0-9]+", " ", text)

    return clean_text(text)


def parse_number(text):
    text = clean_text(text)

    if not text:
        return None

    text = text.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        value = float(match.group(0))
    except ValueError:
        return None

    if value == 0:
        return None

    return value


def request_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=40
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or response.encoding
        or "utf-8"
    )

    return response.text


def find_bank_match(actual_name):
    actual = normalize(actual_name)

    for bank in BANKS:

        for alias in bank["aliases"]:

            alias_normalized = normalize(alias)

            if alias_normalized in actual:
                return bank["name"]

    return None


def get_tables(soup):
    return soup.find_all("table")


def find_rates_table(soup):

    tables = get_tables(soup)

    best_table = None
    best_score = -1

    for table in tables:

        text = normalize(
            table.get_text(" ", strip=True)
        )

        score = 0

        if "кредитные финансовые организации" in text:
            score += 10

        if "межбанк покупка" in text:
            score += 3

        if "межбанк продажа" in text:
            score += 3

        if "наличные покупка" in text:
            score += 3

        if "наличные продажа" in text:
            score += 3

        if "безналичные покупка" in text:
            score += 2

        if "безналичные продажа" in text:
            score += 2

        if score > best_score:
            best_score = score
            best_table = table

    return best_table


def get_table_rows(table):

    rows = []

    for tr in table.find_all("tr"):

        cells = tr.find_all(["th", "td"])

        values = []

        for cell in cells:

            values.append(
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True
                    )
                )
            )

        if values:
            rows.append(values)

    return rows


def find_header_row(rows):

    for index, row in enumerate(rows):

        text = normalize(" ".join(row))

        if (
            "кредитные финансовые организации"
            in text
        ):
            return index

    return None


def parse_bank_table(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    table = find_rates_table(soup)

    if table is None:
        raise RuntimeError(
            "Таблица НБТ не найдена."
        )

    rows = get_table_rows(table)

    if not rows:
        raise RuntimeError(
            "В таблице НБТ нет строк."
        )

    header_index = find_header_row(rows)

    if header_index is None:
        raise RuntimeError(
            "Заголовок таблицы НБТ не найден."
        )

    header = rows[header_index]

    header_map = {}

    for index, value in enumerate(header):

        h = normalize(value)

        if "кредитные финансовые организации" in h:
            header_map["organization"] = index

        elif "межбанк покупка" in h:
            header_map["interbank_buy"] = index

        elif "межбанк продажа" in h:
            header_map["interbank_sell"] = index

        elif "наличные покупка" in h:
            header_map["cash_buy"] = index

        elif "наличные продажа" in h:
            header_map["cash_sell"] = index

        elif "безналичные покупка" in h:
            header_map["cashless_buy"] = index

        elif "безналичные продажа" in h:
            header_map["cashless_sell"] = index

        elif "эл кошелек покупка" in h:
            header_map["wallet_buy"] = index

        elif "эл кошелек продажа" in h:
            header_map["wallet_sell"] = index

        elif "карты покупка" in h:
            header_map["cards_buy"] = index

        elif "карты продажа" in h:
            header_map["cards_sell"] = index

        elif "нпцдп покупка" in h:
            header_map["npcdp_buy"] = index

        elif "нпцдп продажа" in h:
            header_map["npcdp_sell"] = index

        elif h == "дата":
            header_map["date"] = index

    if "organization" not in header_map:
        raise RuntimeError(
            "Колонка организации не найдена."
        )

    found = {}

    for row in rows[header_index + 1:]:

        org_index = header_map["organization"]

        if org_index >= len(row):
            continue

        source_name = row[org_index]

        if not source_name:
            continue

        bank_name = find_bank_match(
            source_name
        )

        if bank_name is None:
            continue

        found[bank_name] = {
            "bank": bank_name,
            "official_name": source_name,

            "interbank": {
                "buy": get_value(
                    row,
                    header_map,
                    "interbank_buy"
                ),
                "sell": get_value(
                    row,
                    header_map,
                    "interbank_sell"
                )
            },

            "cash": {
                "buy": get_value(
                    row,
                    header_map,
                    "cash_buy"
                ),
                "sell": get_value(
                    row,
                    header_map,
                    "cash_sell"
                )
            },

            "cashless": {
                "buy": get_value(
                    row,
                    header_map,
                    "cashless_buy"
                ),
                "sell": get_value(
                    row,
                    header_map,
                    "cashless_sell"
                )
            },

            "wallet": {
                "buy": get_value(
                    row,
                    header_map,
                    "wallet_buy"
                ),
                "sell": get_value(
                    row,
                    header_map,
                    "wallet_sell"
                )
            },

            "cards": {
                "buy": get_value(
                    row,
                    header_map,
                    "cards_buy"
                ),
                "sell": get_value(
                    row,
                    header_map,
                    "cards_sell"
                )
            },

            "npcdp": {
                "buy": get_value(
                    row,
                    header_map,
                    "npcdp_buy"
                ),
                "sell": get_value(
                    row,
                    header_map,
                    "npcdp_sell"
                )
            },

            "date": get_text_value(
                row,
                header_map,
                "date"
            )
        }

    return found


def get_value(row, mapping, key):

    index = mapping.get(key)

    if index is None:
        return None

    if index >= len(row):
        return None

    return parse_number(row[index])


def get_text_value(row, mapping, key):

    index = mapping.get(key)

    if index is None:
        return None

    if index >= len(row):
        return None

    value = clean_text(row[index])

    return value if value else None


def parse_official_rates(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    result = {}

    tables = soup.find_all("table")

    for table in tables:

        rows = get_table_rows(table)

        for row in rows:

            text = normalize(
                " ".join(row)
            )

            if "доллар сша" in text:
                value = find_last_number(row)

                if value is not None:
                    result["USD"] = value

            elif "евро" in text:
                value = find_last_number(row)

                if value is not None:
                    result["EUR"] = value

            elif "китайский юань" in text:
                value = find_last_number(row)

                if value is not None:
                    result["CNY"] = value

            elif "российский рубль" in text:
                value = find_last_number(row)

                if value is not None:
                    result["RUB"] = value

    return result


def find_last_number(row):

    for value in reversed(row):

        number = parse_number(value)

        if number is not None:
            return number

    return None


def make_final_banks(found):

    result = []

    for bank in BANKS:

        name = bank["name"]

        if name in found:

            item = found[name]

            item["available"] = True

            result.append(item)

        else:

            result.append({
                "bank": name,
                "official_name": None,

                "interbank": {
                    "buy": None,
                    "sell": None
                },

                "cash": {
                    "buy": None,
                    "sell": None
                },

                "cashless": {
                    "buy": None,
                    "sell": None
                },

                "wallet": {
                    "buy": None,
                    "sell": None
                },

                "cards": {
                    "buy": None,
                    "sell": None
                },

                "npcdp": {
                    "buy": None,
                    "sell": None
                },

                "date": None,
                "available": False
            })

    return result


def main():

    print("")
    print("=" * 60)
    print("SHTJK — UPDATE RATES")
    print("=" * 60)
    print("")

    print("1. Загружаем НБТ...")

    banks_html = request_page(
        NBT_BANKS_URL
    )

    print("   OK")

    print("2. Читаем таблицу организаций...")

    found = parse_bank_table(
        banks_html
    )

    print(
        "   Найдено:",
        len(found),
        "из",
        len(BANKS)
    )

    print("")
    print("Найденные организации:")

    for name in found:
        print("   ✓", name)

    print("")

    missing = []

    for bank in BANKS:

        if bank["name"] not in found:
            missing.append(
                bank["name"]
            )

    if missing:

        print("Не найдены на текущей странице НБТ:")

        for name in missing:
            print("   -", name)

    print("")
    print("3. Получаем официальные курсы НБТ...")

    try:

        official_html = request_page(
            NBT_OFFICIAL_URL
        )

        official = parse_official_rates(
            official_html
        )

    except Exception as error:

        print(
            "   Ошибка официального курса:",
            error
        )

        official = {}

    print(
        "   USD:",
        official.get("USD")
    )

    print(
        "   EUR:",
        official.get("EUR")
    )

    print(
        "   RUB:",
        official.get("RUB")
    )

    print(
        "   CNY:",
        official.get("CNY")
    )

    final_banks = make_final_banks(
        found
    )

    available_count = sum(
        1
        for bank in final_banks
        if bank["available"]
    )

    output = {
        "app": {
            "name":
                "Курс Валют от Банков Таджикистан by SHTJK",
            "version": "1.0"
        },

        "source": "НБТ",

        "source_url":
            NBT_BANKS_URL,

        "updated":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "currencies": CURRENCIES,

        "official": official,

        "statistics": {
            "requested": len(BANKS),
            "found": available_count,
            "missing": len(BANKS) - available_count,
            "missing_banks": missing
        },

        "banks": final_banks
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print("=" * 60)
    print("ГОТОВО")
    print("=" * 60)
    print("")
    print(
        "Файл создан:",
        OUTPUT_FILE
    )
    print(
        "Банков найдено:",
        available_count,
        "/",
        len(BANKS)
    )
    print("")


if __name__ == "__main__":
    main()