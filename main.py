import requests
import datetime
import os
import csv
import io
import time

def parse_date(date_str):
    """強力解析日期：支援 115/01/01、2026/01/01 或 20260101"""
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
    all_stocks = {} # 使用字典 ID 當 Key 避免重複
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    today = datetime.date.today()

    # --- 執行 20 天回溯迴圈 ---
    for i in range(20):
        target_date = today - datetime.timedelta(days=i)
        
        # 1. 抓取上市 (TWSE) CSV
        date_twse = target_date.strftime("%Y%m%d")
        try:
            url_twse = f"https://www.twse.com.tw/zh/announcement/punish?response=csv&date={date_twse}"
            r = requests.get(url_twse, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 150:
                content = r.content.decode('utf-8-sig', errors='ignore') if b'\xef\xbb\xbf' in r.content else r.content.decode('cp950', errors='ignore')
                cr = csv.reader(io.StringIO(content))
                for row in cr:
                    # 上市欄位：[1]公布日, [2]代號, [3]名稱, [6]起訖時間
                    if len(row) > 6 and row[2].strip().isdigit():
                        raw_range = row[6].replace(" ", "")
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

        # 2. 抓取上櫃 (TPEx) CSV
        # 櫃買中心日期格式為民國年帶斜線，例如 115/01/02
        date_tpex = f"{target_date.year - 1911}/{target_date.strftime('%m/%d')}"
        try:
            url_tpex = f"https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw&d={date_tpex}&o=csv"
            r = requests.get(url_tpex, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 100:
                content = r.content.decode('utf-8-sig', errors='ignore') if b'\xef\xbb\xbf' in r.content else r.content.decode('cp950', errors='ignore')
                cr = csv.reader(io.StringIO(content))
                for row in cr:
                    # 上櫃欄位：[1]公布日, [2]代號, [3]名稱, [4]起訖時間
                    if len(row) > 4 and row[2].strip().isdigit():
                        raw_range = row[4].replace(" ", "")
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
        
        # 稍微延遲，避免頻繁請求被伺服器暫時封鎖
        if i % 5 == 0: time.sleep(0.5)

    return list(all_stocks.values())

def main():
    today = datetime.date.today()
    stocks = get_real_data()
    
    new_ann, out_jail, still_in = [], [], []

    for s in stocks:
        if not s['end']: continue
        
        exit_day = s['end'] + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) 期間：{s['range']}"
        
        # A. 今日新公告進關 (公布日期 = 今天)
        if s['announce'] == today:
            new_ann.append(f"🔔 {info}")
        
        # B. 本日出關 (出關日 = 今天)
        if exit_day == today:
            out_jail.append(info)
            
        # C. 所有處置中明細 (只要結束日 >= 今天)
        if s['end'] >= today:
            if not any(s['id'] in x for x in new_ann):
                still_in.append(info)

    msg = f"📅 報表日期：{today}\n(已完成 20 日回溯分析)\n\n"
    msg += "【🔔 今日新公告進關】\n" + ("\n".join(new_ann) if new_ann else "無") + "\n\n"
    msg += "【🔓 本日出關股票】\n" + ("\n".join(out_jail) if out_jail else "無") + "\n\n"
    msg += "【⏳ 所有處置中明細】\n" + ("\n".join(still_in) if still_in else "無")

    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg})
    
    print(f"任務完成，彙整 {len(stocks)} 筆數據。")

if __name__ == "__main__":
    main()
