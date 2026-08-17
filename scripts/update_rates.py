import json
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser


# =========================================================
# SHTJK — REAL NBT BANK RATES
# USD / EUR / RUB / CNY
# =========================================================

NBT_URL = "https://www.nbt.tj/ru/kurs/kurs_kommer_bank.php"
OUTPUT_FILE = "api/rates.json"


# ---------------------------------------------------------
# HTML TABLE PARSER
# ---------------------------------------------------------

class TableParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.in_table = False
        self.in_row = False
        self.in_cell = False

        self.rows = []
        self.current_row = []
        self.current_cell = ""

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        if tag == "table":
            self.in_table = True

        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []

        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag in ("td", "th") and self.in_cell:

            value = unescape(self.current_cell)

            value = re.sub(r"\s+", " ", value)

            self.current_row.append(value.strip())

            self.current_cell = ""
            self.in_cell = False

        elif tag == "tr" and self.in_row:

            if self.current_row:
                self.rows.append(self.current_row)

            self.current_row = []
            self.in_row = False

        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):

        if self.in_cell:
            self.current_cell += data


# ---------------------------------------------------------
# DOWNLOAD NBT
# ---------------------------------------------------------

def download_nbt():

    request = urllib.request.Request(
        NBT_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/120 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml"
        }
    )

    with urllib.request.urlopen(request, timeout=60) as response:

        return response.read().decode(
            "utf-8",
            errors="ignore"
        )


# ---------------------------------------------------------
# NUMBER
# ---------------------------------------------------------

def to_number(value):

    value = value.strip()

    value = value.replace(",", ".")

    try:
        return float(value)

    except ValueError:
        return None


# ---------------------------------------------------------
# BANK NAME CLEANING
# ---------------------------------------------------------

def clean_bank_name(name):

    name = unescape(name)

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    return name


# ---------------------------------------------------------
# CHECK BANK
# ---------------------------------------------------------

def is_financial_organization(name):

    name_lower = name.lower()

    forbidden = [
        "кредитные финансовые организации",
        "межбанк",
        "наличные",
        "безналичные",
        "эл.кошелек",
        "карты",
        "нпцдп"
    ]

    for word in forbidden:

        if word in name_lower:
            return False

    return (
        len(name) >= 5
        and (
            "банк" in name_lower
            or "банка" in name_lower
            or "bank" in name_lower
            or "мдо" in name_lower
            or "молия" in name_lower
        )
    )


# ---------------------------------------------------------
# PARSE TABLE
# ---------------------------------------------------------

def parse_table(html):

    parser = TableParser()

    parser.feed(html)

    rows = parser.rows

    if not rows:

        raise RuntimeError(
            "НБТ: таблица банков не найдена."
        )

    # -----------------------------------------------------
    # Ищем строку заголовков
    # -----------------------------------------------------

    header_index = None

    for i, row in enumerate(rows):

        joined = " ".join(row).lower()

        if (
            "кредитные финансовые организации" in joined
            and "наличные покупка" in joined
            and "наличные продажа" in joined
        ):

            header_index = i

            break

    if header_index is None:

        raise RuntimeError(
            "НБТ: заголовок таблицы не найден."
        )

    header = rows[header_index]

    # -----------------------------------------------------
    # Определяем позиции колонок
    # -----------------------------------------------------

    name_index = None
    cash_buy_index = None
    cash_sell_index = None
    date_index = None

    for i, column in enumerate(header):

        c = column.lower().strip()

        if (
            "кредитные финансовые организации"
            in c
        ):

            name_index = i

        elif c == "наличные покупка":

            cash_buy_index = i

        elif c == "наличные продажа":

            cash_sell_index = i

        elif c == "дата":

            date_index = i

    if (
        name_index is None
        or cash_buy_index is None
        or cash_sell_index is None
    ):

        raise RuntimeError(
            "НБТ: нужные колонки не найдены."
        )

    # -----------------------------------------------------
    # Банки
    # -----------------------------------------------------

    banks = []

    latest_date = None

    for row in rows[header_index + 1:]:

        if len(row) <= max(
            name_index,
            cash_buy_index,
            cash_sell_index
        ):

            continue

        name = clean_bank_name(
            row[name_index]
        )

        if not is_financial_organization(name):

            continue

        buy = to_number(
            row[cash_buy_index]
        )

        sell = to_number(
            row[cash_sell_index]
        )

        if buy is None or sell is None:

            continue

        # 0.0000 означает, что курс отсутствует

        if buy == 0 and sell == 0:

            continue

        bank = {
            "bank": name,
            "buy": buy,
            "sell": sell
        }

        if date_index is not None and len(row) > date_index:

            date_value = row[date_index].strip()

            if date_value:

                bank["updated"] = date_value

                latest_date = date_value

        banks.append(bank)

    return banks, latest_date


# ---------------------------------------------------------
# GET CURRENT NBT CURRENCY
# ---------------------------------------------------------

def get_current_currency():

    html = download_nbt()

    banks, date_value = parse_table(html)

    return banks, date_value


# ---------------------------------------------------------
# IMPORTANT
#
# NBT page normally shows ONE selected currency.
#
# This function tries several known parameter names.
# If NBT changes its form, the script will not overwrite
# the existing JSON with empty data.
# ---------------------------------------------------------

def get_currency(currency):

    possible_urls = [

        NBT_URL + "?currency=" + currency,

        NBT_URL + "?valuta=" + currency,

        NBT_URL + "?cur=" + currency,

        NBT_URL + "?code=" + currency,

        NBT_URL + "?currency_code=" + currency,

    ]

    for url in possible_urls:

        try:

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 SHTJK"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=60
            ) as response:

                html = response.read().decode(
                    "utf-8",
                    errors="ignore"
                )

            banks, date_value = parse_table(
                html
            )

            if banks:

                return banks, date_value

        except Exception:

            continue

    return [], None


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print("====================================")
    print("SHTJK REAL NBT RATES")
    print("====================================")

    currencies = [
        "USD",
        "EUR",
        "RUB",
        "CNY"
    ]

    result = {

        "source": "НБТ",

        "source_url": NBT_URL,

        "updated": datetime.now(
            timezone.utc
        ).isoformat(),

        "base": "TJS",

        "type": "cash",

        "currencies": {}

    }

    total = 0

    # -----------------------------------------------------
    # Получаем валюты
    # -----------------------------------------------------

    for currency in currencies:

        print(
            "Получаем",
            currency,
            "..."
        )

        banks, date_value = get_currency(
            currency
        )

        # -------------------------------------------------
        # Защита от пустого результата
        # -------------------------------------------------

        if not banks:

            print(
                "WARNING:",
                currency,
                "не получен"
            )

            continue

        result["currencies"][currency] = {

            "updated": date_value,

            "banks": banks

        }

        total += len(banks)

        print(
            currency,
            "OK:",
            len(banks),
            "организаций"
        )

    # -----------------------------------------------------
    # Если ничего не получили — НЕ портим JSON
    # -----------------------------------------------------

    if total == 0:

        raise RuntimeError(
            "НБТ не вернул ни одного курса. "
            "rates.json НЕ изменён."
        )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("====================================")
    print("SHTJK SUCCESS")
    print("Всего записей:", total)
    print("Файл:", OUTPUT_FILE)
    print("====================================")


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":

    main()