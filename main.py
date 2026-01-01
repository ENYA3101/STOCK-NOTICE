import requests
import datetime
import os

def parse_date(date_str):
    if not date_str: return None
    date_str = str(date_str).strip().replace(" ", "").replace("-", "")
    try:
        if '/' in date_str: # 民國: 115/01/01
            parts = date_str.split('/')
            return datetime.date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
        elif len(date_str) == 8: # 西元: 20260101
            return datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except:
        return None

def get_real_data():
    all_stocks = []
    
    # 1. 抓取上櫃 (TPEx)
    tpex_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
    try:
        r = requests.get(tpex_url, timeout=15)
        if r.status_code == 200:
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
    except Exception as e:
        print(f"櫃買中心抓取跳過 (假日可能休眠): {e}")

    # 2. 抓取上市 (TWSE)
    twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish?response=json"
    try:
        r = requests.get(twse_url, timeout=15)
        if r.status_code == 200:
            json_data = r.json()
            # 修正解析邏輯：確保 data 存在且為清單
            items = json_data.get('data', [])
            for i in items:
                # 證交所的欄位：0:公告日, 1:代號, 2:名稱, 3:起始日, 4:結束日
                if len(i) < 5: continue
                start_d, end_d = str(i[3]), str(i[4])
                formatted_range = f"{start_d[:4]}/{start_d[4:6]}/{start_d[6:]}-{end_d[:4]}/{end_d[4:6]}/{end_d[6:]}"
                all_stocks.append({
                    'id': i[1], 'name': i[2], 
                    'announce': parse_date(i[0]),
                    'end': parse_date(end_d), 
                    'range': formatted_range
                })
    except Exception as e:
        print(f"證交所抓取錯誤: {e}")

    return all_stocks

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_announcement = [] 
    out_of_jail = []      
    still_in = []         

    for s in stocks:
        if not s['end'] or not s['announce']: continue
        
        exit_date = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['range']}"
        
        if s['announce'] == today:
            new_announcement.append(f"🔔 {info}")
        
        if exit_date == today:
            out_of_jail.append(info)
        elif s['end'] >= today:
            still_in.append(info)

    # 組合訊息
    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_announcement) if new_announcement else "無") + "\n\n"
    msg += "【本日出關】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【所有處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})
    print(f"任務完成。總共處理 {len(stocks)} 筆資料。")

if __name__ == "__main__":
    main()
