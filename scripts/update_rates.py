import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import json
import re
import os

BASE_URL = "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"

CURRENCIES = {
    "USD": "Доллар США",
    "EUR": "Евро",
    "RUB": "Российский рубль",
    "CNY": "Китайский юань"
}

OUTPUT_FILE = "api/rates.json"


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def number(value):
    if value is None:
        return None

    value = value.replace(",", ".").strip()

    try:
        return float(value)
    except:
        return None


def get_nbt_page(currency):
    print(f"Получаем {currency}...")

    params = {
        "valuta": currency
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
    }

    response = requests.get(
        BASE_URL,
        params=params,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    response.encoding = response.apparent_encoding

    return response.text


def parse_currency(html, currency):
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")

    if not tables:
        raise RuntimeError(
            f"НБТ не вернул таблицу для {currency}"
        )

    result = {}

    for table in tables:

        rows = table.find_all("tr")

        if len(rows) < 2:
            continue

        for row in rows[1:]:

            cells = row.find_all(["td", "th"])

            if len(cells) < 4:
                continue

            values = [
                clean_text(cell.get_text(" ", strip=True))
                for cell in cells
            ]

            bank_name = values[0]

            if not bank_name:
                continue

            # НБТ:
            # 0 = организация
            # 1 = межбанк покупка
            # 2 = межбанк продажа
            # 3 = наличные покупка
            # 4 = наличные продажа
            # 5 = безналичные покупка
            # 6 = безналичные продажа

            buy = None
            sell = None

            if len(values) >= 5:
                buy = number(values[3])
                sell = number(values[4])

            if buy is None or sell is None:
                continue

            # Не принимаем нулевые значения
            if buy == 0 and sell == 0:
                continue

            result[bank_name] = {
                "buy": buy,
                "sell": sell
            }

    return result


def main():

    print("====================================")
    print(" SHTJK - НБТ CURRENCY UPDATER")
    print("====================================")

    all_data = {}

    for currency in CURRENCIES:

        try:
            html = get_nbt_page(currency)

            parsed = parse_currency(
                html,
                currency
            )

            all_data[currency] = parsed

            print(
                f"{currency}: найдено "
                f"{len(parsed)} организаций"
            )

        except Exception as e:

            print(
                f"ОШИБКА {currency}: {e}"
            )

            all_data[currency] = {}

    banks = {}

    # Собираем все организации
    for currency in all_data:

        for bank_name in all_data[currency]:

            if bank_name not in banks:
                banks[bank_name] = {
                    "bank": bank_name
                }

            banks[bank_name][currency] = \
                all_data[currency][bank_name]

    final_banks = []

    for bank_name, data in banks.items():

        # Добавляем только организации,
        # где есть хотя бы одна валюта
        currencies_count = 0

        for currency in CURRENCIES:
            if currency in data:
                currencies_count += 1

        if currencies_count > 0:
            final_banks.append(data)

    final_banks.sort(
        key=lambda x: x["bank"].lower()
    )

    now = datetime.now(
        timezone.utc
    ).astimezone()

    output = {
        "source": "Национальный Банк Таджикистана",
        "source_url": BASE_URL,
        "updated": now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "currency_count": len(CURRENCIES),
        "bank_count": len(final_banks),
        "banks": final_banks
    }

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
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
    print("====================================")
    print(" ГОТОВО")
    print("====================================")
    print(
        f"Банков/организаций: {len(final_banks)}"
    )
    print(
        f"Файл: {OUTPUT_FILE}"
    )
    print("====================================")


if __name__ == "__main__":
    main()