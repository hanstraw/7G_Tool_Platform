import requests
import time
DELETE_BATCH_SIZE = 100 # 每批删除的样本数量

# 配置信息
TASK_ID = 148
HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTIsInVzZXJuYW1lIjoiZGVuZ2d1b2p1bkBnbWFpbC5jb20iLCJleHAiOjE3NzY5MjYyMjl9.yGtFInDyKWhwEVp9EEyvI1Y78j_16rQVlhoqF23IodM",
    "Content-Type": "application/json",
}
BASE_URL = f"http://113.141.72.253:38000/api/v1/tasks/{TASK_ID}/samples"

def get_all_skipped_ids():
    all_skipped_ids = []
    page = 1
    size = 100 # 每页拉取 100 条以提高效率

    while True:
        print(f"正在拉取第 {page} 页样本...")
        params = {"page": page, "size": size}
        
        try:
            response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            if response.status_code != 200:
                print(f"获取第 {page} 页失败: {response.status_code}")
                break
            
            res_data = response.json().get("data", [])
            if not res_data:
                print("所有页面已拉取完毕。")
                break
            
            # 筛选当前页中状态为 SKIPPED 的 ID
            # 注意：请根据你之前打印的数据确认是 "SKIPPED" 还是 "SKIP"
            current_skipped = [s['id'] for s in res_data if s.get('state') == 'SKIPPED']
            all_skipped_ids.extend(current_skipped)
            
            print(f"第 {page} 页处理完成，发现 {len(current_skipped)} 个跳过样本。")
            
            # 如果当前页返回的数据少于 size，说明已经是最后一页了
            if len(res_data) < size:
                break
            
            page += 1
            time.sleep(0.5) # 稍微停顿，避免请求过快
            
        except Exception as e:
            print(f"发生错误: {e}")
            break
            
    return all_skipped_ids

def delete_samples(ids, batch_size=None):
    if not ids:
        print("没有需要删除的样本。")
        return
    
    batch_size = batch_size or DELETE_BATCH_SIZE
    if batch_size < 1:
        raise ValueError("batch_size 必须 >= 1")
        
    total = len(ids)
    # 计算总批次数 
    batches = (total + batch_size - 1) // batch_size
    print(f"准备删除共计 {total} 个样本，分 {batches} 批 (每批最多 {batch_size} 个)...")
    
    ok_count = 0
    # 记录失败的批次信息：(批次序号, ids切片, 状态码或异常, 详细信息)
    failed_batches = [] 
    
    for i in range(0, total, batch_size):
        chunk = ids[i : i + batch_size]
        batch_index = (i // batch_size) + 1
        print(f"正在删除第 {batch_index}/{batches} 批次 ({len(chunk)} 个样本)...", end=" ")
        
        payload = {"sample_ids": chunk}
        
        try:
            # 请确保 BASE_URL 和 HEADERS 在外部已正确定义
            response = requests.delete(BASE_URL, headers=HEADERS, json=payload, timeout=30)
            
            if response.status_code == 200:
                print("成功")
                ok_count += len(chunk)
            else:
                print(f"失败 (状态码: {response.status_code})")
                failed_batches.append((batch_index, chunk, response.status_code, response.text))
        except Exception as e:
            print(f"发生异常: {e}")
            failed_batches.append((batch_index, chunk, "Exception", str(e)))
        
        # 避免连续请求触发服务器限流，稍微停顿 (最后一批不需要等)
        if batch_index < batches:
            time.sleep(0.5)

    # 打印最终统计结果
    print("\n--- 批量删除任务结束 ---")
    print(f"成功删除: {ok_count} / {total} 个样本")
    
    if failed_batches:
        print(f"警告: 共有 {len(failed_batches)} 个批次处理失败，请检查 failed_batches 列表获取详情。")

if __name__ == "__main__":
    # 1. 递归拉取所有页面的 ID
    skipped_list = get_all_skipped_ids()
    print(f"--- 扫描结束：总计发现 {len(skipped_list)} 个跳过状态的样本 ---")
    
    # 2. 一次性执行删除
    if skipped_list:
        confirm = input(f"确定要删除这 {len(skipped_list)} 个样本吗？(y/n): ")
        if confirm.lower() == 'y':
            delete_samples(skipped_list)
        else:
            print("操作已取消。")