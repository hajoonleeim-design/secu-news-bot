import os
import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import html
import re

KST = timezone(timedelta(hours=9))

RSS_SOURCES = [
    {
        "name": "🛡️ 보안뉴스 (오늘의 주요 기사)",
        "url": "https://news.google.com/rss/search?q=site:boannews.com+when:2d&hl=ko&gl=KR&ceid=KR:ko",
        "encoding": "utf-8",
        "limit": 5,
    },
    {
        "name": "🚨 데일리시큐 (최신 보안 뉴스)",
        "url": "https://www.dailysecu.com/rss/allArticle.xml",
        "encoding": "utf-8",
        "limit": 5,
    },
]


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_rss_items(source: dict) -> list:
    req = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SecuNewsBot/1.0"
        },
    )
    items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        try:
            xml_text = raw.decode(source["encoding"], errors="replace")
        except Exception:
            xml_text = raw.decode("utf-8", errors="replace")

        root = ET.fromstring(xml_text)
        for item in root.findall(".//item")[: source["limit"]]:
            title = clean_text(item.findtext("title", ""))
            link = (item.findtext("link", "") or "").strip()
            desc = clean_text(item.findtext("description", ""))
            if len(desc) > 90:
                desc = desc[:90] + "..."
            if title and link:
                items.append({"title": title, "link": link, "desc": desc})
    except Exception as e:
        print(f"[WARN] {source['name']} 수집 실패: {e}")
    return items


def build_message() -> str:
    now_str = datetime.now(KST).strftime("%Y-%m-%d (%a) %H:%M")
    lines = [f"📢 **[오늘의 보안뉴스 브리핑]** `{now_str}`\n"]

    for src in RSS_SOURCES:
        articles = fetch_rss_items(src)
        lines.append(f"**{src['name']}**")
        if not articles:
            lines.append("- (수집된 기사가 없습니다)")
        for idx, art in enumerate(articles, 1):
            title = art["title"].replace(" - 보안뉴스", "").strip()
            lines.append(f"{idx}. [{title}](<{art['link']}>)")
        lines.append("")

    return "\n".join(lines).strip()


def send_discord(webhook_url: str, message: str):
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SecuNewsBot/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"[OK] Discord 전송 완료 (HTTP {resp.status})")


def send_telegram(bot_token: str, chat_id: str, message: str):
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"[OK] Telegram 전송 완료 (HTTP {resp.status})")


def main():
    import sys
    msg = build_message()
    print("=== 생성된 보안뉴스 브리핑 ===")
    print(msg)
    print("==============================")

    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not discord_webhook and len(sys.argv) > 1:
        discord_webhook = sys.argv[1].strip()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    sent = False
    if discord_webhook:
        send_discord(discord_webhook, msg)
        sent = True

    if tg_token and tg_chat_id:
        send_telegram(tg_token, tg_chat_id, msg)
        sent = True

    if not sent:
        print(
            "[INFO] DISCORD_WEBHOOK_URL 또는 TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않아 콘솔 출력만 수행했습니다."
        )


if __name__ == "__main__":
    main()
