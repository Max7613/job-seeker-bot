import os
import json
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- Конфигурация ---
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL")
SEEN_FILE = "seen_results.json"

# --- Поисковые запросы (поиск клиентов для клинингового агентства) ---
QUERIES = [
    # Иврит
    {"q": "מחפש עוזרת בית", "hl": "iw", "gl": "il"},
    {"q": "מחפשת עוזרת בית תל אביב", "hl": "iw", "gl": "il"},
    {"q": "צריך שירותי ניקיון", "hl": "iw", "gl": "il"},
    {"q": "חברת ניקיון דירות", "hl": "iw", "gl": "il"},
    {"q": "מחפש מנקה לבית", "hl": "iw", "gl": "il"},
    # Русский
    {"q": "ищу уборщицу Израиль", "hl": "ru", "gl": "il"},
    {"q": "нужна помощница по хозяйству Тель-Авив", "hl": "ru", "gl": "il"},
    {"q": "клининг квартиры Израиль", "hl": "ru", "gl": "il"},
    {"q": "уборка дома Израиль", "hl": "ru", "gl": "il"},
    # Английский
    {"q": "looking for cleaning service Israel", "hl": "en", "gl": "il"},
    {"q": "need house cleaner Tel Aviv", "hl": "en", "gl": "il"},
    {"q": "apartment cleaning Israel", "hl": "en", "gl": "il"},
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def search(query_params):
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "q": query_params["q"],
        "hl": query_params["hl"],
        "gl": query_params["gl"],
        "num": 10,
            }
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = []
        for r in data.get("organic_results", []):
            results.append({
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "query": query_params["q"],
            })
        return results
    except Exception as e:
        print(f"[!] Ошибка при поиске '{query_params['q']}': {e}")
        return []

def send_email(new_results):
    if not new_results:
        print("[i] Новых результатов нет, письмо не отправляется.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Misme — потенциальные клиенты {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    msg["From"] = GMAIL_USER
    msg["To"] = NOTIFY_EMAIL

    # Группируем по запросу
    by_query = {}
    for r in new_results:
        by_query.setdefault(r["query"], []).append(r)

    html = """
    <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
    <h2 style="color: #2c7be5;">🏠 Misme — потенциальные клиенты</h2>
    <p style="color: #666;">Новые результаты поиска за последние сутки</p>
    """

    for query, results in by_query.items():
        html += f'<h3 style="background:#f0f4ff;padding:8px;border-radius:4px;">🔍 {query}</h3>'
        for r in results:
            html += f"""
            <div style="border:1px solid #e0e0e0;border-radius:6px;padding:12px;margin-bottom:10px;">
                <a href="{r['link']}" style="font-size:16px;color:#2c7be5;text-decoration:none;">
                    {r['title']}
                </a>
                <p style="color:#555;margin:6px 0;">{r['snippet']}</p>
                <a href="{r['link']}" style="font-size:12px;color:#999;">{r['link']}</a>
            </div>
            """

    html += f"""
    <p style="color:#999;font-size:12px;margin-top:20px;">
        Всего новых результатов: {len(new_results)} | 
        Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}
    </p>
    </body></html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
        print(f"[✓] Письмо отправлено: {len(new_results)} результатов")
    except Exception as e:
        print(f"[!] Ошибка отправки письма: {e}")

def main():
    print(f"[→] Запуск бота: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    seen = load_seen()
    all_results = []

    for query_params in QUERIES:
        print(f"[→] Запрос: {query_params['q']}")
        results = search(query_params)
        for r in results:
            if r["link"] not in seen:
                seen.add(r["link"])
                all_results.append(r)
                print(f"    [+] {r['title']}")

    print(f"[i] Новых результатов: {len(all_results)}")
    save_seen(seen)
    send_email(all_results)
    print("[✓] Готово")

if __name__ == "__main__":
    main()
