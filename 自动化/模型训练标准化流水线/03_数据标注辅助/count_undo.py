import requests
import time
from collections import Counter


TASK_ID = 148
HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTIsInVzZXJuYW1lIjoiZGVuZ2d1b2p1bkBnbWFpbC5jb20iLCJleHAiOjE3NzY5MjYyMjl9.yGtFInDyKWhwEVp9EEyvI1Y78j_16rQVlhoqF23IodM",
    "Content-Type": "application/json",
}
BASE_URL = f"http://113.141.72.253:38000/api/v1/tasks/{TASK_ID}/samples"

def scan_pending_pages():
    page = 1
    size = 10  # 强制按每页 10 个划分
    
    # 我们认为“已处理完毕”的状态
    FINISHED_STATES = ['DONE', 'SKIPPED', 'SKIP']
    
    total_pending = 0
    pages_with_pending_count = 0
    
    # 状态探测器：记录所有出现过的状态
    state_counter = Counter()

    print(f"扫描任务 {TASK_ID} 的未处理样本...\n")
    print("--- 扫描结果 ---")

    while True:
        params = {"page": page, "size": size}
        
        try:
            response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"获取第 {page} 页失败: 状态码 {response.status_code}")
                break
                
            samples = response.json().get("data", [])
            
            if not samples:
                break
                
            current_page_pending = 0
            
            for sample in samples:
                # 获取状态，如果状态为空则默认为 'UNKNOWN'
                state = sample.get('state', 'UNKNOWN')
                state_counter[state] += 1
                
                # 核心逻辑：只要不是 DONE 也不是 SKIPPED，统统视为未标注
                if state not in FINISHED_STATES:
                    current_page_pending += 1
            
            # 按要求格式输出
            if current_page_pending > 0:
                print(f"页码 {page + 1}: {current_page_pending}")
                total_pending += current_page_pending
                pages_with_pending_count += 1
                
            if len(samples) < size:
                break
                
            page += 1
            time.sleep(0.2)
            
        except Exception as e:
            print(f"扫描第 {page} 页时发生异常: {e}")
            break

    print("\n--- 探测器报告 ---")
    print("你的任务中实际存在以下状态：")
    for s, count in state_counter.items():
        print(f" - {s}: {count} 个")

    print("\n--- 总计统计 ---")
    print(f"包含未处理数据的页数: {pages_with_pending_count} 页")
    print(f"总计未处理样本数量: {total_pending} 个")
    print(f"共计扫描了 {page} 页数据")

if __name__ == "__main__":
    scan_pending_pages()