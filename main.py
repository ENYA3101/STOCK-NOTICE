import requests
import datetime
import os

def parse_date(date_str):
    date_str = date_str.strip().replace(" ", "")
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            return datetime.date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
        return None
    except:
        return None

def main():
    # ======= 模擬測試環境 =======
    # 假裝今天是 2025/12/29
    today = datetime.date(2025, 12, 29) 
    
    # 模擬 API 原始資料
    mock_data = [
        {
            "id": "4991", "name": "環宇", 
            "announce": "114/12/29", # 今天的公告
            "range": "114/12/30-115/01/12" # 明天開始處置
        },
        {
            "id": "5475", "name": "德宏", 
            "announce": "114/12/11", 
            "range": "114/12/12-114/12/28" # 昨天結束，今天出關
        },
        {
            "id": "3081", "name": "聯亞", 
            "announce": "114/12/22", 
            "range": "114/12/23-115/01/09" # 處置中
        }
    ]
    # ==========================

    new_announcement = []
    out_of_jail = []
    still_in = []

    for s in mock_data:
        dates = s['range'].split('-')
        announce_date = parse_date(s['announce'])
        end_date = parse_date(dates[1])
        
        if not end_date or not announce_date: continue
        
        exit_date = end_date + datetime.timedelta(days=1)
        info = f"{s['name']}({s['id']}) {s['range']}"
        
        # 判斷邏輯
        if announce_date == today:
            new_announcement.append(f"🔔 {info}")
        
        if exit_date == today:
            out_of_jail.append(info)
        elif end_date >= today:
            still_in.append(info)

    # 組合訊息
    msg = f"🧪【公告日邏輯測試】\n📅 模擬日期：{today}\n\n"
    
    msg += "【🔔 今日新公告進關】\n"
    msg += "\n".join(new_announcement) if new_announcement else "無"
    msg += "\n\n"
    
    msg += "【本日出關】\n"
    msg += "\n".join(out_of_jail) if out_of_jail else "無"
    msg += "\n\n"
    
    msg += "【所有處置中明細】\n"
    msg += "\n".join(still_in) if still_in else "無"

    # 發送 Telegram
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": msg})
    print(msg)

if __name__ == "__main__":
    main()
