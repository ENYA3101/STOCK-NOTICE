import requests
import datetime
import os

def parse_date(date_str):
    date_str = date_str.strip().replace(" ", "").replace("-", "")
    try:
        if '/' in date_str: # 民國格式: 115/01/01
            parts = date_str.split('/')
            year = int(parts[0]) + 1911
            return datetime.date(year, int(parts[1]), int(parts[2]))
        elif len(date_str) == 8: # 西元格式: 20260101
            return datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except Exception as e:
        print(f"日期解析失敗 ({date_str}): {e}")
        return None

def get_real_data():
    tpex_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    all_stocks = []
    
    # 抓取上櫃 (TPEx)
    try:
        r = requests.get(tpex_url, timeout=15)
        data = r.json().get('aaData', [])
        print(f"DEBUG: 櫃買中心 API 回傳 {len(data)} 筆")
        for i in data:
            dates = i[3].split('-')
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce': parse_date(i[0]),
                'end': parse_date(dates[1]), 
                'range': i[3]
            })
    except Exception as e: print(f"櫃買抓取錯誤: {e}")

    # 抓取上市 (TWSE)
    try:
        r = requests.get(twse_url, timeout=15)
        data = r.json().get('data', [])
        print(f"DEBUG: 證交所 API 回傳 {len(data)} 筆")
        for i in data:
            start_d, end_d = i[3], i[4]
            formatted_range = f"{start_d[:4]}/{start_d[4:6]}/{start_d[6:]}-{end_d[:4]}/{end_d[4:6]}/{end_d[6:]}"
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce': parse_date(i[0]),
                'end': parse_date(end_d), 
                'range': formatted_range
            })
    except Exception as e: print(f"證交所抓取錯誤: {e}")

    return all_stocks

def main():
    today = datetime.date.today()
    print(f"--- 開始執行任務，今日日期: {today} ---")
    
    stocks = get_real_data()
    new_announcement = [] 
    out_of_jail = []      
    still_in = []         

    for s in stocks:
        if not s['end'] or not s['announce']: continue
        
        exit_date = s['end'] + datetime.timedelta(days=1)
        
        # DEBUG: 查看每一筆的比對狀態
        # print(f"檢查: {s['name']} | 結束:{s['end']} | 狀態:{'OK' if s['end'] >= today else '已過期'}")
        
        if s['announce'] == today:
            new_announcement.append(f"🔔 {s['name']}({s['id']}) {s['range']}")
        
        if exit_date == today:
            out_of_jail.append(f"{s['name']}({s['id']}) {s['range']}")
        elif s['end'] >= today:
            still_in.append(f"{s['name']}({s['id']}) {s['range']}")

    # 組合訊息
    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_announcement) if new_announcement else "無") + "\n\n"
    msg += "【本日出關】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【所有處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})
    
    print("--- 任務結束，訊息已發送 ---")

if __name__ == "__main__":
    main()
