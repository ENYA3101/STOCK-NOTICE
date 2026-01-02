import requests
import datetime
import os

# =============================
# 基本設定
# =============================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# =============================
# 工具函式
# =============================
def parse_date(date_str):
    """支援 115/01/01、1150101、20260101"""
    if not date_str:
        return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:  # 民國
            return datetime.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:  # 西元
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except:
        return None
    return None


def split_period(raw):
    """處理 ～ 或 - 的日期區間"""
    if not raw:
        return None, None
    if '～' in raw:
        p = raw.split('～')
    elif '-' in raw:
        p = raw.split('-')
    else:
        return None, None

    if len(p) < 2:
        return None, None

    return parse_date(p[0]), parse_date(p[1])


# =============================
# 抓取資料（上市＋上櫃）
# =============================
def get_real_data():
    all_stocks = []

    # ---------- 上市 TWSE ----------
    try:
        r = requests.get(
            "https://www.twse.com.tw/rwd/zh/announcement/punish",
            params={"response": "json"},
            headers=HEADERS,
            timeout=15
        )
        items = r.json().get("data", [])

        for i in items:
            if len(i) < 7:
                continue

            start, end = split_period(i[6])
            if not end:
                continue

            all_stocks.append({
                "id": i[2],
                "name": i[3],
                "announce": parse_date(i[1]),
                "start": start,
                "end": end,
                "range": i[6],
                "market": "上市"
            })

    except Exception as e:
        print("❌ 上市抓取失敗:", e)

    # ---------- 上櫃 TPEx ----------
    try:
        r = requests.get(
            "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php",
            params={"l": "zh-tw", "response": "json"},
            headers=HEADERS,
            timeout=15
        )

        # 🔒 防爬蟲：GitHub Actions 常被擋
        if not r.text or not r.text.strip().startswith("{"):
            print("⚠️ 上櫃回傳非 JSON（可能被 TPEx 擋）")
            print(r.text[:200])
            data = []
        else:
            json_data = r.json()
            data = json_data.get("aaData", [])
            print("📌 上櫃處置股筆數：", len(data))

        for i in data:
            if len(i) < 4:
                continue

            start, end = split_period(i[3])
            if not end:
                continue

            all_stocks.append({
                "id": i[1],
                "name": i[2],
                "announce": parse_date(i[0]),
                "start": start,
                "end": end,
                "range": i[3],
                "market": "上櫃"
            })

    except Exception as e:
        print("❌ 上櫃抓取失敗:", e)

    # 🔑 關鍵：一定回傳 list
    return all_stocks


# =============================
# 主程式
# =============================
def main():
    today = datetime.date.today()
    stocks = get_real_data()

    new_announcement = []
    out_of_jail = []
    still_in = []

    for s in stocks:
        if not s.get("end"):
            continue

        exit_day = s["end"] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']})[{s['market']}] 期間：{s['range']}"

        # 今日出關
        if exit_day == today:
            out_of_jail.append(info)

        # 今日新公告
        if s["announce"] == today:
            new_announcement.append(f"🔔 {info}")

        # 處置中
        if s["end"] >= today and s["announce"] != today:
            still_in.append(info)

    # ---------- 組訊息 ----------
    msg = f"📅 處置股報表：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_announcement) if new_announcement else "無") + "\n\n"
    msg += "【🔓 本日出關股票】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【⏳ 處置中股票】\n" + ("\n".join(still_in) if still_in else "無")

    # ---------- Telegram ----------
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg}
        )

    print(f"✅ 執行完成，共抓到 {len(stocks)} 檔（上市＋上櫃）")


if __name__ == "__main__":
    main()