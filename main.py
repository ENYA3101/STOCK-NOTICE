import requests
import datetime
import os
import csv
import io
import time
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


def split_period(raw_range):
    if not raw_range:
        return None
    parts = re.split(r'[~～\-]', raw_range.replace(" ", ""))
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def get_real_data():
    all_stocks = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    today = datetime.date.today()

    for i in range(21):
        target_date = today - datetime.timedelta(days=i)

        # =====================
        # 1. 上市 TWSE
        # =====================
        try:
            date_twse = target_date.strftime("%Y%m%d")
            url_twse = f"https://www.twse.com.tw/zh/announcement/punish?response=csv&date={date_twse}"
            r = requests.get(url_twse, headers=headers, timeout=10)

            if r.status_code == 200 and len(r.content) > 100:
                content = (
                    r.content.decode('utf-8-sig', errors='ignore')
                    if b'\xef\xbb\xbf' in r.content
                    else r.content.decode('cp950', errors='ignore')
                )

                for row in csv.reader(io.StringIO(content)):
                    if len(row) > 6 and row[2].strip().isdigit():
                        period = split_period(row[6])
                        if not period:
                            continue

                        s_id = row[2].strip()
                        all_stocks[s_id] = {
                            'id': s_id,
                            'name': row[3].strip(),
                            'announce': parse_date(row[1]),
                            'start': parse_date(period[0]),
                            'end': parse_date(period[1]),
                            'range': row[6].strip()
                        }
        except Exception as e:
            print("TWSE error:", e)

        # =====================
        # 2. 上櫃 TPEx
        # =====================
        try:
            date_tpex = f"{target_date.year - 1911}/{target_date.strftime('%m/%d')}"
            url_tpex = (
                "https://www.tpex.org.tw/web/stock/margin_trading/"
                "disposal/disposal_result.php"
                f"?l=zh-tw&d={date_tpex}&o=csv"
            )
            r = requests.get(url_tpex, headers=headers, timeout=10)

            if r.status_code == 200 and len(r.content) > 100:
                content = (
                    r.content.decode('utf-8-sig', errors='ignore')
                    if b'\xef\xbb\xbf' in r.content
                    else r.content.decode('cp950', errors='ignore')
                )

                for row in csv.reader(io.StringIO(content)):
                    if len(row) > 4 and row[2].strip().isdigit():
                        period = split_period(row[4])
                        if not period:
                            continue

                        s_id = row[2].strip()
                        all_stocks[s_id] = {
                            'id': s_id,
                            'name': row[3].strip(),
                            'announce': parse_date(row[1]),
                            'start': parse_date(period[0]),
                            'end': parse_date(period[1]),
                            'range': row[4].strip()
                        }
        except Exception as e:
            print("TPEx error:", e)

        if i % 5 == 0:
            time.sleep(0.3)

    return list(all_stocks.values())


def main():
    today = datetime.date.today()
    stocks = get_real_data()

    new_ann, out_jail, still_in = [], [], []

    for s in stocks:
        if not s['end']:
            continue

        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"

        if s['announce'] == today:
            new_ann.append(f"🔔 {info}")

        if exit_day == today:
            out_jail.append(info)

        if s['end'] >= today and not any(s['id'] in x for x in new_ann):
            still_in.append(info)

    msg = (
        f"📅 報表日期：{today}\n(歷史 20 日資料彙整)\n\n"
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

    print(f"完成！共彙整 {len(stocks)} 筆不重複資料。")


if __name__ == "__main__":
    main()
