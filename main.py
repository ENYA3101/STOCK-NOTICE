import requests
import datetime
import os
import csv
import io
import re

# ===========================
# 日期處理工具
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
    """ 推算下一個交易日 (簡單跳過週末) """
    if d.weekday() == 4: return d + datetime.timedelta(days=3) # 五 -> 一
    if d.weekday() == 5: return d + datetime.timedelta(days=2) # 六 -> 一
    if d.weekday() == 6: return d + datetime.timedelta(days=1) # 日 -> 一
    return d + datetime.timedelta(days=1)

def format_md(d):
    """ 將日期轉為 MM/DD 格式 """
    return d.strftime('%m/%d') if d else "??"

# ===========================
# 資料抓取核心
# ===========================
def get_real_data():
    all_stocks = []
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # 設定查詢範圍：前後多抓一點，確保抓到剛結束或未來的
    today = datetime.date.today() - datetime.timedelta(days=1)  # 前一天
    start_str = (today - datetime.timedelta(days=10)).strftime('%Y%m%d')
    end_str = (today + datetime.timedelta(days=30)).strftime('%Y%m%d')

    # --- 1. TWSE（上市） ---
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
                
                # 模糊搜尋日期區間
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
    except Exception as e:
        print(f"上市錯誤: {e}")

    # --- 2. TPEx（上櫃） ---
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
    except Exception as e:
        print(f"上櫃錯誤: {e}")

    return all_stocks

# ===========================
# 主程式
# ===========================
def main():
    # 使用前一天作為資料日期
    today = datetime.date.today() - datetime.timedelta(days=1)
    next_day = next_trading_day(today)

    raw_stocks = get_real_data()

    # 資料去重 (保留結束日最晚的)
    unique_stocks = {}
    for s in raw_stocks:
        key = (s["market"], s["id"])
        if key not in unique_stocks or s["end"] > unique_stocks[key]["end"]:
            unique_stocks[key] = s
    
    # 排序：先上市櫃 -> 再代號
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

        # 修正日期判斷，不再多加一天
        enter_date = s["start"]
        exit_date  = s["end"]

        if exit_date == today:
            result[market]["today_out"].append(info)
        elif exit_date == next_day:
            result[market]["tomorrow_out"].append(info)
        elif enter_date == today:
            result[market]["today_in"].append(info)
        elif enter_date <= today <= exit_date:
            result[market]["still_in"].append(info)

    # 組合訊息函式
    def build_section(title, items):
        if not items:
            return f"{title}: 無"
        return f"{title}:\n" + "\n".join(items)

    msg = f"📅 日期：{today}\n"
    msg += f"⏩ 下個交易日：{next_day}\n\n"

    for market in ["上市", "上櫃"]:
        msg += f"🟥【{market}】\n"
        msg += build_section("🔓 今日出關", result[market]["today_out"]) + "\n\n"
        msg += build_section("⏭️ 明日出關", result[market]["tomorrow_out"]) + "\n\n"
        msg += build_section("🔔 今日進關", result[market]["today_in"]) + "\n\n"
        msg += build_section("⏳ 處置中", result[market]["still_in"]) + "\n\n"
        msg += "--------------------\n"

    print(msg)

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        )

if __name__ == "__main__":
    main()