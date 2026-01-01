import requests
import datetime
import os

def parse_date(date_str):
    """處理民國或西元日期格式"""
    date_str = date_str.strip().replace(" ", "").replace("-", "")
    try:
        if '/' in date_str: # 民國: 114/12/31
            parts = date_str.split('/')
            return datetime.date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
        elif len(date_str) == 8: # 西元: 20251231
            return datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except:
        return None

def get_real_data():
    """從兩大交易所抓取資料，並提取公告日期"""
    tpex_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    
    all_stocks = []
    
    # 1. 抓取上櫃 (TPEx)
    try:
        r = requests.get(tpex_url, timeout=15)
        data = r.json().get('aaData', [])
        for i in data:
            # i[0]:公告日期, i[1]:代號, i[2]:名稱, i[3]:處置期間
            dates = i[3].split('-')
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce': parse_date(i[0]), # 公告日期
                'end': parse_date(dates[1]), 
                'range': i[3]
            })
    except: pass

    # 2. 抓取上市 (TWSE)
    try:
        r = requests.get(twse_url, timeout=15)
        data = r.json().get('data', [])
        for i in data:
            # i[0]:公告日期, i[1]:代號, i[2]:名稱, i[3]:起始, i[4]:結束
            start_d, end_d = i[3], i[4]
            formatted_range = f"{start_d[:4]}/{start_d[4:6]}/{start_d[6:]}-{end_d[:4]}/{end_d[4:6]}/{end_d[6:]}"
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce': parse_date(i[0]), # 公告日期
                'end': parse_date(end_d), 
                'range': formatted_range
            })
    except: pass

    return all_stocks

def main():
    today = datetime.date.today()
    # 測試用：today = datetime.date(2025, 12, 28) # 假設這天有新公告
    
    stocks = get_real_data()
    new_announcement = [] # 今日新公告
    out_of_jail = []      # 本日出關
    still_in = []         # 處置中

    for s in stocks:
        if not s['end'] or not s['announce']: continue
        
        exit_date = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['range']}"
        
        # 邏輯判斷
        if s['announce'] == today:
            new_announcement.append(f"🔔 {info}")
        
        if exit_date == today:
            out_of_jail.append(info)
        elif s['end'] >= today:
            # 處置中的清單
            still_in.append(info)

    # 組合訊息
    msg = f"📅 報表日期：{today}\n\n"
    
    msg += "【🔔 今日新公告進關】\n"
    msg += "\n".join(new_announcement) if new_announcement else "無"
    msg += "\n\n"
    
    msg += "【本日出關】\n"
    msg += "\n".join(out_of_jail) if out_of_jail else "無"
    msg += "\n\n"
    
    msg += "【所有處置中明細】\n"
    msg += "\n".join(still_in) if still_in else "無"

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})

if __name__ == "__main__":
    main()
