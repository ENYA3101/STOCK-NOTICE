import requests
import datetime
import os
import csv
import io
import re
import pytz

# ===========================
# 1. 設定與工具函式
# ===========================

# 設定時區
TW_TZ = pytz.timezone("Asia/Taipei")

def get_twse_holidays():
    """
    抓取證交所休市日 (自動切換民國年對應的西元)
    """
    url = "https://www.twse.com.tw/rwd/zh/holiday/holidaySchedule"
    holiday_set = set()
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if "data" in data:
            for item in data["data"]:
                # Date 格式通常為 "115/01/01" 或 "2026/01/01"
                raw_date = item.get("Date", "")
                if raw_date:
                    parts = raw_date.split('/')
                    if len(parts) == 3:
                        y = int(parts[0])
                        # 如果是民國年 (例如 115)，轉西元
                        if y < 1911:
                            y += 1911
                        m = int(parts[1])
                        d = int(parts[2])
                        holiday_set.add(datetime.date(y, m, d))
    except Exception as e:
        print(f"⚠️ 無法抓取休市表 (僅依賴週末判斷): {e}")
    return holiday_set

# 快取休市日資料
CACHED_HOLIDAYS = get_twse_holidays()

def is_trading_day(date_obj):
    """ 判斷是否為交易日 (排除週末與休市日) """
    if date_obj.weekday() >= 5: # 5=週六, 6=週日
        return False
    if date_obj in CACHED_HOLIDAYS:
        return False
    return True

def get_next_trading_day(current_date):
    """ 取得下一個交易日 """
    next_d = current_date + datetime.timedelta(days=1)
    while not is_trading_day(next_d):
        next_d += datetime.timedelta(days=1)
    return next_d

def parse_roc_date(date_str):
    """ 解析民國字串 (例如 1150102) 轉 date 物件 """
    if not date_str: return None
    s = "".join(filter(str.isdigit, str(date_str)))
    if len(s) == 7:
        y = int(s[:3]) + 1911
        m = int(s[3:5])
        d = int(s[5:])
        return datetime.date(y, m, d)
    return None

def split_period(raw_str):
    """ 分割日期區間字串 (支援 ~ 或 -) """
    if not raw_str: return None, None
    clean_str = str(raw_str).replace(" ", "")
    # 常見分隔符號
    parts = re.split(r"[~～\-]", clean_str)
    if len(parts) >= 2:
        return parse_roc_date(parts[0]), parse_roc_date(parts[1])
    return None, None

def format_md(d):
    """ 格式化日期 MM/DD """
    return d.strftime('%m/%d') if d else "??"

# ===========================
# 2. 資料抓取
# ===========================

def get_disposition_stocks():
    """ 整合上市與上櫃的處置股資料 """
    all_stocks = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # 時間範圍：抓前後寬鬆一點，確保涵蓋到處置期間
    today = datetime.datetime.now(TW_TZ).date()
    start_lookback = (today - datetime.timedelta(days=20)).strftime('%Y%m%d')
    end_lookahead = (today + datetime.timedelta(days=40)).strftime('%Y%m%d')

    # --- 上市 (TWSE) ---
    try:
        twse_url = "https://www.twse.com.tw/rwd/zh/announcement/punish"
        params = {"response": "json", "startDate": start_lookback, "endDate": end_lookahead}
        r = requests.get(twse_url, params=params, headers=headers, timeout=10)
        data = r.json()
        
        if "data" in data:
            for row in data["data"]:
                # TWSE 格式通常: [序號, 公告日, 證券代號, 證券名稱, 處置條件, 處置起迄時間, ...]
                # 尋找含有 '~' 的欄位作為日期區間
                period_str = ""
                for col in row:
                    if isinstance(col, str) and ("~" in col or "～" in col):
                        period_str = col
                        break
                
                start_d, end_d = split_period(period_str)
                if start_d and end_d:
                    # 處理代號 (去除可能的空白或非數字前綴，保留如 30061)
                    stock_id = str(row[2]).strip()
                    stock_name = str(row[3]).strip()
                    all_stocks.append({
                        "market": "上市",
                        "id": stock_id,
                        "name": stock_name,
                        "start": start_d,
                        "end": end_d
                    })
    except Exception as e:
        print(f"Error fetching TWSE: {e}")

    # --- 上櫃 (TPEx) ---
    try:
        # 上櫃 CSV 連結
        tpex_url = "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw&o=data"
        r = requests.get(tpex_url, headers=headers, timeout=10)
        # 上櫃通常是 UTF-8-SIG 或 CP950，這裡用 auto decode
        r.encoding = 'utf-8' 
        
        csv_data = csv.reader(io.StringIO(r.text))
        # 跳過標題 (通常第一行是標題)
        header_skipped = False
        for row in csv_data:
            if not header_skipped:
                header_skipped = True
                continue
            
            if len(row) < 4: continue
            
            # TPEx CSV 格式: [公告日, 證券代號, 證券名稱, 處置起迄時間, ...]
            # 需注意上櫃 CSV 有時第一欄是日期
            stock_id = row[1].strip()
            stock_name = row[2].strip()
            period_str = row[3].strip()
            
            start_d, end_d = split_period(period_str)
            
            if start_d and end_d:
                all_stocks.append({
                    "market": "上櫃",
                    "id": stock_id,
                    "name": stock_name,
                    "start": start_d,
                    "end": end_d
                })

    except Exception as e:
        print(f"Error fetching TPEx: {e}")

    return all_stocks

