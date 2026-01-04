import requests
import datetime
import os
import csv
import io
import time

def parse_date(date_str):
    """強力解析：支援 115/01/01、2026/01/01 或 20260101"""
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
    all_stocks = {} # 使用字典避免重複
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    today = datetime.date.today()

    # 1. 抓取上市 (TWSE) - 回溯 5 天確保資料完整
    for i in range(5):
        target_date = (today - datetime.timedelta(days=i)).strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/zh/announcement/punish?response=csv&date={target_date}"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 100:
                # 使用 utf-8-sig 處理可能的 BOM 頭，若失敗則用 cp950
                try:
                    content = r.content.decode('utf-8-sig')
                except:
                    content = r.content.decode('cp950', errors='ignore')
                
                cr = csv.reader(io.StringIO(content))
                for row in cr:
                    # 上市欄位索引：[1]公布日, [2]代號, [3]名稱, [6]起迄時間
                    if len(row) > 6 and row[2].strip().isdigit():
                        raw_range = row[6]
                        period = raw_range.split('～') if '～' in raw_range else raw_range.split('-')
                        if len(period) >= 2:
                            s_id = row[2].strip()
                            all_stocks[s_id] = {
                                'id': s_id, 'name': row[3].strip(),
                                'announce': parse_date(row[1]),
                                'start': parse_date(period[0]), 'end': parse_date(period[1]),
                                'range': raw_range
                            }
        except: pass

    # 2. 抓取上櫃 (TPEx)
    try:
        url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw&o=csv"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            try:
                content = r.content.decode('utf-8-sig')
            except:
                content = r.content.decode('cp950', errors='ignore')
            
            cr = csv.reader(io.StringIO(content))
            for row in cr:
                # 上櫃欄位索引：[1]公布日, [2]代號, [3]名稱, [4]起迄時間
                if len(row) > 4 and row[2].strip().isdigit():
                    raw_range = row[4]
                    period = raw_range.split('~') if '~' in raw_range else raw_range.split('-')
                    if len(period) >= 2:
                        s_id = row[2].strip()
                        all_stocks[s_id] = {
                            'id': s_id, 'name': row[3].strip(),
                            'announce': parse_date(row[1]),
                            'start': parse_date(period[0]), 'end': parse_date(period[1]),
                            'range': raw_range
                        }
    except: pass
    
    return list(all_stocks.values())

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_ann, out_jail, still_in = [], [], []

    for s in stocks:
        if not s['end']: continue
        
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        # A. 今日出關 (結束日+1 = 今天)
        if exit_day == today:
            out_jail.append(info)
        
        # B. 今日新公告進關 (公告日 = 今天)
        if s['announce'] == today:
            new_ann.append(f"🔔 {info}")
        
        # C. 所有處置中明細 (結束日 >= 今天)
        if s['end'] >= today:
            # 排除已列在今日新公告的，避免重複
            if not any(s['id'] in x for x in new_ann):
                still_in.append(info)

    # 組合訊息
    msg = f"📅 報表日期：{today}\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_ann) if new_ann else "無") + "\n\n"
    msg += "【🔓 本日出關股票】\n" + ("\n".join(out_jail) if out_jail else "無") + "\n\n"
    msg += "【⏳ 所有處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})
    print(f"處理完成，共彙整 {len(stocks)} 筆資料。")

if __name__ == "__main__":
    main()
