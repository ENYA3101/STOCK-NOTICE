import requests
import datetime
import os
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def parse_date(date_str):
    """強力解析日期：支援 115/01/01 或 20260101"""
    if not date_str: return None
    s = "".join(filter(str.isdigit, str(date_str)))
    try:
        if len(s) == 7: # 民國: 1150101
            return datetime.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
        elif len(s) == 8: # 西元: 20260101
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
        return None
    except:
        return None

def get_real_data():
    all_stocks = []
    
    # 1. 抓取上市 (TWSE) 
    # 欄位順序：編號[0], 公布日期[1], 證券代號[2], 證券名稱[3], 累計[4], 處置條件[5], 處置起迄時間[6]...
    try:
        r = requests.get("https://www.twse.com.tw/rwd/zh/announcement/punish?response=json", timeout=15)
        items = r.json().get('data', [])
        for i in items:
            if len(i) < 7: continue
            
            # 解析「處置起迄時間」，通常格式為 2025/12/29～2026/01/12
            raw_time = i[6]
            period = raw_time.split('～') if '～' in raw_time else raw_time.split('-')
            
            if len(period) >= 2:
                all_stocks.append({
                    'id': i[2],           # 證券代號
                    'name': i[3],         # 證券名稱
                    'announce': parse_date(i[1]), # 公布日期
                    'start': parse_date(period[0]),
                    'end': parse_date(period[1]),
                    'range': raw_time     # 處置起迄時間原始文字
                })
    except Exception as e:
        print(f"上市抓取失敗: {e}")

    # 2. 抓取上櫃 (TPEx)
    # 欄位順序：公布日期[0], 證券代號[1], 證券名稱[2], 處置起迄時間[3]...
    try:
r = requests.get(
    "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php",
    params={
        "l": "zh-tw",
        "response": "json"
    },
    headers=HEADERS,
    timeout=15
)
        data = r.json().get('aaData', [])
        for i in data:
            if len(i) < 4: continue
            period = i[3].split('-')
            all_stocks.append({
                'id': i[1], 
                'name': i[2], 
                'announce': parse_date(i[0]),
                'start': parse_date(period[0]),
                'end': parse_date(period[1]),
                'range': i[3]
            })
    except Exception as e:
        print(f"上櫃抓取失敗: {e}")
    
    return all_stocks

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_announcement = [] # 今日新公告進關
    out_of_jail = []      # 本日出關
    still_in = []         # 處置中

    for s in stocks:
        if not s['end']: continue
        
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        # A. 判斷今日出關 (結束日+1 = 今天)
        if exit_day == today:
            out_of_jail.append(info)
        
        # B. 判斷今日新公告進關 (公布日期 = 今天)
        elif s['announce'] == today:
            new_announcement.append(f"🔔 {info}")
        
        # C. 判斷處置中 (只要還在處置結束日之前)
        if s['end'] >= today:
            # 避免重複放入「今日新公告」的股票
            if not any(s['id'] in x for x in new_announcement):
                still_in.append(info)

    # 組合訊息
    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_announcement) if new_announcement else "無") + "\n\n"
    msg += "【🔓 本日出關股票】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【⏳ 正在處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})
    print(f"處理完成：共 {len(stocks)} 筆數據。")

if __name__ == "__main__":
    main()