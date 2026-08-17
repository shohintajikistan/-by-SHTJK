# -*- coding: utf-8 -*-

"""
SHTJK — Курс Валют от Банков Таджикистан

Получает данные с официального сайта НБТ:
https://nbt.tj/ru/kurs/kurs_kommer_bank.php

Сохраняет:
api/rates.json

ВАЖНО:
- Никаких придуманных курсов.
- Если НБТ не даёт данные -> null.
- Ищем все организации из REQUIRED_ORGANIZATIONS.
- Сохраняем подробные данные НБТ.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_URL = "https://nbt.tj"
RATES_URL = "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"
OFFICIAL_URL = "https://nbt.tj/ru/kurs/kurs.php"

OUTPUT = Path("api/rates.json")


# ============================================================
# ОРГАНИЗАЦИИ, КОТОРЫЕ НУЖНЫ SHTJK
# ============================================================

REQUIRED_ORGANIZATIONS = [
    "Алиф Банк",
    "Амонатбанк",
    "Банк Арванд",
    "Банк Эсхата",
    "ФИНКА",
    "Инвестиционно-Кредитный Банк Таджикистан",
    "Актив Банк",
    "Хумо",
    "Имон Интернешнл",
    "Международный банк Таджикистана",
    "Ориёнбанк",
    "Саноатсодиротбонк",
    "Тавхидбанк",
    "Спитамен Банк",
    "Фридом Банк Таджикистан",
    "Васл Банк",
    "Душанбе Сити",
]


# ============================================================
# ВАЛЮТЫ
# ============================================================

CURRENCIES = {
    "USD": [
        "USD",
        "доллар",
        "доллар сша",
        "долл"
    ],
    "EUR": [
        "EUR",
        "евро"
    ],
    "RUB": [
        "RUB",
        "руб",
        "рубль",
        "российский рубль"
    ],
    "CNY": [
        "CNY",
        "юань",
        "китайский юань"
    ],
}


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def get(url, session):
    """
    Надёжная загрузка страницы.
    """

    last_error = None

    for attempt in range(3):

        try:

            response = session.get(
                url,
                headers=HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or response.encoding
                or "utf-8"
            )

            return response

        except Exception as exc:

            last_error = exc

            if attempt < 2:
                time.sleep(3)

    raise last_error


# ============================================================
# ТЕКСТ
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = value.replace("\xa0", " ")
    value = value.replace("\u200b", "")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_name(value):
    """
    Нормализация названия организации.
    """

    value = clean_text(value).lower()

    value = value.replace("ё", "е")

    # ОАО / ЗАО / ООО / ГУП / МДО и т.д.
    value = re.sub(
        r'\b(оао|зао|ооо|гуп|мдо|мкк|мко|пэбт|сб рт)\b',
        ' ',
        value,
    )

    value = re.sub(
        r'["«»„“”]',
        ' ',
        value,
    )

    value = re.sub(
        r'[^a-zа-я0-9]+',
        ' ',
        value,
    )

    return clean_text(value)


# ============================================================
# ЧИСЛА
# ============================================================

def parse_number(value):

    value = clean_text(value)

    if not value:
        return None

    value = value.replace(",", ".")

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        value
    )

    if not match:
        return None

    try:
        number = float(match.group(0))
    except Exception:
        return None

    # НБТ использует 0.0000 там, где операции нет.
    if number == 0:
        return None

    return number


# ============================================================
# ТАБЛИЦА НБТ
# ============================================================

def find_rate_table(soup):

    tables = soup.find_all("table")

    if not tables:
        return None

    best = None
    best_score = -1

    for table in tables:

        text = clean_text(
            table.get_text(" ", strip=True)
        ).lower()

        score = 0

        keywords = [
            "кредитные финансовые организации",
            "межбанк покупка",
            "межбанк продажа",
            "наличные покупка",
            "наличные продажа",
            "безналичные покупка",
            "безналичные продажа",
        ]

        for keyword in keywords:
            if keyword in text:
                score += 1

        if score > best_score:
            best_score = score
            best = table

    return best


# ============================================================
# ЗАГОЛОВКИ
# ============================================================

def get_headers(table):

    rows = table.find_all("tr")

    if not rows:
        return []

    for row in rows[:5]:

        cells = row.find_all(
            ["th", "td"]
        )

        headers = [
            clean_text(
                cell.get_text(
                    " ",
                    strip=True
                )
            )
            for cell in cells
        ]

        joined = " ".join(headers).lower()

        if (
            "кредитные" in joined
            and "покупка" in joined
            and "продажа" in joined
        ):
            return headers

    # fallback
    cells = rows[0].find_all(
        ["th", "td"]
    )

    return [
        clean_text(
            cell.get_text(
                " ",
                strip=True
            )
        )
        for cell in cells
    ]


# ============================================================
# КАРТА КОЛОНОК
# ============================================================

def make_column_map(headers):

    result = {}

    for index, header in enumerate(headers):

        h = normalize_name(header)

        if "кредитные финансовые организации" in h:
            result["organization"] = index

        elif "межбанк покупка" in h:
            result["interbank_buy"] = index

        elif "межбанк продажа" in h:
            result["interbank_sell"] = index

        elif "наличные покупка" in h:
            result["cash_buy"] = index

        elif "наличные продажа" in h:
            result["cash_sell"] = index

        elif "безналичные покупка" in h:
            result["cashless_buy"] = index

        elif "безналичные продажа" in h:
            result["cashless_sell"] = index

        elif "эл кошелек покупка" in h:
            result["wallet_buy"] = index

        elif "эл кошелек продажа" in h:
            result["wallet_sell"] = index

        elif "карты покупка" in h:
            result["card_buy"] = index

        elif "карты продажа" in h:
            result["card_sell"] = index

        elif "нпцдп покупка" in h:
            result["npcdp_buy"] = index

        elif "нпцдп продажа" in h:
            result["npcdp_sell"] = index

        elif h == "дата":
            result["date"] = index

    return result


# ============================================================
# СООТВЕТСТВИЕ НАЗВАНИЙ
# ============================================================

ALIASES = {

    "Алиф Банк": [
        "алиф банк",
        "алиф"
    ],

    "Амонатбанк": [
        "амонатбанк",
        "амонат банк"
    ],

    "Банк Арванд": [
        "банк арванд",
        "арванд"
    ],

    "Банк Эсхата": [
        "банк эсхата",
        "эсхата"
    ],

    "ФИНКА": [
        "финка"
    ],

    "Инвестиционно-Кредитный Банк Таджикистан": [
        "инвестиционно кредитный банк таджикистан",
        "инвестиционно кредитный банк",
        "икбт"
    ],

    "Актив Банк": [
        "актив банк",
        "актив"
    ],

    "Хумо": [
        "хумо"
    ],

    "Имон Интернешнл": [
        "имон интернешнл",
        "имон"
    ],

    "Международный банк Таджикистана": [
        "международный банк таджикистана",
        "международный банк"
    ],

    "Ориёнбанк": [
        "ориенбанк",
        "ориёнбанк",
        "ориен банк",
        "ориён банк"
    ],

    "Саноатсодиротбонк": [
        "саноатсодиротбонк",
        "саноат содиротбонк"
    ],

    "Тавхидбанк": [
        "тавхидбанк",
        "тавхид банк"
    ],

    "Спитамен Банк": [
        "спитамен банк",
        "спитаменбанк"
    ],

    "Фридом Банк Таджикистан": [
        "фридом банк таджикистан",
        "фридом банк",
        "фридом"
    ],

    "Васл Банк": [
        "васл банк",
        "васл"
    ],

    "Душанбе Сити": [
        "душанбе сити",
        "душанбе сити банк",
        "dushanbe city bank"
    ],
}


def matches_organization(actual, wanted):

    actual_norm = normalize_name(actual)

    aliases = ALIASES.get(
        wanted,
        [wanted]
    )

    for alias in aliases:

        alias_norm = normalize_name(alias)

        if not alias_norm:
            continue

        if alias_norm in actual_norm:
            return True

    return False


# ============================================================
# ИЗВЛЕЧЕНИЕ СТРАНИЦЫ ОДНОЙ ВАЛЮТЫ
# ============================================================

def parse_currency_page(
    html,
    currency
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    table = find_rate_table(soup)

    if table is None:
        raise RuntimeError(
            f"Таблица НБТ не найдена для {currency}"
        )

    headers = get_headers(table)

    column_map = make_column_map(
        headers
    )

    if "organization" not in column_map:
        raise RuntimeError(
            f"Не найдена колонка организации для {currency}"
        )

    rows = table.find_all("tr")

    result = {}

    for row in rows:

        cells = row.find_all(
            ["td", "th"]
        )

        if not cells:
            continue

        values = [
            clean_text(
                cell.get_text(
                    " ",
                    strip=True
                )
            )
            for cell in cells
        ]

        org_index = column_map["organization"]

        if org_index >= len(values):
            continue

        organization =
            values[org_index]

        if not organization:
            continue

        for wanted in REQUIRED_ORGANIZATIONS:

            if not matches_organization(
                organization,
                wanted
            ):
                continue

            item = {
                "source_name": organization,
                "currency": currency,

                "interbank": {
                    "buy": get_cell_number(
                        values,
                        column_map,
                        "interbank_buy"
                    ),
                    "sell": get_cell_number(
                        values,
                        column_map,
                        "interbank_sell"
                    ),
                },

                "cash": {
                    "buy": get_cell_number(
                        values,
                        column_map,
                        "cash_buy"
                    ),
                    "sell": get_cell_number(
                        values,
                        column_map,
                        "cash_sell"
                    ),
                },

                "cashless": {
                    "buy": get_cell_number(
                        values,
                        column_map,
                        "cashless_buy"
                    ),
                    "sell": get_cell_number(
                        values,
                        column_map,
                        "cashless_sell"
                    ),
                },

                "wallet": {
                    "buy": get_cell_number(
                        values,
                        column_map,
                        "wallet_buy"
                    ),
                    "sell": get_cell_number(
                        values,
                        column_map,
                        "wallet_sell"
                    ),
                },

                "cards": {
                    "buy": get_cell_number(
                        values,
                        column_map,
                        "card_buy"
                    ),
                    "sell": get_cell_number(
                        values,
                        column_map,
                        "card_sell"
                    ),
                },

                "npcdp": {
                    "buy": get_cell_number(
                        values,
                        column_map,
                        "npcdp_buy"
                    ),
                    "sell": get_cell_number(
                        values,
                        column_map,
                        "npcdp_sell"
                    ),
                },

                "date": get_cell_text(
                    values,
                    column_map,
                    "date"
                ),
            }

            result[wanted] = item

    return result


def get_cell_number(
    values,
    column_map,
    key
):

    index = column_map.get(key)

    if index is None:
        return None

    if index >= len(values):
        return None

    return parse_number(
        values[index]
    )


def get_cell_text(
    values,
    column_map,
    key
):

    index = column_map.get(key)

    if index is None:
        return None

    if index >= len(values):
        return None

    value = clean_text(
        values[index]
    )

    return value or None


# ============================================================
# ПОПЫТКА ПОЛУЧИТЬ ВАЛЮТУ ЧЕРЕЗ ФОРМУ НБТ
# ============================================================

def discover_currency_urls(
    soup
):

    urls = {}

    for form in soup.find_all("form"):

        selects = form.find_all("select")

        for select in selects:

            options =
                select.find_all("option")

            for option in options:

                text = clean_text(
                    option.get_text(
                        " ",
                        strip=True
                    )
                )

                value = (
                    option.get("value")
                    or ""
                )

                combined = (
                    text + " " + value
                ).lower()

                for currency, words in CURRENCIES.items():

                    for word in words:

                        if word.lower() in combined:

                            form_action = (
                                form.get("action")
                                or RATES_URL
                            )

                            full_url = urljoin(
                                RATES_URL,
                                form_action
                            )

                            urls.setdefault(
                                currency,
                                {
                                    "url": full_url,
                                    "params": {}
                                }
                            )

                            name = select.get(
                                "name"
                            )

                            if name:
                                urls[currency][
                                    "params"
                                ][name] = value

                            break

    return urls


# ============================================================
# ПОЛУЧЕНИЕ ОФИЦИАЛЬНЫХ КУРСОВ
# ============================================================

def parse_official_rates(
    html
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text =
        clean_text(
            soup.get_text(
                " ",
                strip=True
            )
        )

    result = {}

    # Ищем обычные пары вида:
    # USD ... 9.22
    # EUR ... 10.50
    #
    # Это только резервный поиск.
    # Если структура страницы НБТ изменится,
    # отсутствующие значения остаются null.

    for currency, words in CURRENCIES.items():

        for word in words:

            pattern = (
                r"\b"
                + re.escape(word)
                + r"\b"
                r".{0,150}?"
                r"(\d+\.\d+)"
            )

            match = re.search(
                pattern,
                text,
                flags=re.I
            )

            if match:

                number =
                    parse_number(
                        match.group(1)
                    )

                if number is not None:

                    result[currency] =
                        number

                    break

    return result


# ============================================================
# ОБЪЕДИНЕНИЕ
# ============================================================

def build_banks(currency_data):

    banks = {}

    for wanted in REQUIRED_ORGANIZATIONS:

        banks[wanted] = {
            "bank": wanted,
            "official_name": None,

            "USD": None,
            "EUR": None,
            "RUB": None,
            "CNY": None,

            "available": False,
        }


    for currency, data in currency_data.items():

        for bank_name, item in data.items():

            if bank_name not in banks:
                continue

            banks[bank_name][
                currency
            ] = item

            banks[bank_name][
                "official_name"
            ] = item.get(
                "source_name"
            )

            banks[bank_name][
                "available"
            ] = True


    return list(
        banks.values()
    )


# ============================================================
# СТАТИСТИКА
# ============================================================

def statistics(banks):

    available = 0

    missing = []

    for bank in banks:

        if bank.get("available"):
            available += 1
        else:
            missing.append(
                bank["bank"]
            )

    return {
        "requested": len(
            REQUIRED_ORGANIZATIONS
        ),
        "found": available,
        "missing": missing,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SHTJK — UPDATE RATES")
    print("Источник: Национальный банк Таджикистана")
    print("=" * 70)

    session = requests.Session()

    # --------------------------------------------------------
    # Главная страница
    # --------------------------------------------------------

    print("\n[1/3] Загружаем НБТ...")

    response =
        get(
            RATES_URL,
            session
        )

    print(
        "OK:",
        response.url
    )

    # --------------------------------------------------------
    # Определяем валюты
    # --------------------------------------------------------

    print("\n[2/3] Получаем USD / EUR / RUB / CNY...")

    first_soup =
        BeautifulSoup(
            response.text,
            "html.parser"
        )

    currency_urls =
        discover_currency_urls(
            first_soup
        )

    currency_data = {}

    # Всегда сначала пытаемся разобрать
    # текущую страницу как USD.
    try:

        currency_data["USD"] =
            parse_currency_page(
                response.text,
                "USD"
            )

        print(
            "USD:",
            len(
                currency_data["USD"]
            ),
            "организаций"
        )

    except Exception as exc:

        print(
            "USD ERROR:",
            exc
        )

        currency_data["USD"] = {}


    # Остальные валюты.
    for currency in [
        "EUR",
        "RUB",
        "CNY"
    ]:

        info =
            currency_urls.get(
                currency
            )

        if not info:

            print(
                currency,
                ": URL/параметры НБТ не обнаружены"
            )

            currency_data[
                currency
            ] = {}

            continue

        try:

            r =
                session.get(
                    info["url"],
                    params=info["params"],
                    headers=HEADERS,
                    timeout=30
                )

            r.raise_for_status()

            r.encoding =
                r.apparent_encoding \
                or r.encoding \
                or "utf-8"

            currency_data[
                currency
            ] =
                parse_currency_page(
                    r.text,
                    currency
                )

            print(
                currency,
                ":",
                len(
                    currency_data[
                        currency
                    ]
                ),
                "организаций"
            )

        except Exception as exc:

            print(
                currency,
                "ERROR:",
                exc
            )

            currency_data[
                currency
            ] = {}


    # --------------------------------------------------------
    # Официальные курсы
    # --------------------------------------------------------

    official = {}

    try:

        official_response =
            get(
                OFFICIAL_URL,
                session
            )

        official =
            parse_official_rates(
                official_response.text
            )

    except Exception as exc:

        print(
            "Official rates error:",
            exc
        )


    # --------------------------------------------------------
    # Формируем JSON
    # --------------------------------------------------------

    print("\n[3/3] Создаём rates.json...")

    banks =
        build_banks(
            currency_data
        )

    stats =
        statistics(
            banks
        )


    output = {

        "app": {
            "name":
                "Курс Валют от Банков Таджикистан by SHTJK",
            "version":
                "3.0"
        },

        "source": "НБТ",

        "source_url":
            RATES_URL,

        "updated":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "currency_pages": {
            currency:
                len(
                    currency_data.get(
                        currency,
                        {}
                    )
                )
            for currency in CURRENCIES
        },

        "statistics": stats,

        "official": official,

        "currencies": [
            "USD",
            "EUR",
            "RUB",
            "CNY"
        ],

        "banks": banks,

    }


    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with OUTPUT.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )


    # --------------------------------------------------------
    # Результат
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        "Запрошено:",
        stats["requested"]
    )

    print(
        "Найдено:",
        stats["found"]
    )

    print(
        "Не найдено:",
        len(
            stats["missing"]
        )
    )


    if stats["missing"]:

        print("\nНе найдены НБТ:")

        for name in stats["missing"]:
            print(
                " -",
                name
            )


    print(
        "\nФайл:",
        OUTPUT
    )


if __name__ == "__main__":
    main()