import requests
import datetime
import os
import csv
import io
import re
import pytz

# ===========================
# 📅 2026 台灣國定假日表 (需手動維護或串接 API)
# ===========================
# 格式：datetime.date(2026, 月, 日)
TW_HOLIDAYS_2026 = {
    datetime.date(2026, 1, 1),   # 元旦
    # 農曆春節 (預估，請依行事曆調整)
    datetime.date(2026, 2, 16), datetime.date(2026, 2, 17), 
    datetime.date(2026, 2, 18), datetime.date(2026, 2, 19), datetime.date(2026, 2, 20),
    datetime.date(2026, 2, 28),  # 228
    datetime.date(2026, 4, 3),   # 兒童節
    datetime.date(2026, 4, 4),   # 清明節
    datetime.date(2026, 5, 1),   # 勞動節
    datetime.date(2026, 6, 19),  # 端午節
    datetime.date(2026, 9, 25),  # 中秋節
    datetime.date(2026, 10, 10), # 國慶日
}

# ===========================
# 日期處理工具
# ===========================
def parse_date(date_str):
    if not date_str: return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:
            year = int(s[:3]) + 1911
            return datetime.date(year, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except:
        return None
    return None

def split_period(raw):
    if not raw: return None
    parts = re.split(r"[~～\-]", str(raw).replace(" ", ""))
    return (parts[0], parts[1]) if len(parts) >= 2 else None

def next_trading_day(d):
    """ 
    推算下一個交易日 
    邏輯：先 +1 天，如果是週末或國定假日，就繼續 +1，直到是工作日 
    """
    d = d + datetime.timedelta(days=1)
    while True:
        # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        is_weekend = d.weekday() >= 5
        is_holiday = d in TW_HOLIDAYS_2026
        
        if is_weekend or is_holiday:
            d = d + datetime.timedelta(days=1)
        else:
            break
    return d

def format_md(d):
    return d.strftime('%m/%d') if d else "??"

# ===========================
# 資料抓取核心 (保持不變)
# ===========================
def get_real_data():
    # ... (你的原始程式碼保持不變) ...
    # 為了版面整潔，這裡省略，請保留你原本的 get_real_data 函數內容
    all_stocks = []
    headers = {"User-Agent": "Mozilla/5.0"}

    today = datetime.date.today()
    start_str = (today - datetime.timedelta(days=10)).strftime('%Y%m%d')
    end_str = (today + datetime.timedelta(days=30)).strftime('%Y%m%d')

    # 1. TWSE
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish"
    params = {"response": "json", "startDate": start_str, "endDate": end_str}
    try:
        r = requests.get(twse_url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            rows = r.json().get("data", [])
            for row in rows:
                if len(row) < 5: continue
                s_id = str(row[2]).strip().split('.')[0]
                s_name = str(row[3]).strip()
                raw_range = ""
                for col in row:
                    if "~" in str(col) or "～" in str(col):
                        raw_range = str(col).strip()
                        break
                period = split_period(raw_range)
                if s_id.isdigit() and period:
                    all_stocks.append({
                        "id": s_id, "name": s_name, "market": "上市",
                        "announce": parse_date(row[1]),
                        "start": parse_date(period[0]),
                        "end": parse_date(period[1])
                    })
    except Exception: pass

    # 2. TPEx
    try:
        tpex_url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
        r = requests.get(tpex_url, headers=headers, timeout=10)
        r.encoding = 'utf-8-sig'
        reader = csv.reader(io.StringIO(r.text))
        next(reader, None)
        for row in reader:
            if len(row) < 4: continue
            s_id = row[1].strip()
            period = split_period(row[3])
            if s_id and period:
                all_stocks.append({
                    "id": s_id, "name": row[2].strip(), "market": "上櫃",
                    "announce": parse_date(row[0]),
                    "start": parse_date(period[0]),
                    "end": parse_date(period[1])
                })
    except Exception: pass

    return all_stocks

# ===========================
# 主程式 (邏輯修正區)
# ===========================
def main():
    tz = pytz.timezone("Asia/Taipei")
    today = datetime.datetime.now(tz).date()
    
    # 用迴圈邏輯計算真正的明天交易日 (不僅僅是 +1)
    next_day = next_trading_day(today)

    raw_stocks = get_real_data()

    unique_stocks = {}
    for s in raw_stocks:
        key = (s["market"], s["id"])
        if key not in unique_stocks or s["end"] > unique_stocks[key]["end"]:
            unique_stocks[key] = s
    
    stocks = sorted(unique_stocks.values(), key=lambda x: (x["market"], x["id"]))

    result = {
        "上市": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
        "上櫃": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
    }

    for s in stocks:
        if not s["end"]: continue

        market = s["market"]
        date_range = f"({format_md(s['start'])} ~ {format_md(s['end'])})"
        info = f"`{s['id']}` {s['name']} {date_range}"

        # 核心修正：計算「真正恢復交易日」
        resumption_date = next_trading_day(s["end"]) 
        
        # 核心修正：計算「開始處置日」
        enter_date = next_trading_day(s["announce"]) if s["announce"] else s["start"]

        # --- 分類邏輯 ---
        
        # 1. 今日出關：意思是「今天」是「恢復交易日」
        if today == resumption_date:
            result[market]["today_out"].append(info)
            
        # 2. 明日出關：意思是「今天」是處置的最後一天
        #    (也就是說，恢復交易日 == 下一個交易日)
        elif resumption_date == next_day:
            result[market]["tomorrow_out"].append(info)
            
        # 3. 今日進關
        elif today == enter_date:
            result[market]["today_in"].append(info)
            
        # 4. 處置中：今天在開始與結束之間 (且不是最後一天，最後一天會被上面條件2抓走，如果不希望重疊要調整順序)
        elif enter_date <= today <= s["end"]:
            # 這裡會有一個小重疊：如果是處置最後一天，它既是「明日出關」也是「處置中」。
            # 通常看盤軟體會希望在「明日出關」看到它，但也希望知道它還在關。
            # 如果你希望「明日出關」的股票不要顯示在「處置中」，加一個判斷：
            if resumption_date != next_day: 
                result[market]["still_in"].append(info)
            # 或者你想重複顯示也可以把 if 拿掉

    def build_section(title, items):
        if not items: return f"{title}: 無"
        return f"{title}:\n" + "\n".join(items)

    msg = f"📅 日期：{today}\n"
    msg += f"⏩ 下個交易日：{next_day}\n\n"

    for market in ["上市", "上櫃"]:
        msg += f"🟥【{market}】\n"
        msg += build_section("🔓 今日出關 (恢復交易)", result[market]["today_out"]) + "\n\n"
        msg += build_section("⏭️ 明日出關 (處置最後一天)", result[market]["tomorrow_out"]) + "\n\n"
        msg += build_section("🔔 今日進關", result[market]["today_in"]) + "\n\n"
        msg += build_section("⏳ 處置中", result[market]["still_in"]) + "\n\n"
        msg += "--------------------\n"

    print(msg)

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        )

if __name__ == "__main__":
    main()
