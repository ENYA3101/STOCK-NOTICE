import requests
import datetime
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def parse_date(date_str):
    if not date_str:
        return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:
            return datetime.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except:
        return None
    return None

def split_period(raw):
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

def get_real_data():
    all_stocks = []

    # ---- TWSE 上市 ----
    try:
        r = requests.get(
            "https://www.twse.com.tw/rwd/zh/announcement/punish",
            params={"response": "json"},
            headers=HEADERS,
            timeout=15
        )
        json_data = r.json()
        items = json_data.get('data', [])
        for i in items:
            if len(i) < 7:
                continue
            start, end = split_period(i[6])
            if not end:
                continue
            all_stocks.append({
                'id': i[2], 'name': i[3],
                'announce': parse_date(i[1]),
                'start': start, 'end': end,
                'range': i[6], 'market': '上市'
            })
    except Exception as e:
        print("上市抓取失敗:", e)

# ---- TPEx 上櫃 ----
try:
    r = requests.get(
        "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php",
        params={"l": "zh-tw", "response": "json"},
        headers=HEADERS,
        timeout=15
    )

    # 🔒 關鍵防爬蟲防呆
    if not r.text or not r.text.strip().startswith("{"):
        print("⚠️ 上櫃回傳非 JSON，可能被 TPEx 擋（GitHub Actions 常見）")
        print(r.text[:200])
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
                'id': i[1],
                'name': i[2],
                'announce': parse_date(i[0]),
                'start': start,
                'end': end,
                'range': i[3],
                'market': '上櫃'
            })

except Exception as e:
    print("上櫃抓取失敗:", e)

def main():
    today = datetime.date.today()
    stocks = get_real_data()

    msg = f"📅 處置股報表：{today}\n\n"
    new_ann, out_jail, still_in = [], [], []

    for s in stocks:
        if not s['end']:
            continue
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']})[{s['market']}] 期間：{s['range']}"

        if exit_day == today:
            out_jail.append(info)
        if s['announce'] == today:
            new_ann.append(f"🔔 {info}")
        if s['end'] >= today and s['announce'] != today:
            still_in.append(info)

    msg += "【🔔 今日新公告】\n" + ("\n".join(new_ann) if new_ann else "無") + "\n\n"
    msg += "【🔓 出關清單】\n" + ("\n".join(out_jail) if out_jail else "無") + "\n\n"
    msg += "【⏳ 處置中】\n" + ("\n".join(still_in) if still_in else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg}
        )

    print("執行成功，共抓到:", len(stocks))

if __name__ == "__main__":
    main()