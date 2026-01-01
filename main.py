import requests
import datetime
import os
import re

def parse_date(date_str):
    """處理日期轉換，支援 113/12/26 (民國) 或 20241226 (西元)"""
    date_str = date_str.strip()
    try:
        if '/' in date_str: # 民國格式: 113/12/26
            y, m, d = map(int, date_str.split('/'))
            return datetime.date(y + 1911, m, d)
        else: # 西元格式: 20241226
            return datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except:
        return None

def get_tpex_data():
    """抓取上櫃 (TPEx) 處置股票"""
    url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
    results = []
    try:
        res = requests.get(url)
        data = res.json().get('aaData', [])
        for item in data:
            # item[1]:代號, item[2]:名稱, item[3]:日期區間 "113/12/12-113/12/25"
            dates = item[3].split('-')
            if len(dates) == 2:
                results.append({
                    'id': item[1], 'name': item[2],
                    'start': parse_date(dates[0]), 'end': parse_date(dates[1]),
                    'raw_range': item[3]
                })
    except Exception as e:
        print(f"TPEx Error: {e}")
    return results

def get_twse_data():
    """抓取上市 (TWSE) 處置股票"""
    # 證交所處置股票資訊 API
    url = "https://www.twse.com.tw/zh/announcement/punish.html" # 網頁版
    # 實際上證交所 API 較細碎，這裡使用公告 API 並過濾
    api_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    results = []
    try:
        res = requests.get(api_url)
        data = res.json().get('data', [])
        for item in data:
            # item[1]:代號, item[2]:名稱, item[3]:起始, item[4]:結束
            start_date = parse_date(item[3])
            end_date = parse_date(item[4])
            results.append({
                'id': item[1], 'name': item[2],
                'start': start_date, 'end': end_date,
                'raw_range': f"{item[3]}-{item[4]}"
            })
    except Exception as e:
        print(f"TWSE Error: {e}")
    return results

def main():
    today = datetime.date.today()
    all_stocks = get_tpex_data() + get_twse_data()
    
    out_of_jail = []
    in_disposal = []

    for s in all_stocks:
        if not s['end']: continue
        
        # 定義：出關日是結束日的隔天
        exit_date = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['raw_range']}"
        
        if exit_date == today:
            out_of_jail.append(info)
        elif s['end'] >= today:
            in_disposal.append(info)

    # 移除重複 (有時候兩邊資料會重疊)
    out_of_jail = list(dict.fromkeys(out_of_jail))
    in_disposal = list(dict.fromkeys(in_disposal))

    # 訊息組合
    msg = f"📅 報表日期：{today}\n\n"
    msg += "【本日出關】\n"
    msg += "\n".join(out_of_jail) if out_of_jail else "無"
    msg += "\n\n【處置中】\n"
    msg += "\n".join(in_disposal) if in_disposal else "無"

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})
    else:
        print(msg)

if __name__ == "__main__":
    main()
