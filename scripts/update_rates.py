import json
import re
import urllib.request
from datetime import datetime, timezone

URL = "https://www.nbt.tj/ru/kurs/kurs_kommer_bank.php"

req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

# Убираем HTML
text = re.sub(r"<[^>]+>", " ", html)
text = re.sub(r"\s+", " ", text)

banks = []

# Ищем строки банков и курсы USD
pattern = re.compile(
    r'(?:ОАО|ЗАО|ООО|ГУП)[^|]{2,100}?\s+'
    r'([0-9]+\.[0-9]+)\s+'
    r'([0-9]+\.[0-9]+)'
)

for match in pattern.finditer(text):
    name = match.group(0)

    numbers = re.findall(r'\d+\.\d+', name)

    if len(numbers) < 2:
        continue

    buy = float(numbers[0])
    sell = float(numbers[1])

    bank_name = re.sub(r'\d+\.\d+', '', name).strip()

    banks.append({
        "bank": bank_name,
        "USD": {
            "buy": buy,
            "sell": sell
        }
    })

data = {
    "source": "НБТ",
    "updated": datetime.now(timezone.utc).isoformat(),
    "banks": banks
}

with open("api/rates.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Банков найдено:", len(banks))
print("rates.json обновлён")