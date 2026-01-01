import requests
import datetime
import os

def parse_date(date_str):
    """最強力解析：只管找出數字部分"""
    if not date_str: return None
    # 只留下數字
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
    # 1. 抓取上櫃 (TPEx)
    try:
        r = requests.get("https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw", timeout=15)
        data = r.json().get('aaData', [])
        for i in data:
            if len(i) < 4: continue
            end_d = parse_date(i[3].split('-')[-1]) # 取區間最後一個日期
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce_raw': str(i[0]),
                'end': end_d, 
                'range': i[3]
            })
    except: pass

    # 2. 抓取上市 (TWSE)
    try:
        r = requests.get("https://www.twse.com.tw/rwd/zh/announcement/punish?response=json", timeout=15)
        items = r.json().get('data', [])
        for i in items:
            if len(i) < 5: continue
            # 證交所：0:公告日, 1:代號, 2:名稱, 4:結束日
            all_stocks.append({
                'id': i[1], 'name': i[2], 
                'announce_raw': str(i[0]),
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
        # 如果結束日解析失敗，這筆才跳過
        if not s['end']:
            continue
        
        exit_date = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['range']}"
        
        # --- 寬鬆比對公告日 ---
        # 只要公告日期字串包含今天日期的數字，就當作是今日公告
        today_str_roc = f"{today.year-1911}/{today.month:02d}/{today.day:02d}"
        today_str_iso = today.strftime("%Y%m%d")
        
        if today_str_roc in s['announce_raw'] or today_str_iso in s['announce_raw']:
            new_announcement.append(f"🔔 {info}")
        
        # --- 處置狀態比對 ---
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
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})
    
    # 增加終極 Debug：印出到底哪些股票被判定過期
    print(f"總共抓到 {len(stocks)} 筆，篩選後剩餘 {len(still_in)} 筆處置中。")

if __name__ == "__main__":
    main()
