import requests
import datetime
import os
import csv
import io
import re
import pytz

# ===========================
# 1. 自動抓取證交所休市表 (API)
# ===========================
def get_twse_holidays():
    """
    從證交所抓取該年度休市日清單 (只抓平日的休市日)
    URL: https://www.twse.com.tw/rwd/zh/holiday/holidaySchedule
    """
    url = "https://www.twse.com.tw/rwd/zh/holiday/holidaySchedule"
    holiday_set = set()
    
    try:
        # 預設抓取當年度
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if "data" in data:
            for item in data["data"]:
                # item["Date"] 格式通常是 "114/01/01" (民國年/月/日)
                raw_date = item.get("Date", "")
                if raw_date:
                    parts = raw_date.split('/')
                    if len(parts) == 3:
                        # 民國轉西元
                        y = int(parts[0]) + 1911
                        m = int(parts[1])
                        d = int(parts[2])
                        holiday_set.add(datetime.date(y, m, d))
    except Exception as e:
        print(f"⚠️ 無法抓取休市表 (將僅依賴週末判斷): {e}")
    
    return holiday_set

# 全域變數：執行時先抓一次，避免重複請求
CACHED_HOLIDAYS = get_twse_holidays()

# ===========================
# 2. 日期處理工具
# ===========================
def parse_date(date_str):
    if not date_str: return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:  # 民國 1140102
            year = int(s[:3]) + 1911
            return datetime.date(year, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:  # 西元 20250102
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
        # 0=Mon, ..., 5=Sat, 6=Sun
        is_weekend = d.weekday() >= 5
        is_holiday = d in CACHED_HOLIDAYS
        
        if is_weekend or is_holiday:
            d = d + datetime.timedelta(days=1)
        else:
            break
    return d

def is_trading_day(d):
    """ 判斷某天是否為交易日 """
    if d.weekday() >= 5: return False
    if d in CACHED_HOLIDAYS: return False
    return True

def format_md(d):
    return d.strftime('%m/%d') if d else "??"

# ===========================
# 3. 資料抓取核心
# ===========================
def get_real_data():
    all_stocks = []
    headers = {"User-Agent": "Mozilla/5.0"}

    today = datetime.date.today()
    start_str = (today - datetime.timedelta(days=10)).strftime('%Y%m%d')
    end_str = (today + datetime.timedelta(days=30)).strftime('%Y%m%d')

    # --- TWSE（上市） ---
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

    # --- TPEx（上櫃） ---
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
# 4. 主程式
# ===========================
def main():
    tz = pytz.timezone("Asia/Taipei")
    today = datetime.datetime.now(tz).date()
    
    # 檢查今天是否休市 (如果是休市日，可以在這裡決定是否不發送訊息，或在訊息中標註)
    market_is_open = is_trading_day(today)
    
    # 計算「明天」的定義 (下一個交易日)
    if market_is_open:
        next_day = next_trading_day(today)
    else:
        # 如果今天是假日，next_day 就是下一個開盤日
        # 例如今天是週六，next_day 就是週一
        next_day = next_trading_day(today - datetime.timedelta(days=1))

    raw_stocks = get_real_data()

    # 資料去重 (保留結束日最晚的)
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

        # --- 核心邏輯 ---
        # 1. 恢復交易日 = 處置結束日(s['end']) 的「下一個交易日」
        resumption_date = next_trading_day(s["end"]) 
        
        # 2. 開始處置日 = 公告日的「下一個交易日」
        enter_date = next_trading_day(s["announce"]) if s["announce"] else s["start"]

        # --- 分類 ---
        if today == resumption_date:
            # 只有在今天真的是交易日時，才算「今日出關」
            # 如果今天休市(例如跑程式抓資料備用)，它依然算今日出關，但實際交易是下次開盤
            result[market]["today_out"].append(info)
            
        elif resumption_date == next_day:
            # 明天(下個交易日)恢復交易 = 今天是坐牢最後一天
            result[market]["tomorrow_out"].append(info)
            
        elif today == enter_date:
            result[market]["today_in"].append(info)
            
        elif enter_date <= today <= s["end"]:
            # 避免重複顯示在「明日出關」和「處置中」
            if resumption_date != next_day:
                result[market]["still_in"].append(info)

    def build_section(title, items):
        if not items: return f"{title}: 無"
        return f"{title}:\n" + "\n".join(items)

    # 訊息標頭
    msg = f"📅 日期：{today} " + ("(休市)" if not market_is_open else "(開盤)") + "\n"
    msg += f"⏩ 下個交易日：{next_day}\n\n"

    for market in ["上市", "上櫃"]:
        msg += f"🟥【{market}】\n"
        msg += build_section("🔓 今日出關 (恢復交易)", result[market]["today_out"]) + "\n\n"
        msg += build_section("⏭️ 明日出關 (處置最後一天)", result[market]["tomorrow_out"]) + "\n\n"
        msg += build_section("🔔 今日進關", result[market]["today_in"]) + "\n\n"
        msg += build_section("⏳ 處置中", result[market]["still_in"]) + "\n\n"
        msg += "--------------------\n"

    print(msg)

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
            )
        except Exception as e:
            print(f"Telegram 發送失敗: {e}")

if __name__ == "__main__":
    main()
