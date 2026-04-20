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
    
    # 升級版：優先嘗試用正則抓取 yyyy/mm/dd 或 yyy/mm/dd，可相容未補零格式如 115/4/2
    match = re.search(r'(\d{2,4})[-/](\d{1,2})[-/](\d{1,2})', str(date_str))
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if y < 1911: y += 1911
        try:
            return datetime.date(y, m, d)
        except: pass
            
    # 退回原本純數字邏輯
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
    # 加上較完整的 User-Agent 降低被券商網站阻擋的機率
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    today = datetime.date.today()
    start_str = (today - datetime.timedelta(days=15)).strftime('%Y%m%d')
    end_str = (today + datetime.timedelta(days=30)).strftime('%Y%m%d')

    # ---------------------------
    # 上市
    # ---------------------------
    try:
        url = f"https://www.twse.com.tw/rwd/zh/announcement/punish?response=json&startDate={start_str}&endDate={end_str}"
        resp = requests.get(url, headers=headers, timeout=10)
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

    # ---------------------------
    # 上櫃
    # ---------------------------
    try:
        url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
        r = requests.get(url, headers=headers, timeout=10)
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
        
    # ---------------------------
    # 興櫃 (國票證券)
    # ---------------------------
    try:
        url_ibfs = "https://www.ibfs.com.tw/stock3/measuringstock.aspx?xy=6&xt=1"
        r = requests.get(url_ibfs, headers=headers, timeout=10)
        
        # 不額外依賴 bs4，用 Regex 解析 HTML 表格 <tr> <td>
        trs = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.IGNORECASE | re.DOTALL)
        for tr in trs:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.IGNORECASE | re.DOTALL)
            if len(tds) >= 4:
                # 移除 HTML 標籤取得乾淨文字
                cols = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                
                # 排除表頭等無效行
                if "證券名稱" in cols[0] or "代號" in cols[0]:
                    continue
                
                stock_id, stock_name = None, None
                for text in cols:
                    # 匹配格式: "泰谷(3339)" 或是 "3339 泰谷" (排除數字與括號以抓取名稱)
                    m1 = re.search(r'^([^\d\(\)\s]+)\s*\(?(\d{4,5})\)?$', text)
                    m2 = re.search(r'^(\d{4,5})\s*([^\d\(\)\s]+)$', text)
                    if m1:
                        stock_name, stock_id = m1.group(1).strip(), m1.group(2)
                        break
                    elif m2:
                        stock_id, stock_name = m2.group(1), m2.group(2).strip()
                        break
                
                if not stock_id:
                    continue
                
                # 尋找日期區間 (同一欄位中出現2個日期即視為處置區間)
                for text in cols:
                    dates = re.findall(r'\d{2,4}[-/]\d{1,2}[-/]\d{1,2}', text)
                    if len(dates) >= 2:
                        start_d = parse_date(dates[0])
                        end_d = parse_date(dates[-1])
                        # 公告日通常在表格第一欄
                        announce_d = parse_date(cols[0])
                        
                        if start_d and end_d:
                            all_stocks.append({
                                "id": stock_id, "name": stock_name,
                                "announce": announce_d, 
                                "start": start_d, "end": end_d
                            })
                        break
    except Exception as e:
        print(f"⚠️ 興櫃資料抓取錯誤: {e}")
        
    return all_stocks

# ===========================
# 3. 主執行
# ===========================
def main():
    tz = pytz.timezone("Asia/Taipei")
    today = datetime.datetime.now(tz).date()
    
    if is_trading_day(today):
        next_day = next_trading_day(today)
        market_status = "(開盤)"
    else:
        next_day = next_trading_day(today)
        market_status = "(休市)"

    raw_data = get_disposal_data()
    unique_stocks = {}
    
    for s in raw_data:
        if not s["start"] or not s["end"]: continue
        if s["id"] not in unique_stocks or s["end"] > unique_stocks[s["id"]]["end"]:
            unique_stocks[s["id"]] = s
    
    status_groups = {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []}

    for s in sorted(unique_stocks.values(), key=lambda x: x["id"]):
        resumption_date = next_trading_day(s["end"])
        enter_date = next_trading_day(s["announce"]) if s["announce"] else s["start"]
        
        info = f"<code>{s['id']}</code> {s['name']} ({s['start'].strftime('%m/%d')} ~ {s['end'].strftime('%m/%d')})"

        if today == resumption_date:
            status_groups["today_out"].append(info)
        elif resumption_date == next_day:
            status_groups["tomorrow_out"].append(info)
        elif today == enter_date:
            status_groups["today_in"].append(info)
        elif enter_date <= today <= s["end"]:
            status_groups["still_in"].append(info)

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
    
    print(msg)

    # ===========================
    # 4. Telegram 發送邏輯
    # ===========================
    token = os.getenv("TG_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

    print("-" * 30)
    print(f"Debug: Token 狀態: {'✅ 已讀取' if token else '❌ 未讀取 (None)'}")
    print(f"Debug: ChatID 狀態: {'✅ 已讀取' if chat_id else '❌ 未讀取 (None)'}")

    if not token or not chat_id:
        print("❌ 錯誤：找不到 Telegram 設定。請檢查 GitHub Secrets 或 .env 檔案。")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": msg, 
            "parse_mode": "HTML", 
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
