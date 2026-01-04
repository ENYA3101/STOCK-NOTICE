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
    today = datetime.date.today()
    # today = datetime.date(2026, 1, 4)  # 測試用

    stocks = get_real_data()

    result = {
        "上市": {
            "today_out": [],
            "tomorrow_out": [],
            "today_in": [],
            "still_in": []
        },
        "上櫃": {
            "today_out": [],
            "tomorrow_out": [],
            "today_in": [],
            "still_in": []
        }
    }

    stocks.sort(key=lambda x: (x['market'], x['id']))

    for s in stocks:
        if not s["announce"] or not s["end"]:
            continue

        market = s["market"]
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"

        enter_date = s["announce"] + datetime.timedelta(days=1)
        exit_date  = s["end"] + datetime.timedelta(days=1)

        # 1️⃣ 今日出關
        if exit_date == today:
            result[market]["today_out"].append(f"🔓 {info}")
            continue

        # 2️⃣ 明日出關（含週末特例）
        if (
            exit_date == today + datetime.timedelta(days=1)
            or (
                s["end"].weekday() == 4      # 星期五
                and today.weekday() == 6     # 星期日
            )
        ):
            result[market]["tomorrow_out"].append(f"⏭️ {info}")
            continue

        # 3️⃣ 今日被關（真正進關日）
        if enter_date == today:
            result[market]["today_in"].append(f"🔔 {info}")
            continue

        # 4️⃣ 還在處置中
        if enter_date < today <= s["end"]:
            result[market]["still_in"].append(f"⏳ {info}")
            continue

    # ===== 組訊息 =====
    def block(title, items):
        return f"【{title}】\n" + ("\n".join(items) if items else "無")

    msg = f"📅 報表日期：{today}\n\n"

    for market in ["上市", "上櫃"]:
        msg += (
            f"🟥 {market}\n"
            + block("🔓 今日出關", result[market]["today_out"]) + "\n\n"
            + block("⏭️ 明日出關", result[market]["tomorrow_out"]) + "\n\n"
            + block("🔔 今日被關", result[market]["today_in"]) + "\n\n"
            + block("⏳ 還在處置", result[market]["still_in"]) + "\n\n"
        )

    print(msg)

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
