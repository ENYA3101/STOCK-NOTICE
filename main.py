import requests
import datetime
import os
import csv
import io

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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Encoding': 'gzip, deflate' # 告訴伺服器我們可以處理壓縮檔
    }
    
    # 1. 抓取上市 (TWSE) CSV
    try:
        twse_csv_url = "https://www.twse.com.tw/zh/announcement/punish?response=csv"
        r = requests.get(twse_csv_url, headers=headers, timeout=15)
        if r.status_code == 200:
            # 自動處理編碼 (上市 CSV 通常是 cp950)
            content = r.content.decode('cp950', errors='ignore')
            cr = csv.reader(io.StringIO(content))
            for i in cr:
                if len(i) > 6 and i[2].strip().isdigit():
                    period = i[6].split('～') if '～' in i[6] else i[6].split('-')
                    if len(period) >= 2:
                        all_stocks.append({
                            'id': i[2], 'name': i[3], 
                            'announce': parse_date(i[1]),
                            'start': parse_date(period[0]),
                            'end': parse_date(period[1]),
                            'range': i[6]
                        })
    except Exception as e:
        print(f"上市 CSV 抓取異常: {e}")

    # 2. 抓取上櫃 (TPEx) CSV - 強化版
    try:
        tpex_csv_url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw&o=csv"
        r = requests.get(tpex_csv_url, headers=headers, timeout=15)
        
        if r.status_code == 200:
            # 解決 0x89 錯誤：先嘗試用 utf-8，失敗則用 cp950，並忽略非法字元
            try:
                content = r.content.decode('utf-8')
            except UnicodeDecodeError:
                content = r.content.decode('cp950', errors='ignore')
            
            cr = csv.reader(io.StringIO(content))
            for i in cr:
                # 櫃買 CSV 欄位：公布日期[0], 代號[1], 名稱[2], 期間[3]
                if len(i) > 3 and i[1].strip().isdigit():
                    period = i[3].split('-')
                    if len(period) >= 2:
                        all_stocks.append({
                            'id': i[1], 'name': i[2], 
                            'announce': parse_date(i[0]),
                            'start': parse_date(period[0]),
                            'end': parse_date(period[1]),
                            'range': i[3]
                        })
            print(f"DEBUG: 上櫃 CSV 解析成功，目前總筆數: {len(all_stocks)}")
    except Exception as e:
        print(f"上櫃 CSV 解析失敗: {e}")
    
    return all_stocks

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_ann = [] # 今日新公告
    out_jail = [] # 今日出關
    still_in = [] # 處置中

    for s in stocks:
        if not s['end']: continue
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        # A. 今日出關 (結束日+1 = 今天)
        if exit_day == today:
            out_jail.append(info)
        
        # B. 今日新公告 (公告日 = 今天)
        elif s['announce'] == today:
            new_ann.append(f"🔔 {info}")
        
        # C. 正在處置中 (只要結束日大於等於今天)
        if s['end'] >= today:
            if not any(s['id'] in x for x in new_ann):
                still_in.append(info)

    # 組合訊息
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
