import requests
import datetime
import os

def parse_date(date_str):
    """全自動日期辨識：支援 115/01/01, 2026/01/01, 20260101"""
    if not date_str: return None
    s = str(date_str).strip().replace("/", "").replace("-", "").replace(" ", "")
    try:
        if len(s) == 7: # 民國格式: 1150101
            y = int(s[:3]) + 1911
            return datetime.date(y, int(s[3:5]), int(s[5:]))
        elif len(s) == 8: # 西元格式: 20260101
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
        return None
    except:
        return None

def get_real_data():
    all_stocks = []
    # 1. 抓取上櫃 (TPEx)
    try:
        r = requests.get("https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw", timeout=15)
        data = r.json().get('aaData', [])
        for i in data:
            if len(i) < 4: continue
            dates = i[3].split('-')
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce': parse_date(i[0]),
                'end': parse_date(dates[1]), 
                'range': i[3]
            })
    except: pass

    # 2. 抓取上市 (TWSE)
    try:
        r = requests.get("https://www.twse.com.tw/rwd/zh/announcement/punish?response=json", timeout=15)
        items = r.json().get('data', [])
        for i in items:
            if len(i) < 5: continue
            # 證交所 API 欄位：0:公告日, 1:代號, 2:名稱, 4:結束日
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce': parse_date(i[0]),
                'end': parse_date(i[4]), 
                'range': f"{i[3]}-{i[4]}"
            })
    except: pass
    return all_stocks

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_announcement = [] 
    out_of_jail = []      
    still_in = []         

    for s in stocks:
        # 只要結束日期沒解析出來，就跳過
        if not s['end']: continue
        
        # 公告日解析失敗沒關係，只有「今日新公告」會失效，不影響「處置中」
        exit_date = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['range']}"
        
        # 比對邏輯
        if s.get('announce') == today:
            new_announcement.append(f"🔔 {info}")
        
        if exit_date == today:
            out_of_jail.append(info)
        elif s['end'] >= today:
            still_in.append(info)

    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_announcement) if new_announcement else "無") + "\n\n"
    msg += "【本日出關】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【所有處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})

if __name__ == "__main__":
    main()
