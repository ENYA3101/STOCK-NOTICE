import requests
import datetime
import os

def get_tpex_disposal():
    url = "https://www.tpex.org.tw/web/stock/margin_trading/disposal/disposal_result.php?l=zh-tw"
    
    try:
        response = requests.get(url)
        data = response.json()
        items = data.get('aaData', [])
        
        today = datetime.date.today()
        # 測試用：如果要模擬 12/26 的情況，可取消下行註解
        # today = datetime.date(2024, 12, 26) 
        
        out_of_jail = []  # 本日出關
        in_disposal = []  # 處置中
        
        for item in items:
            stock_id = item[1]
            stock_name = item[2]
            date_range = item[3] # 格式 "113/12/12-113/12/25"
            
            try:
                start_str, end_str = date_range.split('-')
                
                # 民國轉西元函數
                def parse_roc_date(roc_str):
                    y, m, d = map(int, roc_str.strip().split('/'))
                    return datetime.date(y + 1911, m, d)
                
                end_date = parse_roc_date(end_str)
                # 出關日 = 結束日的隔天
                exit_date = end_date + datetime.timedelta(days=1)
                
                formatted_info = f"{stock_name}({stock_id}) {date_range}"
                
                # 邏輯判斷
                if exit_date == today:
                    out_of_jail.append(formatted_info)
                elif end_date >= today:
                    in_disposal.append(formatted_info)
            except:
                continue

        # 組合訊息
        msg = f"📅 報表日期：{today}\n\n"
        
        msg += "【本日出關】\n"
        msg += "\n".join(out_of_jail) if out_of_jail else "無"
            
        msg += "\n\n【處置中】\n"
        msg += "\n".join(in_disposal) if in_disposal else "無"
            
        return msg

    except Exception as e:
        return f"數據解析錯誤: {e}"

def send_telegram(text):
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

if __name__ == "__main__":
    report_content = get_tpex_disposal()
    send_telegram(report_content)