# ===========================
# 3. 主程式邏輯
# ===========================

def main():
    today = datetime.datetime.now(TW_TZ).date()
    
    # 判斷今日狀態
    market_open = is_trading_day(today)
    
    # 計算「下個交易日」
    # 如果今天是交易日，Next就是明天(或下週一)
    # 如果今天是假日，Next就是下一個開盤日
    if market_open:
        next_trading_day_val = get_next_trading_day(today)
    else:
        # 假設今天是假日，我們要顯示的 "下個交易日" 依然是接下來要開盤的那天
        # 但為了計算邏輯，我們先找出今天的 "有效下一天"
        next_trading_day_val = get_next_trading_day(today)

    # 抓取原始資料
    raw_data = get_disposition_stocks()

    # 資料去重 (保留結束日最晚的，以防同一檔股票有多筆處置資料)
    unique_map = {}
    for s in raw_data:
        key = (s["market"], s["id"])
        # 如果尚未存在，或這筆資料的結束日比已存在的更晚 (延長處置)，則更新
        if key not in unique_map or s["end"] > unique_map[key]["end"]:
            unique_map[key] = s
    
    # 排序：先上市後上櫃 (顯示時分開)，內部分類依代號排序
    stocks = sorted(unique_map.values(), key=lambda x: x['id'])

    # 準備容器
    results = {
        "上市": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []},
        "上櫃": {"today_out": [], "tomorrow_out": [], "today_in": [], "still_in": []}
    }

    for s in stocks:
        market = s["market"]
        # 該股的恢復交易日 (處置結束日的下一個交易日)
        resumption_date = get_next_trading_day(s["end"])
        
        # 格式化顯示字串
        display_str = f"{s['id']} {s['name']} ({format_md(s['start'])} ~ {format_md(s['end'])})"

        # --- 分類邏輯 ---
        
        # 1. 今日出關: 恢復交易日就是今天
        if resumption_date == today:
            results[market]["today_out"].append(display_str)
        
        # 2. 明日出關: 恢復交易日是下一個交易日 (意即今天是處置最後一天)
        elif resumption_date == next_trading_day_val:
            results[market]["tomorrow_out"].append(display_str)
            
        # 3. 今日進關: 處置開始日是今天
        elif s["start"] == today:
            results[market]["today_in"].append(display_str)
            
        # 4. 處置中: 今天介於開始與結束之間 (且不滿足上述條件)
        # 注意: 避免與「明日出關」重複，因為明日出關代表今天還在處置中，
        # 但為了資訊清晰，通常「明日出關」會獨立顯示，不放在「處置中」。
        elif s["start"] <= today <= s["end"]:
            results[market]["still_in"].append(display_str)

    # ===========================
    # 4. 輸出結果 (Markdown 格式)
    # ===========================
    
    status_text = "(開盤)" if market_open else "(休市)"
    # 日期顯示格式
    date_header = f"📅 日期：{format_md(today)} {status_text}"
    next_header = f"⏩ 下個交易日：{format_md(next_trading_day_val)}"

    output = []
    output.append(date_header)
    output.append(next_header)
    output.append("") # 空行

    def build_section_text(market_name, data_dict):
        section = []
        section.append(f"🟥【{market_name}】")
        
        # 輔助函式：產生清單文字
        def list_to_str(lst):
            return "\n".join(lst) if lst else f"無 ({format_md(next_trading_day_val)} 出關)" if "今日出關" in title else "無"

        # 今日出關
        if data_dict["today_out"]:
            section.append(f"🔓 今日出關:\n" + "\n".join(data_dict["today_out"]))
        else:
            # 依照你的範例，若無則顯示特定文字 (這裡預設顯示 無)
            section.append(f"🔓 今日出關: 無")

        section.append("") 

        # 明日出關
        if data_dict["tomorrow_out"]:
            section.append(f"⏭️ 明日出關:\n" + "\n".join(data_dict["tomorrow_out"]))
        else:
            section.append(f"⏭️ 明日出關: 無")

        section.append("")

        # 今日進關
        if data_dict["today_in"]:
             section.append(f"🔔 今日進關:\n" + "\n".join(data_dict["today_in"]))
        else:
             section.append(f"🔔 今日進關: 無")

        section.append("")

        # 處置中
        if data_dict["still_in"]:
            section.append(f"⏳ 處置中:\n" + "\n".join(data_dict["still_in"]))
        else:
            section.append(f"⏳ 處置中: 無")
            
        section.append("-" * 20)
        return "\n".join(section)

    output.append(build_section_text("上市", results["上市"]))
    output.append(build_section_text("上櫃", results["上櫃"]))

    final_msg = "\n".join(output)
    print(final_msg)

    # --- 若需要發送到 Telegram，可保留以下程式碼 ---
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": final_msg, "parse_mode": "Markdown"}
            )
        except Exception as e:
            print(f"Telegram Send Error: {e}")

if __name__ == "__main__":
    main()
