import requests
import datetime
import os

def parse_date(date_str):
    date_str = date_str.strip()
    try:
        if '/' in date_str: # 民國格式
            y, m, d = map(int, date_str.split('/'))
            return datetime.date(y + 1911, m, d)
        else: # 西元格式
            return datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except:
        return None

def get_tpex_data():
    url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
    results = []
    try:
        res = requests.get(url)
        data = res.json().get('aaData', [])
        for item in data:
            dates = item[3].split('-')
            if len(dates) == 2:
                results.append({
                    'id': item[1], 'name': item[2],
                    'end': parse_date(dates[1]),
                    'raw_range': item[3]
                })
    except: pass
    return results

def get_twse_data():
    api_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    results = []
    try:
        res = requests.get(api_url)
        data = res.json().get('data', [])
        for item in data:
            end_date = parse_date(item[4])
            results.append({
                'id': item[1], 'name': item[2],
                'end': end_date,
                'raw_range': f"{item[3]}-{item[4]}"
            })
    except: pass
    return results

def main():
    # ======= 模擬測試區 =======
    # 強制設定日期為 2025 年 12 月 29 日
    today = datetime.date(2025, 12, 29) 
    # =========================
    
    all_stocks = get_tpex_data() + get_twse_data()
    out_of_jail = []
    in_disposal = []

    for s in all_stocks:
        if not s['end']: continue
        exit_date = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['raw_range']}"
        
        if exit_date == today:
            out_of_jail.append(info)
        elif s['end'] >= today:
            in_disposal.append(info)

    out_of_jail = list(dict.fromkeys(out_of_jail))
    in_disposal = list(dict.fromkeys(in_disposal))

    msg = f"🧪【模擬測試報告】\n📅 測試日期：{today}\n\n"
    msg += "【本日出關】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【處置中】\n" + ("\n".join(in_disposal) if in_disposal else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})
    print(msg)

if __name__ == "__main__":
    main()
