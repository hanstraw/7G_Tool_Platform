from ultralytics import YOLO


MODEL = "/mnt/sda1/yolov11/roadsideillegalvending4/runs/detect/retrain_v1_yolo11s_highres/weights/best.pt"
DATA = "/mnt/sda1/yolov11/roadsideillegalvending4/data/dataset.yaml"


if __name__ == "__main__":
    model = YOLO(MODEL)
    model.val(
        data=DATA,
        split="test",
        imgsz=1280,
        conf=0.35,
        iou=0.5,
        device=0,
        project="/mnt/sda1/yolov11/roadsideillegalvending4/runs/detect",
        name="native_test_retrain_v1_yolo11s_highres",
        exist_ok=False,
        plots=True,
    )
