import requests
import datetime
import os

# 設定 Header 模擬瀏覽器，防止被櫃買中心擋掉
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
    except Exception as e:
        print(f"上市抓取失敗: {e}")

    # 2. 抓取上櫃 (TPEx) - 加入 HEADERS 並修正索引
    try:
        # 換成更直接的 JSON 資料接口
        tpex_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
        r = requests.get(tpex_url, headers=HEADERS, timeout=15)
        
        # 檢查是否成功抓取到 JSON
        data_json = r.json()
        items = data_json.get('aaData', [])
        
        print(f"DEBUG: 櫃買中心 API 回傳 {len(items)} 筆原始資料")

        for i in items:
            # i[0]:公告日期, i[1]:代號, i[2]:名稱, i[3]:處置期間
            if len(i) < 4: continue
            
            # 解析上櫃的期間格式： "114/12/29-115/01/12"
            raw_range = i[3]
            period = raw_range.split('-')
            
            if len(period) >= 2:
                all_stocks.append({
                    'id': i[1], 
                    'name': i[2], 
                    'announce': parse_date(i[0]),
                    'start': parse_date(period[0]),
                    'end': parse_date(period[1]),
                    'range': raw_range
                })
    except Exception as e:
        print(f"上櫃抓取失敗: {e}")
    
    return all_stocks

def main():
    # 為了測試今天 1/4 的情況，如果 API 還有資料，這會抓得到
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_announcement = [] 
    out_of_jail = []      
    still_in = []         

    for s in stocks:
        if not s['end']: continue
        
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        if exit_day == today:
            out_of_jail.append(info)
        elif s['announce'] == today:
            new_announcement.append(f"🔔 {info}")
        
        # 修正：只要今天還在處置結束日(含)之前，就算處置中
        if s['end'] >= today:
            if not any(s['id'] in x for x in new_announcement):
                still_in.append(info)

    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_announcement) if new_announcement else "無") + "\n\n"
    msg += "【🔓 本日出關股票】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【⏳ 正在處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})
    print(f"處理完成：共 {len(stocks)} 筆數據。")

if __name__ == "__main__":
    main()
