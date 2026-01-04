import requests
import datetime
import os
import csv
import io
import re

def parse_date(date_str):
    if not date_str: return None
    # 移除所有非數字字元
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
    # 支援 ~ 、 ～ 、 - 作為分隔符
    parts = re.split(r"[~～\-]", str(raw).replace(" ", ""))
    return (parts[0], parts[1]) if len(parts) >= 2 else None

def next_trading_day(d):
    """ 推算下一個交易日 (跳過週末) """
    if d.weekday() == 4: return d + datetime.timedelta(days=3) # 五 -> 一
    if d.weekday() == 5: return d + datetime.timedelta(days=2) # 六 -> 一
    if d.weekday() == 6: return d + datetime.timedelta(days=1) # 日 -> 一
    return d + datetime.timedelta(days=1)

def get_real_data():
    all_stocks = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # 設定查詢範圍：往前找 7 天 (確保抓到剛結束的)，往後找 30 天 (抓未來的)
    today = datetime.date.today()
    start_str = (today - datetime.timedelta(days=7)).strftime('%Y%m%d')
    end_str = (today + datetime.timedelta(days=30)).strftime('%Y%m%d')

    # =====================
    # 1. TWSE（上市）- 加入日期參數 & 模糊搜尋
    # =====================
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish"
    params = {
        "response": "json",
        "startDate": start_str,
        "endDate": end_str
    }
    
    try:
        r = requests.get(twse_url, params=params, headers=headers, timeout=15)
        if r.status_code == 200:
            json_data = r.json()
            rows = json_data.get("data", [])
            for row in rows:
                # 欄位通常是: 0序號, 1公告日, 2代號, 3名稱 ...
                if len(row) < 5: continue
                
                s_id = str(row[2]).strip().split('.')[0] # 處理 1618.0
                s_name = str(row[3]).strip()
                
                # 自動尋找含有 "~" 的欄位作為日期區間 (解決欄位位移問題)
                raw_range = ""
                for col in row:
                    col_str = str(col)
                    if "~" in col_str or "～" in col_str:
                        raw_range = col_str.strip()
                        break
                
                period = split_period(raw_range)
                
                if s_id.isdigit() and period:
                    all_stocks.append({
                        "id": s_id,
                        "name": s_name,
                        "announce": parse_date(row[1]),
                        "start": parse_date(period[0]),
                        "end": parse_date(period[1]),
                        "market": "上市",
                    })
    except Exception as e:
        print(f"上市資料解析錯誤: {e}")

    # =====================
    # 2. TPEx（上櫃）
    # =====================
    try:
        # 上櫃通常列出當前生效的，比較少有歷史查詢 API，直接抓當前列表
        tpex_url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
        r = requests.get(tpex_url, headers=headers, timeout=15)
        r.encoding = 'utf-8-sig' # 處理 BOM
        
        # 轉成 CSV 讀取
        reader = csv.reader(io.StringIO(r.text))
        next(reader, None) # 跳過表頭

        for row in reader:
            if len(row) < 4: continue
            s_id = row[1].strip()
            # 上櫃欄位通常固定
            period = split_period(row[3])
            
            if s_id and period:
                all_stocks.append({
                    "id": s_id,
                    "name": row[2].strip(),
                    "announce": parse_date(row[0]),
                    "start": parse_date(period[0]),
                    "end": parse_date(period[1]),
                    "market": "上櫃",
                })
    except Exception as e:
        print(f"上櫃資料解析錯誤: {e}")

    return all_stocks

def main():
    today = datetime.date.today()
    # today = datetime.date(2026, 1, 4) # 測試用: 模擬週日
    
    next_day = next_trading_day(today)
    print(f"DEBUG: 今天={today}, 下個交易日={next_day}")

    stocks = get_real_data()

    result = {
        "上市": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
        "上櫃": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
    }
    
    # 去重 (API 撈一段時間範圍可能會重複抓到同一檔股票不同日期的公告，取最新的)
    # 使用字典以 (market, id) 為 key 進行去重，保留 end 日期最晚的
    unique_stocks = {}
    for s in stocks:
        key = (s["market"], s["id"])
        if key not in unique_stocks:
            unique_stocks[key] = s
        else:
            # 如果發現同一檔股票有多筆，保留結束日期比較晚的那筆
            if s["end"] > unique_stocks[key]["end"]:
                unique_stocks[key] = s
    
    stocks = list(unique_stocks.values())
    stocks.sort(key=lambda x: (x["market"], x["id"]))

    for s in stocks:
        if not s["end"]: continue

        market = s["market"]
        info = f"{s['name']}({s['id']})"

        # 真正進關日 = 公告日 + 1個交易日
        enter_date = next_trading_day(s["announce"]) if s["announce"] else s["start"]
        
        # 真正出關日 = 結束日 + 1個交易日
        # 例如：結束日 1/2(五) -> 出關日 1/5(一)
        exit_date  = next_trading_day(s["end"])

        # 邏輯判斷
        if exit_date == today:
            result[market]["today_out"].append(f"🔓 {info}")
        elif exit_date == next_day:
            result[market]["tomorrow_out"].append(f"⏭️ {info}")
        elif enter_date == today:
            result[market]["today_in"].append(f"🔔 {info}")
        elif enter_date <= today <= s["end"]: # 修改：包含 enter_date 當天如果還沒過 end
             result[market]["still_in"].append(f"⏳ {info}")
        elif enter_date > today: # 未來會被關
             # 這裡可以選擇要不要顯示「即將被關」，目前歸類在 today_in 或是忽略
             pass

    # 輸出訊息
    msg = f"📅 報表日期：{today}\n"
    msg += f"下個交易日：{next_day}\n\n"

    for market in ["上市", "上櫃"]:
        msg += f"【{market}處置動態】\n"
        msg += "🔓 今日出關: " + (", ".join(result[market]["today_out"]) or "無") + "\n"
        msg += "⏭️ 明日出關: " + (", ".join(result[market]["tomorrow_out"]) or "無") + "\n"
        msg += "🔔 今日進關: " + (", ".join(result[market]["today_in"]) or "無") + "\n"
        msg += "⏳ 處置中: " + (", ".join(result[market]["still_in"]) or "無") + "\n\n"

    print(msg)

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg}
        )

if __name__ == "__main__":
    main()
