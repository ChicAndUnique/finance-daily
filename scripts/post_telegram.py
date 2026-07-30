#!/usr/bin/env python3
"""把每日简报 JSON 推送到 Telegram 频道。

用法:
    post_telegram.py docs/data/2026/07/29.json [更多文件...]
    post_telegram.py --dry-run docs/data/2026/07/29.json

环境变量:
    TG_BOT_TOKEN  BotFather 给的 token
    TG_CHAT_ID    频道标识，公开频道用 @yourchannel，私有频道用 -100xxxxxxxxxx
"""

import json
import os
import sys
import time
import html
import urllib.request
import urllib.error

API = "https://api.telegram.org/bot{token}/sendMessage"
LIMIT = 4000          # 官方上限 4096，留余量
GAP = 3.0             # 频道限速约每分钟 20 条

CATS = {
    "global": "全球市场",
    "cn":     "大陆金融",
    "policy": "政策动向",
    "scoop":  "独家爆料",
}
ORDER = ["global", "cn", "policy", "scoop"]
ARROW = {"利多": "▲", "利空": "▼", "中性": "・"}


def esc(s):
    return html.escape(str(s or ""), quote=False)


def render_item(it):
    cat = CATS.get(it.get("cat"), "其他")
    conf = it.get("confidence") or "未标注"
    lines = [f"<b>{esc(cat)}</b>  ·  {esc(conf)}"]

    if it.get("progress"):
        lines.append(f"<i>{esc(it['progress'])}</i>")

    title = esc(it.get("title"))
    url = it.get("url")
    lines.append("")
    lines.append(f'<b><a href="{esc(url)}">{title}</a></b>' if url else f"<b>{title}</b>")

    if it.get("facts"):
        lines += ["", esc(it["facts"])]
    if it.get("why"):
        lines += ["", f"<i>{esc(it['why'])}</i>"]

    assets = it.get("assets") or []
    if assets:
        lines.append("")
        lines.append("  ".join(
            f"{ARROW.get(a.get('dir'), '・')}{esc(a.get('name'))}" for a in assets))

    foot = [x for x in (it.get("time"), it.get("source")) if x]
    if foot:
        lines += ["", f"<code>{esc('  ·  '.join(foot))}</code>"]

    return "\n".join(lines)[:LIMIT]


def render_header(day):
    n = len(day.get("items") or [])
    rev = day.get("revision", 1)
    tag = f"  ·  第 {rev} 次更新" if rev and rev > 1 else ""
    counts = []
    for c in ORDER:
        k = sum(1 for i in day["items"] if i.get("cat") == c)
        if k:
            counts.append(f"{CATS[c]} {k}")
    return (f"<b>{esc(day['date'])}</b>  ·  {n} 条{tag}\n"
            f"<code>{esc('　'.join(counts))}</code>")


def send(token, chat_id, text, dry):
    if dry:
        print("─" * 56)
        print(text)
        return
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }).encode()
    req = urllib.request.Request(
        API.format(token=token), data=payload,
        headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if json.load(r).get("ok"):
                    return
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < 2:
                time.sleep(15)
                continue
            raise SystemExit(f"Telegram {e.code}: {body}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(5)
                continue
            raise SystemExit(f"网络错误: {e}")
    raise SystemExit("发送失败")


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if not args:
        print("没有待推送的文件", file=sys.stderr)
        return 0

    token = os.environ.get("TG_BOT_TOKEN", "")
    chat_id = os.environ.get("TG_CHAT_ID", "")
    if not dry and not (token and chat_id):
        raise SystemExit("缺少 TG_BOT_TOKEN 或 TG_CHAT_ID")

    for path in sorted(args):
        try:
            day = json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"跳过 {path}: {e}", file=sys.stderr)
            continue

        items = day.get("items") or []
        if not items:
            print(f"{day.get('date')} 无条目，不推送")
            continue

        items.sort(key=lambda i: ORDER.index(i["cat"]) if i.get("cat") in ORDER else 9)

        send(token, chat_id, render_header(day), dry)
        for it in items:
            time.sleep(0 if dry else GAP)
            send(token, chat_id, render_item(it), dry)
        print(f"{day['date']} 已推送 {len(items)} 条")

    return 0


if __name__ == "__main__":
    sys.exit(main())
