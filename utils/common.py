#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import cv2
import numpy as np
from PIL import Image, ImageQt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt


def cv2_to_qpixmap(cv_img, scaled_size=None):
    """OpenCV图像转换为QPixmap
    
    Args:
        cv_img: OpenCV格式图像(BGR或RGB)
        scaled_size: 缩放尺寸(width, height)，如果指定则缩放图像
        
    Returns:
        QPixmap: 转换后的QPixmap对象
    """
    # 确保图像是RGB格式
    if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
        if cv_img.dtype == np.uint8:
            # OpenCV使用BGR，需要转换为RGB
            rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            bytes_per_line = ch * w
            
            # 创建QImage
            q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 创建QPixmap
            pixmap = QPixmap.fromImage(q_img)
            
            # 如果需要缩放
            if scaled_size:
                pixmap = pixmap.scaled(
                    scaled_size[0], 
                    scaled_size[1], 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                
            return pixmap
    
    # 处理失败，返回空QPixmap
    return QPixmap()


def pil_to_qpixmap(pil_img, scaled_size=None):
    """PIL图像转换为QPixmap
    
    Args:
        pil_img: PIL格式图像
        scaled_size: 缩放尺寸(width, height)，如果指定则缩放图像
        
    Returns:
        QPixmap: 转换后的QPixmap对象
    """
    # 将PIL图像转换为QImage
    q_img = ImageQt.ImageQt(pil_img)
    
    # 创建QPixmap
    pixmap = QPixmap.fromImage(q_img)
    
    # 如果需要缩放
    if scaled_size:
        pixmap = pixmap.scaled(
            scaled_size[0], 
            scaled_size[1], 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
    return pixmap


def format_time(seconds):
    """格式化时间
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化的时间字符串 (HH:MM:SS)
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


def get_confidence_color(conf):
    """根据置信度返回对应的颜色
    
    Args:
        conf: 置信度值(0~1)
        
    Returns:
        tuple: (R, G, B)颜色值
    """
    if conf >= 0.7:
        return (0, 255, 0)  # 绿色 - 高置信度
    elif conf >= 0.4:
        return (255, 165, 0)  # 橙色 - 中等置信度
    else:
        return (255, 0, 0)  # 红色 - 低置信度 