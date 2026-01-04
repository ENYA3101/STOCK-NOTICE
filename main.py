import requests
import datetime
import os
import csv
import io
import re


def parse_date(date_str):
    if not date_str:
        return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7:  # 民國
            return datetime.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
        elif len(s) == 8:  # 西元
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except:
        return None
    return None


def split_period(raw):
    if not raw:
        return None
    parts = re.split(r"[~～\-]", raw.replace(" ", ""))
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def get_real_data():
    all_stocks = {}
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # =====================
    # 1. TWSE（上市）
    # =====================
    try:
        url = "https://www.twse.com.tw/announcement/punish?response=open_data"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        for row in data:
            # 欄位名稱以實際 open_data 為準
            s_id = row.get("StockNo", "").strip()
            if not s_id.isdigit():
                continue

            period = split_period(row.get("PunishDate", ""))
            if not period:
                continue

            all_stocks[s_id] = {
                "id": s_id,
                "name": row.get("StockName", "").strip(),
                "announce": parse_date(row.get("AnnounceDate")),
                "start": parse_date(period[0]),
                "end": parse_date(period[1]),
                "range": row.get("PunishDate", "").strip(),
            }
    except Exception as e:
        print("TWSE error:", e)

    # =====================
    # 2. TPEx（上櫃）
    # =====================
    try:
        url = (
            "https://www.tpex.org.tw/web/bulletin/"
            "disposal_information/disposal_information_result.php"
            "?l=zh-tw&o=data"
        )
        r = requests.get(url, headers=headers, timeout=10)
        content = r.content.decode("utf-8-sig", errors="ignore")

        for row in csv.reader(io.StringIO(content)):
            # 欄位：公布日[0], 代號[1], 名稱[2], 區間[3]
            if len(row) < 4 or not row[1].isdigit():
                continue

            period = split_period(row[3])
            if not period:
                continue

            s_id = row[1].strip()
            all_stocks[s_id] = {
                "id": s_id,
                "name": row[2].strip(),
                "announce": parse_date(row[0]),
                "start": parse_date(period[0]),
                "end": parse_date(period[1]),
                "range": row[3].strip(),
            }
    except Exception as e:
        print("TPEx error:", e)

    return list(all_stocks.values())


def main():
    today = datetime.date.today()
    stocks = get_real_data()

    new_ann, out_jail, still_in = [], [], []

    for s in stocks:
        if not s["end"]:
            continue

        exit_day = s["end"] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"

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

    print(f"完成！共彙整 {len(stocks)} 筆資料。")


if __name__ == "__main__":
    main()
