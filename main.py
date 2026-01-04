import requests
import datetime
import os
import csv
import io
import re

def parse_date(date_str):
    if not date_str:
        return None
    # 移除所有非數字字元
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
    if not raw:
        return None
    # 支援多種分隔符號
    parts = re.split(r"[~～\-]", raw.replace(" ", ""))
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None

def get_real_data():
    all_stocks = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/91.0.4472.124 Safari/537.36"
    }

    # =====================
    # 1. TWSE（上市）
    # =====================
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    try:
        r = requests.get(twse_url, headers=headers, timeout=15)
        if r.status_code == 200:
            json_data = r.json()
            rows = json_data.get("data", [])

            for row in rows:
                # 欄位：0 公告日, 1 代號, 2 名稱, 3 起日, 4 迄日
                if len(row) < 5:
                    continue

                s_id = str(row[1]).strip()
                if not s_id.isdigit():
                    continue

                start_d = str(row[3])
                end_d = str(row[4])

                start_date = parse_date(start_d)
                end_date = parse_date(end_d)
                if not start_date or not end_date:
                    continue

                all_stocks[s_id] = {
                    "id": s_id,
                    "name": str(row[2]).strip(),
                    "announce": parse_date(row[0]),
                    "start": start_date,
                    "end": end_date,
                    "range": f"{start_d}~{end_d}",
                    "market": "上市",
                }
    except Exception as e:
        print(f"證交所抓取錯誤: {e}")

    # =====================
    # 2. TPEx（上櫃）- 保持原樣 (CSV 格式)
    # =====================
    try:
        url = (
            "https://www.tpex.org.tw/web/bulletin/"
            "disposal_information/disposal_information_result.php"
            "?l=zh-tw&o=data"
        )
        r = requests.get(url, headers=headers, timeout=10)
        content = r.content.decode("utf-8-sig", errors="ignore")

        reader = csv.reader(io.StringIO(content))
        next(reader, None) # 跳過表頭

        for row in reader:
            if len(row) < 4:
                continue

            s_id = row[1].strip()
            if not s_id.isdigit():
                continue

            raw_range = row[3].strip()
            period = split_period(raw_range)
            if not period:
                continue

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
        print("TPEx error:", e)

    return list(all_stocks.values())

# main 函式保持不變...
    return list(all_stocks.values())


def main():
    today = datetime.date.today()
    stocks = get_real_data()

    new_ann, out_jail, still_in = [], [], []

    for s in stocks:
        if not s["end"]:
            continue

        exit_day = s["end"] + datetime.timedelta(days=1)
        info = f"[{s['market']}] {s['name']}({s['id']}) 期間：{s['range']}"

        if s["announce"] == today:
            new_ann.append(f"🔔 {info}")

        if exit_day == today:
            out_jail.append(info)

        if s["end"] >= today and not any(s["id"] in x for x in new_ann):
            still_in.append(info)

    msg = (
        f"📅 報表日期：{today}\n\n"
        "【🔔 今日新公告進關】\n"
        + ("\n".join(new_ann) if new_ann else "無")
        + "\n\n【🔓 本日出關股票】\n"
        + ("\n".join(out_jail) if out_jail else "無")
        + "\n\n【⏳ 所有處置中明細】\n"
        + ("\n".join(still_in) if still_in else "無")
    )

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg}
        )

    print(f"完成！共彙整 {len(stocks)} 筆（上市＋上櫃）資料。")


if __name__ == "__main__":
    main()
