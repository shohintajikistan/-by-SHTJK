import json
import re
import urllib.request
from datetime import datetime, timezone
from html import unescape

NBT_URL = "https://www.nbt.tj/ru/kurs/kurs_kommer_bank.php"
OUTPUT_FILE = "api/rates.json"

CURRENCIES = ["USD", "EUR", "RUB", "CNY"]


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 SHTJK Currency Bot"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def clean_html(html):
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.I | re.S)

    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</tr\s*>", "\n", html, flags=re.I)
    html = re.sub(r"</td\s*>", " | ", html, flags=re.I)
    html = re.sub(r"</th\s*>", " | ", html, flags=re.I)

    html = re.sub(r"<[^>]+>", " ", html)

    text = unescape(html)

    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text


def number(value):
    try:
        value = value.replace(",", ".").strip()
        return float(value)
    except:
        return None


def find_currency_blocks(html):
    """
    Пытаемся определить выбранную валюту
    на странице НБТ.
    """

    text = clean_html(html)

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    return lines


def parse_bank_rows(lines):
    banks = []

    for line in lines:

        # В строке НБТ обычно есть:
        #
        # Название банка | число | число | число ...
        #
        if "|" not in line:
            continue

        parts = [
            p.strip()
            for p in line.split("|")
        ]

        if len(parts) < 4:
            continue

        bank_name = parts[0]

        # Отбрасываем заголовки
        if (
            "Кредитные финансовые организации" in bank_name
            or "Межбанк" in bank_name
            or "Наличные" in bank_name
            or "Безналичные" in bank_name
        ):
            continue

        # Собираем числа
        values = []

        for part in parts[1:]:
            value = number(part)

            if value is not None:
                values.append(value)

        if len(values) < 2:
            continue

        # НБТ:
        #
        # 0 = межбанк покупка
        # 1 = межбанк продажа
        # 2 = наличные покупка
        # 3 = наличные продажа
        # 4 = безналичные покупка
        # 5 = безналичные продажа
        #
        # Для SHTJK используем НАЛИЧНЫЕ.

        buy = values[2] if len(values) > 2 else values[0]
        sell = values[3] if len(values) > 3 else values[1]

        # Нулевые значения означают,
        # что данный курс отсутствует.
        if buy == 0 and sell == 0:
            continue

        banks.append({
            "bank": bank_name,
            "buy": buy,
            "sell": sell
        })

    return banks


def get_currency(currency):

    """
    НБТ использует одну и ту же страницу
    коммерческих банков, но отображает
    выбранную валюту.

    Здесь пытаемся получить страницу
    для каждой валюты.
    """

    # Сначала обычная страница.
    #
    # В дальнейшем, если НБТ изменит параметры
    # выбора валюты, это место легко изменить.

    url = NBT_URL

    html = download(url)

    lines = find_currency_blocks(html)

    banks = parse_bank_rows(lines)

    return banks


def main():

    result = {
        "source": "НБТ",
        "updated": datetime.now(timezone.utc).isoformat(),
        "base": "TJS",
        "currencies": {}
    }

    for currency in CURRENCIES:

        print("Получаем:", currency)

        banks = get_currency(currency)

        result["currencies"][currency] = banks

        print(
            currency,
            "банков:",
            len(banks)
        )

    # Проверяем, что что-то реально получили
    total = sum(
        len(items)
        for items in result["currencies"].values()
    )

    if total == 0:
        raise RuntimeError(
            "НБТ не вернул курсы. "
            "Файл rates.json не будет перезаписан."
        )

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
    print("================================")
    print("SHTJK RATES UPDATED")
    print("Всего записей:", total)
    print("================================")


if __name__ == "__main__":
    main()