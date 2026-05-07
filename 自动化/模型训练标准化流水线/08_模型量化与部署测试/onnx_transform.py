import sys
from ultralytics import YOLO
from onnxsim import simplify
import onnx


"""
def get_onnx_model(ptModelPath,onnxModelPath):
  print("pt transform onnx==============")
  model = YOLO(ptModelPath)
  #dynamic转 rknn 设为 false
  model.export(format='onnx', dynamic=False,opset=11,imgsz=(640,640))

  #
  #check
  onnx_model = onnx.load(onnxModelPath)
  model_simp, check = simplify(onnx_model)

  assert check, "Simplified ONNX model could not be validated"
  onnx.save(model_simp, onnxModelPath)


#/home/dev/anaconda3/envs/7gModel/bin/python3  onnx_transform.py runs/detect/train17/weights/best.pt  runs/detect/train17/weights/best.onnx
if __name__ == '__main__':
    ptModelPath = sys.argv[1]  # 模型.pt 路径
    onnxModelPath = sys.argv[2]  # 模型.onnx 路径
    #
    get_onnx_model(ptModelPath,onnxModelPath)

"""

#底层要进行修改：参考 https://github.com/sophgo/sophon-demo/blob/release/sample/YOLOv8_plus_det/docs/YOLOv8_Export_Guide.md
#导出模型
#方式二
# ==================== 配置区 ====================
# 模型路径（推荐用自己训练好的车辆检测模型）
model_path = "./best.pt"  # 或 "best.pt"（训练好的车辆模型）
# 加载 YOLOv11 OBB 模型
model = YOLO(model_path)

#from ultralytics import YOLO
model.export(format='onnx', opset=13, dynamic=True)  # 导出为ONNX
# 导出的文件通常为 best.onnx