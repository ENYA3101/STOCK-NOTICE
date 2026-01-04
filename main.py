import requests
import datetime
import os
import csv
import io
import re

def parse_date(date_str):
    if not date_str: return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:  # 民國 1141231
            year = int(s[:3]) + 1911
            return datetime.date(year, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:  # 西元 20260101
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except:
        return None
    return None

def split_period(raw):
    if not raw: return None
    # 支援多種分隔符號並移除空格
    parts = re.split(r"[~～\-]", str(raw).replace(" ", ""))
    return (parts[0], parts[1]) if len(parts) >= 2 else None

def next_trading_day(d):
    """ 簡單推算下一個可能的交易日 (不考慮國定假日，僅處理週末) """
    if d.weekday() == 4: return d + datetime.timedelta(days=3) # 五 -> 一
    if d.weekday() == 5: return d + datetime.timedelta(days=2) # 六 -> 一
    if d.weekday() == 6: return d + datetime.timedelta(days=1) # 日 -> 一
    return d + datetime.timedelta(days=1)

def get_real_data():
    all_stocks = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # 1. TWSE（上市）
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    try:
        r = requests.get(twse_url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            for row in data:
                # 欄位索引可能因 API 變動，通常：1:日期, 2:代號, 3:名稱, 6:期間
                if len(row) < 7: continue
                s_id = str(row[2]).strip()
                name = str(row[3]).strip()
                raw_range = str(row[6]).strip()
                period = split_period(raw_range)
                
                if s_id and period:
                    all_stocks.append({
                        "id": s_id, "name": name, "announce": parse_date(row[1]),
                        "start": parse_date(period[0]), "end": parse_date(period[1]),
                        "range": raw_range, "market": "上市"
                    })
    except Exception as e:
        print(f"上市抓取失敗: {e}")

    # 2. TPEx（上櫃）
    tpex_url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
    try:
        r = requests.get(tpex_url, headers=headers, timeout=15)
        r.encoding = 'utf-8-sig'
        reader = csv.reader(io.StringIO(r.text))
        next(reader, None) # 跳過標題
        for row in reader:
            if len(row) < 4: continue
            s_id = row[1].strip()
            period = split_period(row[3])
            if s_id and period:
                all_stocks.append({
                    "id": s_id, "name": row[2].strip(), "announce": parse_date(row[0]),
                    "start": parse_date(period[0]), "end": parse_date(period[1]),
                    "range": row[3].strip(), "market": "上櫃"
                })
    except Exception as e:
        print(f"上櫃抓取失敗: {e}")

    return all_stocks

def main():
    today = datetime.date.today()
    next_day = next_trading_day(today)
    stocks = get_real_data()

    # 格式化輸出容器
    result = {
        "上市": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
        "上櫃": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
    }

    for s in stocks:
        if not s["end"] or not s["announce"]: continue
        
        market = s["market"]
        info = f"{s['name']}({s['id']})"
        
        # 處置邏輯：公告日隔天開始，結束日隔天恢復正常
        enter_date = next_trading_day(s["announce"])
        exit_date = next_trading_day(s["end"])

        if exit_date == today:
            result[market]["today_out"].append(f"🔓 {info}")
        elif exit_date == next_day:
            result[market]["tomorrow_out"].append(f"⏭️ {info}")
        elif enter_date == today:
            result[market]["today_in"].append(f"🔔 {info}")
        elif enter_date < today <= s["end"]:
            result[market]["still_in"].append(f"⏳ {info}")

    # 組合訊息
    msg = f"📅 報表日期：{today}\n"
    msg += "------------------------\n"

    for m in ["上市", "上櫃"]:
        msg += f"【{m}處置股動態】\n"
        msg += "🔓 今日出關: " + (", ".join(result[m]["today_out"]) or "無") + "\n"
        msg += "⏭️ 明日出關: " + (", ".join(result[m]["tomorrow_out"]) or "無") + "\n"
        msg += "🔔 今日進關: " + (", ".join(result[m]["today_in"]) or "無") + "\n"
        msg += "⏳ 處置中: " + (", ".join(result[m]["still_in"]) or "無") + "\n\n"

    print(msg)

    # Telegram 發送
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg})

if __name__ == "__main__":
    main()
