import requests
import datetime
import os

def parse_date(date_str):
    date_str = date_str.strip()
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            return datetime.date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
        return None
    except:
        return None

def main():
    # ======= 強制模擬區：讓你現在就能看到格式 =======
    today = datetime.date(2025, 12, 29) # 假裝今天是 12/29
    
    # 模擬從 API 抓回來的原始資料 (包含你提供的名單)
    mock_data = [
        {"id": "5475", "name": "德宏", "range": "114/12/12-114/12/28"}, # 12/29 出關
        {"id": "4542", "name": "科峤", "range": "114/12/16-114/12/30"},
        {"id": "6443", "name": "元晶", "range": "114/12/17-114/12/31"},
        {"id": "8358", "name": "金居", "range": "114/12/17-114/12/31"},
        {"id": "4991", "name": "環宇", "range": "114/12/29-115/01/12"}
    ]
    # =============================================

    out_of_jail = []
    in_disposal = []

    for s in mock_data:
        dates = s['range'].split('-')
        end_date = parse_date(dates[1])
        
        if not end_date: continue
        
        # 定義：出關日是結束日的隔天
        exit_date = end_date + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['range']}"
        
        if exit_date == today:
            out_of_jail.append(info)
        elif end_date >= today:
            in_disposal.append(info)

    # 組合訊息
    msg = f"🧪【格式測試報告】\n📅 模擬日期：{today}\n\n"
    msg += "【本日出關】\n" + ("\n".join(out_of_jail) if out_of_jail else "無") + "\n\n"
    msg += "【處置中】\n" + ("\n".join(in_disposal) if in_disposal else "無")

    # 發送 TG
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})
    print(msg)

if __name__ == "__main__":
    main()
