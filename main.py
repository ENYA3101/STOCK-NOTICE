import requests
import datetime
import os

# 模擬極度真實的瀏覽器行為
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.tpex.org.tw/',
    'Connection': 'keep-alive'
}

def parse_date(date_str):
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
    try:
        r = requests.get("https://www.twse.com.tw/rwd/zh/announcement/punish?response=json", timeout=15)
        items = r.json().get('data', [])
        for i in items:
            if len(i) < 7: continue
            raw_time = i[6]
            period = raw_time.split('～') if '～' in raw_time else raw_time.split('-')
            if len(period) >= 2:
                all_stocks.append({
                    'id': i[2], 'name': i[3], 
                    'announce': parse_date(i[1]),
                    'start': parse_date(period[0]),
                    'end': parse_date(period[1]),
                    'range': raw_time
                })
    except: pass

    # 2. 抓取上櫃 (TPEx) - 使用備用資料網址並強化連線
    try:
        # 使用櫃買中心另一組 API 介面
        tpex_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
        session = requests.Session() # 使用 Session 保持連線狀態
        r = session.get(tpex_url, headers=HEADERS, timeout=15)
        
        # 如果回傳狀態不是 200，就印出錯誤
        if r.status_code != 200:
            print(f"櫃買中心回傳狀態碼錯誤: {r.status_code}")
            return all_stocks

        data_json = r.json()
        items = data_json.get('aaData', [])
        
        for i in items:
            # i[0]:公布日期, i[1]:代號, i[2]:名稱, i[3]:處置期間
            if len(i) < 4: continue
            period = i[3].split('-')
            if len(period) >= 2:
                all_stocks.append({
                    'id': i[1], 'name': i[2], 
                    'announce': parse_date(i[0]),
                    'start': parse_date(period[0]),
                    'end': parse_date(period[1]),
                    'range': i[3]
                })
        print(f"成功抓取上櫃資料：{len(items)} 筆")
    except Exception as e:
        print(f"上櫃連線依舊失敗: {e}")
    
    return all_stocks

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_ann = [] 
    out_jail = []      
    still_in = []         

    for s in stocks:
        if not s['end']: continue
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        if exit_day == today:
            out_jail.append(info)
        elif s['announce'] == today:
            new_ann.append(f"🔔 {info}")
        
        if s['end'] >= today:
            if not any(s['id'] in x for x in new_ann):
                still_in.append(info)

    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_ann) if new_ann else "無") + "\n\n"
    msg += "【🔓 本日出關股票】\n" + ("\n".join(out_jail) if out_jail else "無") + "\n\n"
    msg += "【⏳ 正在處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})
    print(f"任務完成：共處理 {len(stocks)} 筆數據。")

if __name__ == "__main__":
    main()
