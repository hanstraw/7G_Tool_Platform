from ultralytics import YOLO

# 加载你自己的模型，绝对不会被覆盖！
model = YOLO("./weights/best.pt")

# 开始训练（所有参数直接写，不依赖命令行BUG）
model.train(
    data="./data/dataset.yaml",
    cfg="./train.yaml",
    epochs=200,
    patience=30,
    batch=4,
    imgsz=1280,
    device="0",
    amp=False,  # 关闭自动下载模型的元凶
    pretrained=False
)
