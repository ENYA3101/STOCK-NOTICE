import requests
import datetime
import os
import json

# 更換模擬瀏覽器的 Header，使用更通用的設定
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.tpex.org.tw/zh-tw/announce/market/disposal.html'
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

    # 2. 抓取上櫃 (TPEx) - 修正路徑與解析邏輯
    try:
        # 使用這個更穩定的 API 路徑
        tpex_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
        r = requests.get(tpex_url, headers=HEADERS, timeout=15)
        r.encoding = 'utf-8' # 強制編碼避免亂碼
        
        # 檢查是否為 JSON，若不是則跳過
        try:
            data_json = r.json()
        except:
            print(f"上櫃 API 回傳內容非 JSON (可能是維護中)")
            return all_stocks

        items = data_json.get('aaData', [])
        print(f"DEBUG: 櫃買中心 API 成功回傳 {len(items)} 筆原始資料")

        for i in items:
            # 根據你提供的表格內容：公布日期[0], 證券代號[1], 證券名稱[2], 起訖時間[3]
            if len(i) < 4: continue
            
            raw_range = i[3]
            # 櫃買中心有時日期中間沒空格，需謹慎分割
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
        print(f"上櫃連線異常: {e}")
    
    return all_stocks

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_announcement = [] 
    out_of_jail = []      
    still_in = []         

    for s in stocks:
        if not s['end']: continue
        
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        # A. 出關日 (結束日+1 = 今天)
        if exit_day == today:
            out_of_jail.append(info)
        
        # B. 今日新公告 (公告日 = 今天)
        elif s['announce'] == today:
            new_announcement.append(f"🔔 {info}")
        
        # C. 正在處置中 (含今天)
        if s['end'] >= today:
            # 排除已列入今日新公告的
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
