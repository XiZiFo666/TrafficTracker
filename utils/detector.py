#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import cv2
import numpy as np
import time
from pathlib import Path
from ultralytics import YOLO
from PIL import Image


class YOLODetector:
    """YOLOv8目标检测器类"""
    
    # 类别映射（英文到中文）
    CLASS_MAPPING = {
        'Pedestrian': "行人", 
        'Van': '面包车', 
        'Car': '小汽车', 
        'Two-wheeler': '两轮车', 
        'Bus': '公交车', 
        'Truck': '卡车'
    }
    
    # 类别颜色映射（用于显示不同的边界框颜色）
    COLOR_MAPPING = {
        'Pedestrian': (168, 100, 253),  # 紫色
        'Van': (0, 0, 255),             # 红色
        'Car': (254, 138, 0),           # 蓝色 
        'Two-wheeler': (255, 102, 178), # 粉色
        'Bus': (0, 130, 255),           # 橙色
        'Truck': (0, 255, 0)            # 绿色
    }
    
    def __init__(self, model_path=None, conf_threshold=0.25, iou_threshold=0.5):
        """初始化YOLO检测器
        
        Args:
            model_path: YOLO模型路径
            conf_threshold: 置信度阈值
            iou_threshold: IOU阈值
        """
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # 加载模型
        if model_path and os.path.exists(model_path):
            self.model = YOLO(model_path)
        else:
            raise FileNotFoundError(f"模型文件 {model_path} 不存在")
            
        self.class_names = self.model.names
        
    def detect_image(self, image_path):
        """检测图片中的目标
        
        Args:
            image_path: 图片路径
            
        Returns:
            (processed_img, results_dict): (处理后的图片，检测结果)
        """
        # 检查图片是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件 {image_path} 不存在")
            
        # 执行推理
        results = self.model(image_path, conf=self.conf_threshold, iou=self.iou_threshold)[0]
        
        # 读取原始图片
        original_img = cv2.imread(image_path)
        original_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)
        
        # 统计各类别数量
        class_counts = self._count_objects(results)
        
        # 在图像上绘制边界框和标签
        processed_img = self._draw_boxes(original_img, results)
        
        return processed_img, class_counts
    
    def detect_video_frame(self, frame):
        """检测视频帧中的目标
        
        Args:
            frame: 视频帧(RGB格式)
            
        Returns:
            (processed_frame, results_dict): (处理后的帧，检测结果)
        """
        # 执行推理
        results = self.model(frame, conf=self.conf_threshold, iou=self.iou_threshold)[0]
        
        # 统计各类别数量
        class_counts = self._count_objects(results)
        
        # 在图像上绘制边界框和标签
        processed_frame = self._draw_boxes(frame.copy(), results)
        
        return processed_frame, class_counts
    
    def _count_objects(self, results):
        """统计检测到的各类别目标数量
        
        Args:
            results: YOLO检测结果
            
        Returns:
            dict: 各类别数量统计
        """
        # 初始化计数器
        class_counts = {cn: 0 for cn in self.CLASS_MAPPING.values()}
        
        # 统计数量
        for box in results.boxes:
            cls_id = int(box.cls.item())
            cls_name = self.class_names[cls_id]
            if cls_name in self.CLASS_MAPPING:
                cn_name = self.CLASS_MAPPING[cls_name]
                class_counts[cn_name] += 1
                
        return class_counts
    
    def _draw_boxes(self, img, results):
        """在图像上绘制检测框和标签
        
        Args:
            img: 原始图片
            results: YOLO检测结果
            
        Returns:
            处理后的图片
        """
        # 复制图像以免修改原图
        img_with_boxes = img.copy()
        
        # 遍历所有检测框
        for box in results.boxes:
            # 获取坐标和置信度
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf.item())
            cls_id = int(box.cls.item())
            cls_name = self.class_names[cls_id]
            
            # 仅处理已映射的类别
            if cls_name in self.CLASS_MAPPING:
                cn_name = self.CLASS_MAPPING[cls_name]
                color = self.COLOR_MAPPING.get(cls_name, (0, 255, 0))
                
                # 绘制边界框
                cv2.rectangle(img_with_boxes, (x1, y1), (x2, y2), color, 2)
                
                # 准备标签文本
                label = f"{cn_name} {conf:.2f}"
                
                # 使用PIL绘制中文标签
                pil_img = Image.fromarray(img_with_boxes)
                
                # 导入绘图和字体模块
                from PIL import ImageDraw, ImageFont
                
                # 绘制对象
                draw = ImageDraw.Draw(pil_img)
                
                # 设置字体路径
                font_paths = [
                    "resources/fonts/simhei.ttf",    # 黑体
                    "resources/fonts/SourceHanSansSC-Regular.otf",  # 思源黑体
                    "C:/Windows/Fonts/msyh.ttc",     # Windows微软雅黑
                    "C:/Windows/Fonts/simhei.ttf",   # Windows黑体
                    "resources/fonts/NotoSansSC-Regular.otf",  # Noto Sans SC
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"  # Linux文泉驿微米黑
                ]
                
                # 尝试加载字体
                font = None
                for font_path in font_paths:
                    try:
                        if os.path.exists(font_path):
                            font = ImageFont.truetype(font_path, 18)  # 字体大小改为18
                            break
                    except Exception as e:
                        print(f"字体 {font_path} 加载失败: {e}")
                
                # 如果所有字体都加载失败，使用默认字体
                if font is None:
                    font = ImageFont.load_default()
                
                # 计算标签背景大小
                text_width, text_height = draw.textbbox((0, 0), label, font=font)[2:]
                
                # 绘制标签背景
                draw.rectangle(
                    [(x1, y1 - text_height - 8), (x1 + text_width + 8, y1)],
                    fill=color
                )
                
                # 绘制标签文字
                draw.text(
                    (x1 + 4, y1 - text_height - 4),
                    label,
                    fill=(255, 255, 255),
                    font=font
                )
                
                # 转换回OpenCV格式
                img_with_boxes = np.array(pil_img)
        
        return img_with_boxes 