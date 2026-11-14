#!/usr/bin/env python3
"""Pull yesterday's Meta ads insights for 健人餐廚 and print a markdown table.

LINE 新好友數尚無法自動抓取，該欄標為「待接 LINE 後台」。
Token is read from /home/box/.secrets/meta_token and is never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

AD_ACCOUNT = "act_1163319143317586"
GRAPH_VERSION = "v21.0"
TOKEN_PATH = Path("/home/box/.secrets/meta_token")
TZ = ZoneInfo("Asia/Taipei")

LINK_CLICK_TYPES = ("link_click", "inline_link_click", "outbound_click")
LANDING_TYPES = ("landing_page_view",)
LEAD_TYPES = (
    "lead",
    "offsite_conversion.fb_pixel_lead",
    "offsite_conversion.custom.Lead",
)
CLICKLINE_TYPES = (
    "offsite_conversion.fb_pixel_custom.ClickLINE",
    "offsite_conversion.custom.ClickLINE",
    "ClickLINE",
)


def load_token() -> str:
    if not TOKEN_PATH.exists():
        raise SystemExit(f"找不到 token 檔：{TOKEN_PATH}")
    token = TOKEN_PATH.read_text().strip()
    if not token:
        raise SystemExit(f"token 檔是空的：{TOKEN_PATH}")
    return token


def yesterday(date_str: str | None) -> str:
    if date_str:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    return (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")


def graph_get(path: str, token: str, params: dict) -> dict:
    query = dict(params)
    query["access_token"] = token
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        # Never include the request URL (it has the token).
        raise SystemExit(f"Marketing API 錯誤 HTTP {exc.code}：{body}") from None
    except urllib.error.URLError as exc:
        raise SystemExit(f"Marketing API 連線失敗：{exc.reason}") from None


def action_sum(actions: list | None, wanted: tuple[str, ...], contains: str | None = None) -> float:
    total = 0.0
    if not actions:
        return total
    wanted_set = set(wanted)
    for item in actions:
        action_type = str(item.get("action_type") or "")
        if action_type in wanted_set or (contains and contains.lower() in action_type.lower()):
            try:
                total += float(item.get("value") or 0)
            except (TypeError, ValueError):
                continue
    return total


def fmt_int(value: float | int | str) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "0"


def fmt_money(value: float | int | str) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def fetch_rows(token: str, day: str) -> tuple[list[dict], list[str]]:
    fields = ",".join(
        [
            "ad_id",
            "ad_name",
            "campaign_name",
            "adset_name",
            "spend",
            "impressions",
            "inline_link_clicks",
            "actions",
        ]
    )
    payload = graph_get(
        f"{AD_ACCOUNT}/insights",
        token,
        {
            "level": "ad",
            "fields": fields,
            "time_range": json.dumps({"since": day, "until": day}),
            "limit": 500,
        },
    )
    rows = list(payload.get("data") or [])
    # Follow paging if present; rebuild from the returned URL is unsafe (contains token).
    # Re-request with after= cursor instead.
    paging = payload.get("paging") or {}
    while paging.get("next") and (paging.get("cursors") or {}).get("after"):
        after = paging["cursors"]["after"]
        payload = graph_get(
            f"{AD_ACCOUNT}/insights",
            token,
            {
                "level": "ad",
                "fields": fields,
                "time_range": json.dumps({"since": day, "until": day}),
                "limit": 500,
                "after": after,
            },
        )
        rows.extend(payload.get("data") or [])
        paging = payload.get("paging") or {}

    seen_actions: set[str] = set()
    parsed = []
    for row in rows:
        actions = row.get("actions") or []
        for item in actions:
            if item.get("action_type"):
                seen_actions.add(item["action_type"])
        link_clicks = row.get("inline_link_clicks")
        if link_clicks in (None, ""):
            link_clicks = action_sum(actions, LINK_CLICK_TYPES)
        parsed.append(
            {
                "ad_id": row.get("ad_id") or "",
                "ad_name": row.get("ad_name") or "（未命名）",
                "campaign_name": row.get("campaign_name") or "",
                "spend": float(row.get("spend") or 0),
                "impressions": float(row.get("impressions") or 0),
                "link_clicks": float(link_clicks or 0),
                "landing_page_view": action_sum(actions, LANDING_TYPES),
                "lead": action_sum(actions, LEAD_TYPES, contains="fb_pixel_lead"),
                "click_line": action_sum(actions, CLICKLINE_TYPES, contains="ClickLINE"),
            }
        )
    return parsed, sorted(seen_actions)


def to_markdown(day: str, rows: list[dict], seen_actions: list[str]) -> str:
    lines = [
        f"# 健人餐廚巨蛋店廣告日報（{day}，Asia/Taipei）",
        "",
        "資料來源：Meta Marketing API insights，廣告帳戶 `act_1163319143317586`，依廣告拆開。",
        "LINE 新好友數尚無法自動抓取，該欄標為「待接 LINE 後台」。",
        "",
        "| 廣告 | 花費 (TWD) | 曝光 | 連結點擊 | 落地頁瀏覽 | Lead | ClickLINE | LINE 新好友 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not rows:
        lines.append("| （昨日無投放資料） | 0.00 | 0 | 0 | 0 | 0 | 0 | 待接 LINE 後台 |")
    else:
        totals = {
            "spend": 0.0,
            "impressions": 0.0,
            "link_clicks": 0.0,
            "landing_page_view": 0.0,
            "lead": 0.0,
            "click_line": 0.0,
        }
        for row in rows:
            name = row["ad_name"].replace("|", "\\|")
            if row["ad_id"]:
                name = f"{name} (`{row['ad_id']}`)"
            lines.append(
                "| {name} | {spend} | {impr} | {clicks} | {lpv} | {lead} | {cline} | 待接 LINE 後台 |".format(
                    name=name,
                    spend=fmt_money(row["spend"]),
                    impr=fmt_int(row["impressions"]),
                    clicks=fmt_int(row["link_clicks"]),
                    lpv=fmt_int(row["landing_page_view"]),
                    lead=fmt_int(row["lead"]),
                    cline=fmt_int(row["click_line"]),
                )
            )
            for key in totals:
                totals[key] += row[key]
        lines.append(
            "| **合計** | {spend} | {impr} | {clicks} | {lpv} | {lead} | {cline} | 待接 LINE 後台 |".format(
                spend=fmt_money(totals["spend"]),
                impr=fmt_int(totals["impressions"]),
                clicks=fmt_int(totals["link_clicks"]),
                lpv=fmt_int(totals["landing_page_view"]),
                lead=fmt_int(totals["lead"]),
                cline=fmt_int(totals["click_line"]),
            )
        )

    if seen_actions:
        lines.extend(["", "昨日 API 回傳的 action_type：" + ", ".join(f"`{a}`" for a in seen_actions)])
    else:
        lines.extend(["", "昨日沒有回傳任何 action_type（尚未投放或像素事件還未寫入）。"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="健人餐廚巨蛋店廣告日報")
    parser.add_argument("--date", help="要查的日期（Asia/Taipei，YYYY-MM-DD），預設昨天")
    parser.add_argument("--out", help="同時寫入這個 markdown 檔")
    args = parser.parse_args()

    day = yesterday(args.date)
    token = load_token()
    rows, seen_actions = fetch_rows(token, day)
    report = to_markdown(day, rows, seen_actions)
    sys.stdout.write(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
