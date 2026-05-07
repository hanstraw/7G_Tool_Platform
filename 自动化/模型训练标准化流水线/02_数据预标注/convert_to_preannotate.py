import json
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="将 LabelU 导出的标注结果转换为可导入的预标注 JSON")
    parser.add_argument("--input", default=r"c:\Users\Xiao\Desktop\预标注2\占道经营 (1).json", help="导出的 JSON 文件路径")
    parser.add_argument("--output", default=r"c:\Users\Xiao\Desktop\预标注2\预标注_占道经营.json", help="输出的预标注 JSON 路径")
    parser.add_argument("--task-id", type=int, default=None, help="新的任务 ID，如果提供，将替换 url 中的任务 ID")
    
    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"错误: 找不到文件 {input_path}")
        return
        
    print(f"正在读取 {input_path} ...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    result_data = []
    for item in data:
        new_item = {
            "fileName": item.get("fileName")
        }
        
        # 解析 result 字符串，处理分辨率缩放和 order 修复
        result_str = item.get("result")
        if result_str:
            try:
                res_obj = json.loads(result_str)
                orig_w = res_obj.get("width", 0)
                orig_h = res_obj.get("height", 0)
                
                target_w = 1920
                target_h = 1080
                
                scale_x = target_w / orig_w if orig_w > 0 else 1.0
                scale_y = target_h / orig_h if orig_h > 0 else 1.0
                need_scale = orig_w > 0 and orig_h > 0 and (orig_w != target_w or orig_h != target_h)
                
                # 遍历 annotations 找到 rectTool 进行缩放和修复 order
                for ann in res_obj.get("annotations", []):
                    if ann.get("toolName") == "rectTool":
                        for i, rect in enumerate(ann.get("result", [])):
                            # 修复 order（LabelU Schema 严格要求 order 为 >= 1 的整数，且最好不重复）
                            rect["order"] = i + 1
                            
                            if need_scale:
                                rect["x"] *= scale_x
                                rect["y"] *= scale_y
                                rect["width"] *= scale_x
                                rect["height"] *= scale_y
                
                # 统一设置为目标分辨率
                res_obj["width"] = target_w
                res_obj["height"] = target_h
                
                new_item["result"] = json.dumps(res_obj, ensure_ascii=False)
            except json.JSONDecodeError:
                new_item["result"] = result_str
        else:
            new_item["result"] = result_str
        
        # 保留 folder
        if "folder" in item:
            new_item["folder"] = item["folder"]
            
        # 处理 url，如果指定了新 task_id 则替换
        if "url" in item:
            url = item["url"]
            if args.task_id is not None:
                parts = url.split("/")
                # LabelU URL 格式通常为: /api/v1/tasks/attachment/upload/{task_id}/images_only/xxx.jpg
                if len(parts) >= 7 and parts[4] == "attachment" and parts[5] == "upload":
                    parts[6] = str(args.task_id)
                    url = "/".join(parts)
            new_item["url"] = url
            
        result_data.append(new_item)
        
    print(f"正在保存到 {output_path} ...")
    with open(output_path, "w", encoding="utf-8") as f:
        # 为了更好的可读性以及和普通预标注结果一致，不转义中文且格式化
        json.dump(result_data, f, ensure_ascii=False, indent=2)
        
    print(f"转换成功！共处理 {len(result_data)} 条记录。")

if __name__ == "__main__":
    main()
