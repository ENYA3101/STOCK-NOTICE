import requests
import datetime
import os
import csv
import io
import re

def parse_date(date_str):
    if not date_str: return None
    # 移除所有非數字字元 (例如 114/12/31 -> 1141231)
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:  # 民國 1120101
            return datetime.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:  # 西元 20230101
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except:
        return None
    return None

def split_period(raw):
    if not raw: return None
    # 支援 ~ 、 ～ 、 - 作為分隔符
    parts = re.split(r"[~～\-]", str(raw).replace(" ", ""))
    return (parts[0], parts[1]) if len(parts) >= 2 else None

def get_real_data():
    all_stocks = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # =====================
    # 1. TWSE（上市）- 根據 CSV 結構調整
    # =====================
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    try:
        r = requests.get(twse_url, headers=headers, timeout=15)
        if r.status_code == 200:
            json_data = r.json()
            rows = json_data.get("data", [])
            for row in rows:
                # 參考 CSV 欄位: 1 公告日, 2 代號, 3 名稱, 6 起訖時間
                if len(row) < 7: continue
                
                s_id = str(row[2]).strip().split('.')[0] # 處理可能出現的 1528.0
                raw_range = str(row[6]).strip()
                period = split_period(raw_range)
                
                if s_id.isdigit() and period:
                    all_stocks[s_id] = {
                        "id": s_id,
                        "name": str(row[3]).strip(),
                        "announce": parse_date(row[1]),
                        "start": parse_date(period[0]),
                        "end": parse_date(period[1]),
                        "range": raw_range,
                        "market": "上市",
                    }
    except Exception as e:
        print(f"上市資料解析錯誤: {e}")

    # =====================
    # 2. TPEx（上櫃）
    # =====================
    try:
        tpex_url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
        r = requests.get(tpex_url, headers=headers, timeout=15)
        content = r.content.decode("utf-8-sig", errors="ignore")
        reader = csv.reader(io.StringIO(content))
        next(reader, None) # 跳過表頭

        for row in reader:
            # 參考 CSV 欄位: 0 公告日, 1 代號, 2 名稱, 3 起訖時間
            if len(row) < 4: continue

            s_id = row[1].strip()
            raw_range = row[3].strip()
            period = split_period(raw_range)
            
            if s_id.isdigit() and period:
                all_stocks[s_id] = {
                    "id": s_id,
                    "name": row[2].strip(),
                    "announce": parse_date(row[0]),
                    "start": parse_date(period[0]),
                    "end": parse_date(period[1]),
                    "range": raw_range,
                    "market": "上櫃",
                }
    except Exception as e:
        print(f"上櫃資料解析錯誤: {e}")

    return list(all_stocks.values())

def main():
    today = datetime.date.today(2026, 1, 2)
    # 測試用：若今天要看 1/5 的報表，可手動設定 today = datetime.date(2026, 1, 5)
    
    stocks = get_real_data()
    new_ann, out_jail, still_in = [], [], []
    processed_ids = set()

    # 排序：按市場與代號
    stocks.sort(key=lambda x: (x['market'], x['id']))

    for s in stocks:
        if not s["end"]: continue
        
        info = f"[{s['market']}] {s['name']}({s['id']}) 期間：{s['range']}"
        
        # 1. 今日新公告
        if s["announce"] == today:
            new_ann.append(f"🔔 {info}")
            processed_ids.add(s["id"])

        # 2. 本日出關 (迄日的隔天)
        exit_day = s["end"] + datetime.timedelta(days=1)
        if exit_day == today:
            out_jail.append(f"🔓 {info}")

        # 3. 處置中 (且不是今天才剛公告的)
        if s["start"] <= today <= s["end"] and s["id"] not in processed_ids:
            still_in.append(f"⏳ {info}")

    msg = (
        f"📅 報表日期：{today}\n\n"
        "【🔔 今日新公告進關】\n" + ("\n".join(new_ann) if new_ann else "無") + "\n\n"
        "【🔓 本日出關股票】\n" + ("\n".join(out_jail) if out_jail else "無") + "\n\n"
        "【⏳ 其他處置中明細】\n" + ("\n".join(still_in) if still_in else "無")
    )

    print(msg) # 終端機預覽

    # Telegram 發送
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg}
        )

if __name__ == "__main__":
    main()
