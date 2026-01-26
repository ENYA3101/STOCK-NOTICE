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
    except Exception as e:
        print(f"⚠️ 抓取假期失敗 (非致命錯誤): {e}")
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
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for row in data:
                period_raw = next((str(c) for c in row if "~" in str(c) or "～" in str(c)), "")
                parts = re.split(r"[~～\-]", period_raw)
                if len(parts) >= 2:
                    all_stocks.append({
                        "id": row[2].split('.')[0], "name": row[3],
                        "announce": parse_date(row[1]), "start": parse_date(parts[0]), "end": parse_date(parts[1])
                    })
    except Exception as e:
        print(f"⚠️ 上市資料抓取錯誤: {e}")

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
    except Exception as e:
        print(f"⚠️ 上櫃資料抓取錯誤: {e}")
        
    return all_stocks

# ===========================
# 3. 主執行
# ===========================
def main():
    # 設定時區為台北，避免 GitHub 伺服器時間誤差
    tz = pytz.timezone("Asia/Taipei")
    today = datetime.datetime.now(tz).date()
    
    # 判斷是否為交易日，決定「下個交易日」
    if is_trading_day(today):
        next_day = next_trading_day(today)
        market_status = "(開盤)"
    else:
        # 如果今天是假日，我們還是顯示資訊，但標註休市
        next_day = next_trading_day(today)
        market_status = "(休市)"

    raw_data = get_disposal_data()
    unique_stocks = {}
    
    # 過濾重複資料，取結束日期最晚的
    for s in raw_data:
        if not s["start"] or not s["end"]: continue
        if s["id"] not in unique_stocks or s["end"] > unique_stocks[s["id"]]["end"]:
            unique_stocks[s["id"]] = s
    
    status_groups = {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []}

    for s in sorted(unique_stocks.values(), key=lambda x: x["id"]):
        resumption_date = next_trading_day(s["end"])
        enter_date = next_trading_day(s["announce"]) if s["announce"] else s["start"]
        
        # 使用 HTML 格式的 Code 標籤 <code>...</code>
        info = f"<code>{s['id']}</code> {s['name']} ({s['start'].strftime('%m/%d')} ~ {s['end'].strftime('%m/%d')})"

        if today == resumption_date:
            status_groups["today_out"].append(info)
        elif resumption_date == next_day:
            status_groups["tomorrow_out"].append(info)
        elif today == enter_date:
            status_groups["today_in"].append(info)
        elif enter_date <= today <= s["end"]:
            status_groups["still_in"].append(info)

    # 組建訊息 (使用 HTML 語法)
    msg = f"📅 <b>日期：{today}</b> {market_status}\n"
    msg += f"⏩ 下個交易日：{next_day}\n"
    msg += "━━━━━━━━━━━━━━━\n"

    sections = [
        ("🔓 今日出關 (恢復交易)", "today_out"),
        ("⏭️ 明日出關 (最後一天)", "tomorrow_out"),
        ("🔔 今日進關 (首日處置)", "today_in"),
        ("⏳ 處置中股票清單", "still_in")
    ]

    has_data = False
    for title, key in sections:
        msg += f"<b>{title}</b>\n"
        if status_groups[key]:
            msg += "\n".join(status_groups[key]) + "\n"
            has_data = True
        else:
            msg += "無\n"
        msg += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    
    # 在 Console 印出結果，方便在 GitHub Actions 檢查
    print(msg)

    # ===========================
    # 4. Telegram 發送邏輯 (增強版)
    # ===========================
    
    # 讀取環境變數 (請確保 GitHub Secrets 名稱與此處一致)
    # 這裡預設讀取 TG_TOKEN，如果沒有則嘗試讀取 TELEGRAM_TOKEN (相容性寫法)
    token = os.getenv("TG_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

    print("-" * 30)
    print(f"Debug: Token 狀態: {'✅ 已讀取' if token else '❌ 未讀取 (None)'}")
    print(f"Debug: ChatID 狀態: {'✅ 已讀取' if chat_id else '❌ 未讀取 (None)'}")

    if not token or not chat_id:
        print("❌ 錯誤：找不到 Telegram 設定。請檢查 GitHub Secrets 或 .env 檔案。")
        # 不拋出錯誤，讓程式正常結束，但會紀錄 Log
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": msg, 
            "parse_mode": "HTML", # 改用 HTML 避免 Markdown 解析錯誤
            "disable_web_page_preview": True
        }
        
        print("🚀 正在發送訊息給 Telegram...")
        resp = requests.post(url, json=payload, timeout=10)
        
        if resp.status_code == 200:
            print("✅ Telegram 訊息發送成功！")
        else:
            print(f"❌ 發送失敗。HTTP狀態碼: {resp.status_code}")
            print(f"❌ 錯誤回應: {resp.text}")
            
    except Exception as e:
        print(f"❌ 連線發生例外錯誤: {e}")

if __name__ == "__main__":
    main()
