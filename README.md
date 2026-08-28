# TrafficTracker

基于 YOLOv8/YOLO 系列模型、ByteTrack 和 ROI/计数线的车辆检测与流量统计系统。

## 项目内容

- `main.py`：图形化程序入口
- `ui/`：界面代码和资源
- `utils/`：检测、跟踪、ROI 与计数逻辑
- `model/`：模型权重目录
- `resources/`：界面及运行资源
- `requirements.txt`：Python 依赖

## Windows 运行

1. 创建 Python 虚拟环境并安装依赖：

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. 将模型权重放入 `model/`，默认权重文件为 `model/best.pt`。

3. 启动图形化程序：

   ```bat
   python main.py
   ```

## 说明

- `.venv/`、运行结果、测试视频、日志和本地数据库不会提交到 Git。
- TensorRT `.engine` 文件与 CUDA、显卡和 TensorRT 版本有关，未纳入版本库。
- 运行时请根据本机环境重新安装依赖，并在界面中选择模型和视频。
