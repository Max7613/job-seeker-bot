"""
Job Seeker Bot — ищет объявления "ищу работу" на израильских сайтах
и отправляет дайджест на email раз в час.

Требует переменных окружения:
  GOOGLE_API_KEY       — ключ Google Custom Search API
  GOOGLE_CSE_ID        — ID Custom Search Engine
  GMAIL_USER           — твой Gmail (отправитель)
  GMAIL_APP_PASSWORD   — App Password от Gmail (не основной пароль!)
  NOTIFY_EMAIL         — куда слать результаты
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Настройки ────────────────────────────────────────────────────────────────

SEARCH_QUERIES = [
    # ── Русский ──────────────────────────────────────────────────────────────
    "ищу работу Израиль",
    "ищу работу Тель-Авив",
    "ищу работу Хайфа",
    "ищу работу уборка Израиль",        # релевантно для Misme
    "ищу работу клининг Израиль",

    # ── Английский ───────────────────────────────────────────────────────────
    "looking for work Israel",
    "seeking employment Israel",
    "job seeker Israel cleaning",       # клининг на английском

    # ── Иврит ────────────────────────────────────────────────────────────────
    "מחפש עבודה",                        # мищукаш авода — ищу работу (муж.)
    "מחפשת עבודה",                       # мищукешет авода — ищу работу (жен.)
    "מחפש עבודה ניקיון",                 # ищу работу уборка
    "דרוש עבודה ישראל",                  # требуется работа Израиль

    # ── Амхарский ────────────────────────────────────────────────────────────
    "ስራ እፈልጋለሁ እስራኤል",                  # работу ищу Израиль
    "ስራ ፍለጋ እስራኤል",                     # поиск работы Израиль
    "ስራ እፈልጋለሁ ጽዳት",                    # ищу работу уборка

    # ── Арабский ─────────────────────────────────────────────────────────────
    "أبحث عن عمل إسرائيل",               # ищу работу Израиль
    "أبحث عن عمل تنظيف إسرائيل",        # ищу работу уборка Израиль
    "فرصة عمل إسرائيل",                  # возможность работы Израиль

    # ── Французский ──────────────────────────────────────────────────────────
    "cherche emploi Israël",
    "je cherche du travail Israël",
    "cherche travail ménage Israël",    # ищу работу по дому/уборка
]

# Файл для хранения уже отправленных результатов (дедупликация)
SEEN_FILE = Path("seen_results.json")

# ── Google Search ─────────────────────────────────────────────────────────────

def google_search(query: str, api_key: str, cse_id: str) -> list[dict]:
    """Возвращает список результатов поиска для одного запроса."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": 10,
        "dateRestrict": "d1",   # только за последние сутки
        "hl": "ru",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"[!] Ошибка при поиске '{query}': {e}")
        return []


def collect_results(api_key: str, cse_id: str) -> list[dict]:
    """Собирает все результаты по всем запросам, убирает дубли."""
    seen_urls: set[str] = set()
    results = []

    for query in SEARCH_QUERIES:
        print(f"[→] Запрос: {query}")
        items = google_search(query, api_key, cse_id)
        for item in items:
            url = item.get("link", "")
            if url not in seen_urls:
                seen_urls.add(url)
                results.append({
                    "title":   item.get("title", ""),
                    "url":     url,
                    "snippet": item.get("snippet", ""),
                    "query":   query,
                })

    return results


# ── Дедупликация (не слать одно и то же дважды) ──────────────────────────────

def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data.get("hashes", []))
    return set()


def save_seen(hashes: set[str]) -> None:
    # Храним не более 5000 хешей, чтобы файл не рос бесконечно
    trimmed = list(hashes)[-5000:]
    SEEN_FILE.write_text(
        json.dumps({"hashes": trimmed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def filter_new(results: list[dict], seen: set[str]) -> list[dict]:
    new = []
    for r in results:
        h = url_hash(r["url"])
        if h not in seen:
            new.append(r)
    return new


# ── Email ─────────────────────────────────────────────────────────────────────

def build_html(results: list[dict]) -> str:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    rows = ""
    for r in results:
        rows += f"""
        <tr>
          <td style="padding:10px 8px; border-bottom:1px solid #eee; vertical-align:top;">
            <a href="{r['url']}" style="font-weight:600; color:#1a73e8; text-decoration:none;">
              {r['title']}
            </a><br>
            <span style="font-size:12px; color:#888;">Запрос: {r['query']}</span><br>
            <span style="font-size:13px; color:#444;">{r['snippet']}</span>
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif; color:#222; max-width:700px; margin:auto;">
      <h2 style="background:#1a73e8; color:#fff; padding:16px 20px; border-radius:8px;">
        📋 Дайджест «ищу работу» — {now}
      </h2>
      <p>Найдено новых объявлений: <strong>{len(results)}</strong></p>
      <table width="100%" cellspacing="0" cellpadding="0">{rows}</table>
      <p style="font-size:11px; color:#aaa; margin-top:20px;">
        Бот запускается каждый час. Повторные результаты не присылаются.
      </p>
    </body></html>
    """


def send_email(results: list[dict], gmail_user: str, app_password: str, notify_email: str) -> None:
    subject = f"[Job Bot] {len(results)} новых объявлений — {datetime.now().strftime('%d.%m %H:%M')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = notify_email

    html_part = MIMEText(build_html(results), "html", "utf-8")
    msg.attach(html_part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, notify_email, msg.as_string())

    print(f"[✓] Письмо отправлено на {notify_email}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key      = os.environ["GOOGLE_API_KEY"]
    cse_id       = os.environ["GOOGLE_CSE_ID"]
    gmail_user   = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    notify_email = os.environ["NOTIFY_EMAIL"]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Старт сбора...")

    all_results = collect_results(api_key, cse_id)
    print(f"[i] Всего найдено уникальных URL: {len(all_results)}")

    seen = load_seen()
    new_results = filter_new(all_results, seen)
    print(f"[i] Новых (не присылались раньше): {len(new_results)}")

    if not new_results:
        print("[i] Новых результатов нет, письмо не отправляется.")
        return

    send_email(new_results, gmail_user, app_password, notify_email)

    # Сохраняем хеши отправленных
    new_hashes = {url_hash(r["url"]) for r in new_results}
    save_seen(seen | new_hashes)


if __name__ == "__main__":
    main()
