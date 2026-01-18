import requests
import datetime
import os
import csv
import io
import re
import pytz

# ===========================
# 1. 基礎工具
# ===========================
def get_twse_holidays():
    url = "https://www.twse.com.tw/rwd/zh/holiday/holidaySchedule"
    holiday_set = set()
    try:
        r = requests.get(url, timeout=10).json()
        if "data" in r:
            for item in r["data"]:
                raw_date = item[0] if isinstance(item, list) else item.get("Date", "")
                parts = re.findall(r'\d+', raw_date)
                if len(parts) == 3:
                    holiday_set.add(datetime.date(int(parts[0])+1911, int(parts[1]), int(parts[2])))
    except: pass
    return holiday_set

CACHED_HOLIDAYS = get_twse_holidays()

def is_trading_day(d):
    return not (d.weekday() >= 5 or d in CACHED_HOLIDAYS)

def next_trading_day(d):
    curr = d + datetime.timedelta(days=1)
    while not is_trading_day(curr):
        curr += datetime.timedelta(days=1)
    return curr

def parse_date(date_str):
    if not date_str: return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7: return datetime.date(int(s[:3])+1911, int(s[3:5]), int(s[5:]))
        elif len(s) == 8: return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except: return None

# ===========================
# 2. 資料抓取
# ===========================
def get_disposal_data():
    all_stocks = []
    headers = {"User-Agent": "Mozilla/5.0"}
    today = datetime.date.today()
    start_str = (today - datetime.timedelta(days=15)).strftime('%Y%m%d')
    end_str = (today + datetime.timedelta(days=30)).strftime('%Y%m%d')

    # 上市
    try:
        url = f"https://www.twse.com.tw/rwd/zh/announcement/punish?response=json&startDate={start_str}&endDate={end_str}"
        data = requests.get(url, headers=headers).json().get("data", [])
        for row in data:
            period_raw = next((str(c) for c in row if "~" in str(c) or "～" in str(c)), "")
            parts = re.split(r"[~～\-]", period_raw)
            if len(parts) >= 2:
                all_stocks.append({
                    "id": row[2].split('.')[0], "name": row[3],
                    "announce": parse_date(row[1]), "start": parse_date(parts[0]), "end": parse_date(parts[1])
                })
    except: pass

    # 上櫃
    try:
        url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
        r = requests.get(url, headers=headers)
        r.encoding = 'utf-8-sig'
        reader = csv.reader(io.StringIO(r.text))
        next(reader, None)
        for row in reader:
            if len(row) < 4: continue
            parts = re.split(r"[~～\-]", row[3])
            if len(parts) >= 2:
                all_stocks.append({
                    "id": row[1], "name": row[2],
                    "announce": parse_date(row[0]), "start": parse_date(parts[0]), "end": parse_date(parts[1])
                })
    except: pass
    return all_stocks

# ===========================
# 3. 主執行
# ===========================
def main():
    tz = pytz.timezone("Asia/Taipei")
    today = datetime.datetime.now(tz).date()
    next_day = next_trading_day(today) if is_trading_day(today) else next_trading_day(today - datetime.timedelta(days=1))

    raw_data = get_disposal_data()
    unique_stocks = {}
    for s in raw_data:
        if s["id"] not in unique_stocks or s["end"] > unique_stocks[s["id"]]["end"]:
            unique_stocks[s["id"]] = s
    
    status_groups = {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []}

    for s in sorted(unique_stocks.values(), key=lambda x: x["id"]):
        resumption_date = next_trading_day(s["end"])
        enter_date = next_trading_day(s["announce"]) if s["announce"] else s["start"]
        info = f"`{s['id']}` {s['name']} ({s['start'].strftime('%m/%d')} ~ {s['end'].strftime('%m/%d')})"

        if today == resumption_date:
            status_groups["today_out"].append(info)
        elif resumption_date == next_day:
            status_groups["tomorrow_out"].append(info)
        elif today == enter_date:
            status_groups["today_in"].append(info)
        elif enter_date <= today <= s["end"]:
            status_groups["still_in"].append(info)

    msg = f"📅 *日期：{today}* {'(休市)' if not is_trading_day(today) else '(開盤)'}\n"
    msg += f"⏩ 下個交易日：{next_day}\n"
    msg += "━━━━━━━━━━━━━━━\n"

    sections = [
        ("🔓 今日出關 (恢復交易)", "today_out"),
        ("⏭️ 明日出關 (最後一天)", "tomorrow_out"),
        ("🔔 今日進關 (首日處置)", "today_in"),
        ("⏳ 處置中股票清單", "still_in")
    ]

    for title, key in sections:
        msg += f"*{title}*\n"
        msg += ("\n".join(status_groups[key]) if status_groups[key] else "無") + "\n"
        msg += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

    print(msg)

    token, chat_id = os.getenv("TG_TOKEN"), os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()
