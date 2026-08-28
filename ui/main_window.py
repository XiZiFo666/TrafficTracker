#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QThread, QMutex
from PySide6.QtGui import QPixmap, QIcon, QFont, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QGridLayout,
    QProgressDialog  # 添加QDialog和QProgressDialog
)

from utils.common import cv2_to_qpixmap
from utils.detector import YOLODetector


class VideoProcessThread(QThread):
    """视频处理线程"""

    # 定义信号
    frame_ready = Signal(np.ndarray, dict)  # 帧处理完成信号(处理后的帧, 检测结果)
    video_finished = Signal()  # 视频处理完成信号

    def __init__(self, detector, video_path, parent=None):
        """初始化线程
        
        Args:
            detector: YOLODetector实例
            video_path: 视频文件路径
            parent: 父对象
        """
        super().__init__(parent)
        self.detector = detector
        self.video_path = video_path
        self.stopped = False
        self.mutex = QMutex()

        # 追踪相关变量
        self.tracks = {}  # 存储目标轨迹，格式: {track_id: [(x, y, frame_idx), ...]}
        self.next_track_id = 0  # 下一个轨迹ID
        self.max_track_length = 30  # 最大轨迹长度
        self.previous_boxes = {}  # 存储前一帧检测到的目标，格式: {track_id: (x_center, y_center, width, height, class_id, confidence)}
        self.frame_idx = 0  # 帧索引

        # 保存处理过的帧
        self.processed_frames = []
        self.save_frames = False  # 是否保存帧的标志

        # 获取视频基本信息
        cap = cv2.VideoCapture(video_path)
        self.video_fps = cap.get(cv2.CAP_PROP_FPS)
        self.video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

    def _match_detections(self, current_detections):
        """匹配当前检测结果与现有轨迹
        
        Args:
            current_detections: 当前帧的检测结果，每个元素为 (x_center, y_center, width, height, class_id, confidence)
        
        Returns:
            匹配结果和新的检测结果
        """
        matches = []  # 存储匹配结果，格式: (track_id, detection_idx)
        unmatched_detections = list(range(len(current_detections)))  # 未匹配的检测结果索引

        # 如果没有现有轨迹，则所有检测结果都是新的
        if not self.previous_boxes:
            return matches, unmatched_detections

        # 计算IoU矩阵
        iou_matrix = np.zeros((len(self.previous_boxes), len(current_detections)))
        for i, (track_id, prev_box) in enumerate(self.previous_boxes.items()):
            x1_prev, y1_prev, w_prev, h_prev = prev_box[0] - prev_box[2] / 2, prev_box[1] - prev_box[3] / 2, prev_box[
                2], prev_box[3]
            for j, curr_box in enumerate(current_detections):
                x1_curr, y1_curr, w_curr, h_curr = curr_box[0] - curr_box[2] / 2, curr_box[1] - curr_box[3] / 2, \
                curr_box[2], curr_box[3]

                # 计算IoU
                x_left = max(x1_prev, x1_curr)
                y_top = max(y1_prev, y1_curr)
                x_right = min(x1_prev + w_prev, x1_curr + w_curr)
                y_bottom = min(y1_prev + h_prev, y1_curr + h_curr)

                if x_right < x_left or y_bottom < y_top:
                    iou = 0.0
                else:
                    intersection_area = (x_right - x_left) * (y_bottom - y_top)
                    box1_area = w_prev * h_prev
                    box2_area = w_curr * h_curr
                    iou = intersection_area / float(box1_area + box2_area - intersection_area)

                iou_matrix[i, j] = iou

        # 基于IoU进行匹配
        if iou_matrix.size > 0:
            # 利用贪心算法进行匹配
            while iou_matrix.size > 0 and iou_matrix.max() > 0.3:  # IoU阈值设为0.3
                # 找到最大IoU对应的行列索引
                max_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                row, col = max_idx

                # 获取对应的track_id
                track_id = list(self.previous_boxes.keys())[row]

                # 添加匹配结果
                matches.append((track_id, col))

                # 从未匹配列表中移除已匹配检测
                if col in unmatched_detections:
                    unmatched_detections.remove(col)

                # 将已匹配的行列置为0，防止重复匹配
                iou_matrix[row, :] = 0
                iou_matrix[:, col] = 0

        return matches, unmatched_detections

    def run(self):
        """线程主函数"""
        # 打开视频文件
        cap = cv2.VideoCapture(self.video_path)

        # 检查视频是否打开成功
        if not cap.isOpened():
            QMessageBox.critical(None, "错误", f"无法打开视频文件: {self.video_path}")
            return

        # 处理每一帧
        self.frame_idx = 0
        self.processed_frames = []  # 清空之前的帧

        while not self.stopped:
            # 读取一帧
            ret, frame = cap.read()

            # 检查是否到达视频末尾
            if not ret:
                break

            # 转换颜色空间
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 检测目标
            processed_frame, results = self.detector.detect_video_frame(frame_rgb)

            # 处理检测结果，更新轨迹
            self._update_tracks(processed_frame, results)

            # 如果需要保存帧，则添加到列表中
            if self.save_frames:
                # 转换为BGR以便保存
                frame_bgr = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2BGR)
                self.processed_frames.append(frame_bgr)

            # 发送信号
            self.frame_ready.emit(processed_frame, results)

            # 增加帧索引
            self.frame_idx += 1

            # 控制处理速度
            time.sleep(0.02)

        # 释放资源
        cap.release()

        # 发送视频处理完成信号
        self.video_finished.emit()

    def _update_tracks(self, frame, results):
        """更新目标轨迹
        
        Args:
            frame: 当前帧
            results: 检测结果
        """
        try:
            # 处理检测结果
            current_detections = []

            # 从模型结果中提取检测框（使用主窗口的置信度和IOU值）
            img_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # 通过detector对象获取主窗口设置的参数值
            conf_value = self.detector.conf_threshold
            iou_value = self.detector.iou_threshold

            model_results = self.detector.model(img_bgr, conf=conf_value, iou=iou_value)[0]

            # 提取当前帧的所有检测框
            for box in model_results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf.item())
                cls_id = int(box.cls.item())

                # 计算中心点、宽度和高度
                x_center = (x1 + x2) / 2
                y_center = (y1 + y2) / 2
                width = x2 - x1
                height = y2 - y1

                current_detections.append((x_center, y_center, width, height, cls_id, conf))

            # 匹配当前检测结果与已有轨迹
            matches, unmatched_detections = self._match_detections(current_detections)

            # 更新匹配的轨迹
            for track_id, detection_idx in matches:
                det = current_detections[detection_idx]
                x_center, y_center = det[0], det[1]

                # 将当前位置添加到轨迹中
                if track_id in self.tracks:
                    self.tracks[track_id].append((int(x_center), int(y_center), self.frame_idx))
                    # 保持轨迹长度不超过最大值
                    if len(self.tracks[track_id]) > self.max_track_length:
                        self.tracks[track_id] = self.tracks[track_id][-self.max_track_length:]

                # 更新previous_boxes
                self.previous_boxes[track_id] = det

            # 为未匹配的检测创建新轨迹
            for detection_idx in unmatched_detections:
                det = current_detections[detection_idx]
                x_center, y_center = det[0], det[1]

                # 创建新轨迹
                track_id = self.next_track_id
                self.next_track_id += 1

                self.tracks[track_id] = [(int(x_center), int(y_center), self.frame_idx)]
                self.previous_boxes[track_id] = det

            # 绘制轨迹
            for track_id, track in self.tracks.items():
                if len(track) > 1:
                    # 根据类别ID选择颜色
                    if track_id in self.previous_boxes:
                        cls_id = self.previous_boxes[track_id][4]
                        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]  # 蓝、绿、红、青、黄
                        color = colors[cls_id % len(colors)]
                    else:
                        color = (255, 255, 255)  # 白色

                    # 绘制轨迹线
                    for i in range(1, len(track)):
                        if track[i][2] - track[i - 1][2] <= 5:  # 只连接时间间隔小于5帧的点
                            cv2.line(frame, (track[i - 1][0], track[i - 1][1]),
                                     (track[i][0], track[i][1]), color, 2)

        except Exception as e:
            print(f"更新轨迹时出错: {str(e)}")

    def stop(self):
        """停止线程"""
        self.mutex.lock()
        self.stopped = True
        self.mutex.unlock()

    def start_saving_frames(self):
        """开始保存帧"""
        self.save_frames = True
        self.processed_frames = []  # 清空之前保存的帧

    def stop_saving_frames(self):
        """停止保存帧"""
        self.save_frames = False

    def save_video(self, output_path):
        """将处理过的帧保存为视频
        
        Args:
            output_path: 输出视频路径
            
        Returns:
            bool: 是否保存成功
        """
        if not self.processed_frames:
            return False

        try:
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MP4格式
            out = cv2.VideoWriter(
                output_path,
                fourcc,
                self.video_fps,
                (self.video_width, self.video_height)
            )

            # 写入帧
            for frame in self.processed_frames:
                out.write(frame)

            # 释放资源
            out.release()

            return True
        except Exception as e:
            print(f"保存视频时出错: {str(e)}")
            return False


class MainWindow(QMainWindow):
    """主窗口(功能页)"""

    def __init__(self, username=None, avatar_path=None):
        super().__init__()

        # 用户名
        self.username = username

        # 用户头像路径
        self.avatar_path = avatar_path

        # 初始化检测器
        try:
            self.detector = YOLODetector(model_path="model/best.pt")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载模型失败: {str(e)}")
            self.close()
            return

        # 设置窗口属性
        self.setWindowTitle("基于YOLOv8的车辆行人检测系统")
        self.resize(1200, 700)

        # 创建UI
        self._init_ui()

        # 初始化视频处理相关变量
        self.video_thread = None
        self.is_processing_video = False
        self.is_saving_video = False  # 是否正在保存视频的标志

        # 批量处理图片结果列表
        self.batch_results = []
        self.current_batch_index = -1

    def _init_ui(self):
        """初始化UI"""
        # 设置应用全局样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
                font-family: 'Microsoft YaHei';
            }
            QLabel {
                font-size: 12px;
                color: #2c3e50;
            }
            QFrame {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 5px 10px;
                font-weight: bold;
                border-radius: 4px;
                font-size: 13px;
                height: 28px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                text-align: center;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
            QTableWidget {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                gridline-color: #ecf0f1;
                selection-background-color: #bdc3c7;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #dcdde1;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        # 初始化模型参数默认值
        self.conf_value = self.detector.conf_threshold
        self.iou_value = 0.5  # 默认值

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 左侧控制面板 (25%)
        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.StyledPanel)
        left_panel.setMinimumWidth(230)
        left_panel.setMaximumWidth(280)
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(8, 8, 8, 8)
        left_panel_layout.setSpacing(8)

        # ===== 用户信息区域 =====
        user_info_frame = QFrame()
        user_info_frame.setFrameShape(QFrame.StyledPanel)
        user_info_layout = QHBoxLayout(user_info_frame)
        user_info_layout.setContentsMargins(10, 10, 10, 10)

        # 头像
        avatar_label = QLabel()
        avatar_label.setFixedSize(40, 40)  # 设置固定大小
        avatar_label.setAlignment(Qt.AlignCenter)  # 居中对齐

        # 尝试加载头像图片
        avatar_pixmap = None
        if self.avatar_path and os.path.exists(self.avatar_path):
            # 如果有用户自定义头像，优先使用
            avatar_pixmap = QPixmap(self.avatar_path)
        else:
            # 否则使用默认头像
            avatar_pixmap = QPixmap(os.path.join("resources", "icons", "avator.jpg"))

        if avatar_pixmap and not avatar_pixmap.isNull():
            # 缩放图片并设置为圆形
            scaled_pixmap = avatar_pixmap.scaled(
                40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            avatar_label.setPixmap(scaled_pixmap)
            avatar_label.setStyleSheet("border-radius: 20px; background-color: #ecf0f1;")
        else:
            # 如果找不到图标，使用文字代替
            avatar_label.setText("👤")
            avatar_label.setStyleSheet(
                "font-size: 20px; color: #3498db; background-color: #ecf0f1; border-radius: 20px;")

        self.avatar_label = avatar_label  # 保存引用以便后续更新
        user_info_layout.addWidget(avatar_label)

        # 用户名和退出按钮的垂直布局
        user_info_text_layout = QVBoxLayout()
        user_info_text_layout.setSpacing(2)

        # 用户名
        self.username_label = QLabel(f"{self.username}" if self.username else "访客")
        self.username_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        user_info_text_layout.addWidget(self.username_label)

        # 系统名称
        system_name_label = QLabel("基于YOLOv8的车辆行人检测系统")
        system_name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        system_name_label.setStyleSheet("color: #2c3e50;")
        user_info_text_layout.addWidget(system_name_label)

        user_info_layout.addLayout(user_info_text_layout)
        user_info_layout.addStretch()

        left_panel_layout.addWidget(user_info_frame)

        # ===== 控制按钮区域 =====
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(10, 10, 10, 10)
        control_layout.setSpacing(8)

        # 控制按钮标题
        control_title = QLabel("功能控制")
        control_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        control_title.setAlignment(Qt.AlignCenter)
        control_title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        control_layout.addWidget(control_title)

        # 模型选择按钮
        self.select_model_btn = QPushButton("选择模型文件")
        self.select_model_btn.setIcon(QIcon(os.path.join("resources", "icons", "model.png")))
        self.select_model_btn.clicked.connect(self._on_select_model_clicked)
        control_layout.addWidget(self.select_model_btn)

        # 图片选择按钮
        self.select_image_btn = QPushButton("选择图片文件")
        self.select_image_btn.setIcon(QIcon(os.path.join("resources", "icons", "image.png")))
        self.select_image_btn.clicked.connect(self._on_select_image_clicked)
        control_layout.addWidget(self.select_image_btn)

        # 选择图片列表按钮
        self.select_image_list_btn = QPushButton("选择图片列表")
        self.select_image_list_btn.setIcon(QIcon(os.path.join("resources", "icons", "image-list.png")))
        self.select_image_list_btn.clicked.connect(self._on_select_image_list_clicked)
        control_layout.addWidget(self.select_image_list_btn)

        # 视频选择按钮
        self.select_video_btn = QPushButton("选择视频文件")
        self.select_video_btn.setIcon(QIcon(os.path.join("resources", "icons", "video.png")))
        self.select_video_btn.clicked.connect(self._on_select_video_clicked)
        control_layout.addWidget(self.select_video_btn)

        # 保存检测结果按钮
        self.save_results_btn = QPushButton("保存检测结果")
        self.save_results_btn.setIcon(QIcon(os.path.join("resources", "icons", "save.png")))
        self.save_results_btn.clicked.connect(self._on_save_results_clicked)
        self.save_results_btn.setStyleSheet("""
            background-color: #27ae60;
            color: white;
            border: none;
            padding: 5px 10px;
            font-weight: bold;
            border-radius: 4px;
            font-size: 13px;
            height: 28px;
        """)
        control_layout.addWidget(self.save_results_btn)

        left_panel_layout.addWidget(control_frame)

        # ===== 统计信息区域 =====
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(10, 10, 10, 10)
        stats_layout.setSpacing(8)

        # 目标数统计标题
        stats_title = QLabel("目标数据:")
        stats_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        stats_title.setAlignment(Qt.AlignCenter)
        stats_title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        stats_layout.addWidget(stats_title)

        # 目标数量网格布局
        target_grid = QGridLayout()
        target_grid.setVerticalSpacing(6)
        target_grid.setHorizontalSpacing(8)

        # 各类目标数量标签
        target_types = ["行人", "小汽车", "两轮车", "公交车", "卡车"]
        target_colors = ["#9b59b6", "#3498db", "#e74c3c", "#1abc9c", "#f1c40f"]

        # 创建目标类型标签和计数标签
        self.target_count_labels = {}

        for i, (target_type, color) in enumerate(zip(target_types, target_colors)):
            # 类别标签
            type_label = QLabel(target_type)
            type_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            target_grid.addWidget(type_label, i, 0)

            # 计数标签
            count_label = QLabel("0")
            count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_label.setStyleSheet(f"color: {color}; font-size: 12px;")
            target_grid.addWidget(count_label, i, 1)

            # 进度条
            progress_bar = QProgressBar()
            progress_bar.setMaximum(100)
            progress_bar.setValue(0)
            progress_bar.setFixedHeight(12)
            progress_bar.setTextVisible(False)
            progress_bar.setStyleSheet(f"""
                QProgressBar::chunk {{
                    background-color: {color};
                }}
            """)
            target_grid.addWidget(progress_bar, i, 2)

            # 保存引用
            self.target_count_labels[target_type] = (count_label, progress_bar)

        stats_layout.addLayout(target_grid)
        left_panel_layout.addWidget(stats_frame)

        # ===== 配置信息区域 =====
        conf_frame = QFrame()
        conf_frame.setFrameShape(QFrame.StyledPanel)
        conf_layout = QVBoxLayout(conf_frame)
        conf_layout.setContentsMargins(10, 10, 10, 10)
        conf_layout.setSpacing(8)

        # 模型参数行
        conf_row = QHBoxLayout()

        # CONF标签
        self.conf_value_label = QLabel(f"CONF: {self.conf_value:.2f}")
        self.conf_value_label.setFont(QFont("Microsoft YaHei", 10))
        conf_row.addWidget(self.conf_value_label)

        # CONF进度条
        self.conf_progress = QProgressBar()
        self.conf_progress.setMinimum(0)
        self.conf_progress.setMaximum(100)
        self.conf_progress.setValue(int(self.conf_value * 100))
        self.conf_progress.setFixedHeight(12)
        self.conf_progress.setTextVisible(False)
        self.conf_progress.valueChanged.connect(self._on_conf_changed)
        # 启用鼠标拖动功能
        self.conf_progress.setMouseTracking(True)
        self.conf_progress.mousePressEvent = self._on_conf_progress_click
        conf_row.addWidget(self.conf_progress)

        conf_layout.addLayout(conf_row)

        # IOU行
        iou_row = QHBoxLayout()

        # IOU标签
        self.iou_value_label = QLabel(f"IOU: {self.iou_value:.2f}")
        self.iou_value_label.setFont(QFont("Microsoft YaHei", 10))
        iou_row.addWidget(self.iou_value_label)

        # IOU进度条
        self.iou_progress = QProgressBar()
        self.iou_progress.setMinimum(0)
        self.iou_progress.setMaximum(100)
        self.iou_progress.setValue(int(self.iou_value * 100))
        self.iou_progress.setFixedHeight(12)
        self.iou_progress.setTextVisible(False)
        self.iou_progress.valueChanged.connect(self._on_iou_changed)
        # 启用鼠标拖动功能
        self.iou_progress.setMouseTracking(True)
        self.iou_progress.mousePressEvent = self._on_iou_progress_click
        iou_row.addWidget(self.iou_progress)

        conf_layout.addLayout(iou_row)

        # 用时信息
        time_row = QHBoxLayout()

        # 时钟图标
        time_icon = QLabel("⏱")
        time_icon.setFont(QFont("Arial", 12))
        time_row.addWidget(time_icon)

        # 用时标签
        time_label = QLabel("用时:")
        time_label.setFont(QFont("Microsoft YaHei", 10))
        time_row.addWidget(time_label)

        # 用时值
        self.time_value_label = QLabel("0 s")
        self.time_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        time_row.addWidget(self.time_value_label)

        conf_layout.addLayout(time_row)

        # 目标数目
        target_row = QHBoxLayout()

        # 目标图标
        target_icon = QLabel("🎯")
        target_icon.setFont(QFont("Arial", 12))
        target_row.addWidget(target_icon)

        # 目标标签
        target_label = QLabel("目标数目:")
        target_label.setFont(QFont("Microsoft YaHei", 10))
        target_row.addWidget(target_label)

        # 目标值
        self.target_value_label = QLabel("0")
        self.target_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        target_row.addWidget(self.target_value_label)

        conf_layout.addLayout(target_row)

        left_panel_layout.addWidget(conf_frame)

        # 让统计信息区域占用剩余空间
        left_panel_layout.addStretch(1)

        # ===== 右侧显示区域 =====
        right_panel = QFrame()
        right_panel.setFrameShape(QFrame.StyledPanel)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        # 主显示区域
        display_frame = QFrame()
        display_frame.setFrameShape(QFrame.StyledPanel)
        display_frame.setStyleSheet("background-color: #282c34;")  # 暗色背景
        display_layout = QVBoxLayout(display_frame)

        # 显示标签
        self.display_label = QLabel()
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("border: none;")

        # 默认显示占位图
        placeholder_path = os.path.join("resources", "images", "placeholder.png")
        if os.path.exists(placeholder_path):
            placeholder_pixmap = QPixmap(placeholder_path)
            self.display_label.setPixmap(placeholder_pixmap.scaled(
                640, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        else:
            self.display_label.setText("请选择图像或视频文件进行检测")
            self.display_label.setStyleSheet("color: white; font-size: 16px;")

        display_layout.addWidget(self.display_label)

        # 添加图片导航控制按钮
        nav_layout = QHBoxLayout()

        # 上一张按钮
        self.prev_image_btn = QPushButton("上一张")
        self.prev_image_btn.setIcon(QIcon(os.path.join("resources", "icons", "previous.png")))
        self.prev_image_btn.clicked.connect(self._on_prev_image_clicked)
        self.prev_image_btn.setEnabled(False)
        self.prev_image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        nav_layout.addWidget(self.prev_image_btn)

        # 图片索引指示器
        self.image_index_label = QLabel("0/0")
        self.image_index_label.setAlignment(Qt.AlignCenter)
        self.image_index_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        self.image_index_label.setMinimumWidth(100)
        nav_layout.addWidget(self.image_index_label)

        # 下一张按钮
        self.next_image_btn = QPushButton("下一张")
        self.next_image_btn.setIcon(QIcon(os.path.join("resources", "icons", "next.png")))
        self.next_image_btn.clicked.connect(self._on_next_image_clicked)
        self.next_image_btn.setEnabled(False)
        self.next_image_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        nav_layout.addWidget(self.next_image_btn)

        display_layout.addLayout(nav_layout)
        right_layout.addWidget(display_frame, 7)  # 分配70%的空间

        # 检测结果表格
        table_frame = QFrame()
        table_frame.setFrameShape(QFrame.StyledPanel)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(5, 5, 5, 5)

        # 表格标题
        table_title = QLabel("检测结果")
        table_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        table_title.setAlignment(Qt.AlignCenter)
        table_title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        table_layout.addWidget(table_title)

        # 创建表格
        self.result_table = QTableWidget(0, 5)  # 序号, 画面标识, 结果, 位置, 置信度
        self.result_table.setHorizontalHeaderLabels(["序号", "画面标识", "结果", "位置", "置信度"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 不可编辑
        self.result_table.setAlternatingRowColors(True)  # 交替行颜色
        self.result_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f0f0f0;
            }
        """)

        table_layout.addWidget(self.result_table)
        right_layout.addWidget(table_frame, 3)  # 分配30%的空间

        # 将左右面板添加到主布局
        main_layout.addWidget(left_panel, 1)  # 左侧占比25%
        main_layout.addWidget(right_panel, 3)  # 右侧占比75%

    def _on_select_image_clicked(self):
        """选择图片按钮点击处理"""
        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp)"
        )

        if not file_path:
            return

        try:
            # 记录开始时间
            start_time = time.time()

            # 检测图片，使用当前设置的置信度和IOU阈值
            original_img = cv2.imread(file_path)
            original_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)

            # 执行检测，使用当前设置的置信度和IOU阈值
            results = self.detector.model(original_img, conf=self.conf_value, iou=self.iou_value)[0]

            # 统计各类别数量
            class_counts = self.detector._count_objects(results)

            # 在图像上绘制边界框和标签
            processed_img = self.detector._draw_boxes(original_img.copy(), results)

            # 计算用时
            elapsed_time = time.time() - start_time

            # 更新用时显示
            self.time_value_label.setText(f"{elapsed_time:.2f} s")

            # 更新目标数目
            total_objects = sum(class_counts.values())
            self.target_value_label.setText(str(total_objects))

            # 更新统计数据
            for target_type, (count_label, progress_bar) in self.target_count_labels.items():
                count_label.setText(str(class_counts.get(target_type, 0)))
                progress_bar.setValue(0)

            # 显示处理后的图片
            h, w = processed_img.shape[:2]
            # 计算合适的显示尺寸，保持纵横比
            display_w = self.display_label.width()
            display_h = int(display_w * h / w)

            pixmap = cv2_to_qpixmap(processed_img, (display_w, display_h))
            self.display_label.setPixmap(pixmap)

            # 更新检测结果表格
            self._update_result_table(file_path, processed_img)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理图片时出错: {str(e)}")

    def _on_select_video_clicked(self):
        """选择视频按钮点击处理"""
        # 如果已经在处理视频，则停止
        if self.is_processing_video:
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.stop()
                self.video_thread.wait()

            self.is_processing_video = False
            self.select_video_btn.setText("选择视频文件")
            self.select_video_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-size: 16px; border-radius: 5px;"
            )
            return

        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频",
            "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv)"
        )

        if not file_path:
            return

        try:
            # 创建并启动视频处理线程
            self.video_thread = VideoProcessThread(self.detector, file_path)
            self.video_thread.frame_ready.connect(self._update_video_frame)
            self.video_thread.video_finished.connect(self._on_video_finished)
            self.video_thread.start()

            # 更新状态
            self.is_processing_video = True
            self.select_video_btn.setText("停止视频")
            self.select_video_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-size: 16px; border-radius: 5px;"
            )

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理视频时出错: {str(e)}")

    def _update_video_frame(self, processed_frame, class_counts):
        """更新视频帧
        
        Args:
            processed_frame: 处理后的帧
            class_counts: 各类别数量统计
        """
        # 更新统计数据
        for target_type, (count_label, progress_bar) in self.target_count_labels.items():
            count_label.setText(str(class_counts.get(target_type, 0)))
            progress_bar.setValue(0)

        # 更新目标数目
        total_objects = sum(class_counts.values())
        self.target_value_label.setText(str(total_objects))

        # 显示处理后的帧
        h, w = processed_frame.shape[:2]
        # 计算合适的显示尺寸，保持纵横比
        display_w = self.display_label.width()
        display_h = int(display_w * h / w)

        pixmap = cv2_to_qpixmap(processed_frame, (display_w, display_h))
        self.display_label.setPixmap(pixmap)

        # 更新检测结果表格，传递轨迹信息
        if self.is_processing_video and self.video_thread:
            self._update_result_table("视频帧", processed_frame, self.video_thread.tracks,
                                      self.video_thread.previous_boxes)
        else:
            self._update_result_table("视频帧", processed_frame)

    def _on_video_finished(self):
        """视频处理完成处理"""
        # 更新状态
        self.is_processing_video = False
        self.select_video_btn.setText("选择视频文件")
        self.select_video_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-size: 16px; border-radius: 5px;"
        )

        QMessageBox.information(self, "处理完成", "视频处理已完成")

    def _update_result_table(self, source_name, processed_img, tracks=None, previous_boxes=None):
        """更新检测结果表格
        
        Args:
            source_name: 图像来源名称
            processed_img: 处理后的图像
            tracks: 目标轨迹字典，可选
            previous_boxes: 上一帧检测框字典，可选
        """
        # 修改表格列数，增加轨迹ID列
        if self.result_table.columnCount() == 5:
            self.result_table.setColumnCount(6)  # 序号, 轨迹ID, 画面标识, 结果, 位置, 置信度
            self.result_table.setHorizontalHeaderLabels(["序号", "轨迹ID", "画面标识", "结果", "位置", "置信度"])

        # 清空表格
        self.result_table.setRowCount(0)

        # 重新获取检测结果
        try:
            # 将RGB图像转换为BGR，以便与YOLO模型兼容
            img_bgr = cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR)

            # 执行检测，使用当前设置的置信度和IOU阈值
            results = self.detector.model(img_bgr, conf=self.conf_value, iou=self.iou_value)[0]

            # 获取所有检测框
            row_index = 0

            # 检查是否有轨迹数据
            track_id_map = {}
            if tracks and previous_boxes:
                # 构建中心点到轨迹ID的映射
                for track_id, box_data in previous_boxes.items():
                    x_center, y_center = int(box_data[0]), int(box_data[1])
                    # 使用位置作为键，可能存在多个目标位置相同的情况
                    track_id_map[(x_center, y_center)] = track_id

            for box in results.boxes:
                self.result_table.insertRow(row_index)

                # 获取坐标和置信度
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf.item())
                cls_id = int(box.cls.item())
                cls_name = self.detector.class_names[cls_id]

                # 计算中心点（用于匹配轨迹ID）
                x_center = int((x1 + x2) / 2)
                y_center = int((y1 + y2) / 2)

                # 查找轨迹ID
                track_id = -1
                if track_id_map:
                    # 寻找最近的轨迹点
                    min_distance = float('inf')
                    for pos, tid in track_id_map.items():
                        distance = ((pos[0] - x_center) ** 2 + (pos[1] - y_center) ** 2) ** 0.5
                        if distance < min_distance and distance < 30:  # 设置距离阈值为30像素
                            min_distance = distance
                            track_id = tid

                # 仅处理已映射的类别
                if cls_name in self.detector.CLASS_MAPPING:
                    cn_name = self.detector.CLASS_MAPPING[cls_name]

                    # 序号
                    self.result_table.setItem(row_index, 0, QTableWidgetItem(str(row_index + 1)))

                    # 轨迹ID
                    track_id_item = QTableWidgetItem(str(track_id) if track_id >= 0 else "无")
                    if track_id >= 0:
                        # 为不同轨迹ID设置不同的背景颜色
                        colors = [QColor(255, 200, 200), QColor(200, 255, 200),
                                  QColor(200, 200, 255), QColor(255, 255, 200),
                                  QColor(255, 200, 255), QColor(200, 255, 255)]
                        track_id_item.setBackground(colors[track_id % len(colors)])
                    self.result_table.setItem(row_index, 1, track_id_item)

                    # 画面标识
                    source_item = QTableWidgetItem(
                        os.path.basename(str(source_name)) if isinstance(source_name, str) else str(source_name))
                    self.result_table.setItem(row_index, 2, source_item)

                    # 结果
                    self.result_table.setItem(row_index, 3, QTableWidgetItem(cn_name))

                    # 位置
                    position = f"({x1},{y1})-({x2},{y2})"
                    self.result_table.setItem(row_index, 4, QTableWidgetItem(position))

                    # 置信度
                    conf_str = f"{conf:.2f}"
                    conf_item = QTableWidgetItem(conf_str)
                    self.result_table.setItem(row_index, 5, conf_item)

                    row_index += 1
        except Exception as e:
            print(f"更新检测结果表格时出错: {str(e)}")

    def _on_save_results_clicked(self):
        """保存检测结果按钮点击处理"""
        # 检查是否有检测结果
        if self.result_table.rowCount() == 0:
            QMessageBox.warning(self, "警告", "没有检测结果可保存！")
            return

        # 创建保存目录
        save_dir = os.path.join("results", time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(save_dir, exist_ok=True)

        try:
            # 保存结果数据到CSV文件
            csv_path = os.path.join(save_dir, "detection_results.csv")
            with open(csv_path, 'w', encoding='utf-8') as f:
                # 写入CSV头部
                f.write("序号,画面标识,结果类别,位置坐标,置信度\n")

                # 写入每一行数据
                for row in range(self.result_table.rowCount()):
                    row_data = []
                    for col in range(self.result_table.columnCount()):
                        item = self.result_table.item(row, col)
                        if item is not None:
                            # 确保CSV中的文本字段被引号包围，避免逗号导致的分隔问题
                            text = item.text().replace('"', '""')  # 转义双引号
                            row_data.append(f'"{text}"')
                        else:
                            row_data.append('""')
                    f.write(','.join(row_data) + '\n')

            # 如果正在处理视频，询问是否要保存视频
            if self.is_processing_video and self.video_thread and self.video_thread.isRunning():
                reply = QMessageBox.question(
                    self,
                    "保存视频",
                    "是否要保存当前的视频处理结果？\n(这可能需要一些时间)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Yes:
                    # 使用QProgressDialog替代QMessageBox作为进度显示
                    progress_dialog = QProgressDialog("正在准备保存视频...", "取消", 0, 100, self)
                    progress_dialog.setWindowTitle("保存中")
                    progress_dialog.setMinimumDuration(0)
                    progress_dialog.setWindowModality(Qt.WindowModal)
                    progress_dialog.setValue(10)
                    progress_dialog.setCancelButton(None)  # 禁用取消按钮，防止用户中断

                    # 开始保存帧
                    self.video_thread.start_saving_frames()

                    # 等待几秒钟收集足够的帧
                    seconds_to_wait = 5
                    for i in range(seconds_to_wait):
                        # 更新进度条
                        progress_percent = 10 + int((i + 1) / seconds_to_wait * 40)  # 10-50%
                        progress_dialog.setValue(progress_percent)
                        progress_dialog.setLabelText(f"正在收集视频帧... ({i + 1}/{seconds_to_wait})")

                        QApplication.processEvents()  # 保持UI响应
                        time.sleep(1)

                    # 停止保存帧
                    self.video_thread.stop_saving_frames()

                    # 保存视频
                    progress_dialog.setValue(60)
                    progress_dialog.setLabelText("正在保存视频文件...")
                    QApplication.processEvents()

                    video_path = os.path.join(save_dir, "detection_video.mp4")
                    save_success = self.video_thread.save_video(video_path)

                    # 无论成功与否，都确保进度对话框完成并关闭
                    progress_dialog.setValue(100)
                    progress_dialog.close()

                    if save_success:
                        QMessageBox.information(
                            self,
                            "保存成功",
                            f"检测结果已保存至:\n{save_dir}\n\n包含CSV文件和检测视频。"
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "视频保存失败",
                            f"视频保存失败，但CSV文件已保存至:\n{save_dir}"
                        )
                else:
                    # 只保存当前显示的图像
                    if self.display_label.pixmap() and not self.display_label.pixmap().isNull():
                        image_path = os.path.join(save_dir, "detection_image.png")
                        self.display_label.pixmap().save(image_path, "PNG")

                    QMessageBox.information(
                        self,
                        "保存成功",
                        f"检测结果已保存至:\n{save_dir}\n\n包含CSV文件和当前帧图像。"
                    )
            else:
                # 保存当前显示的图像（非视频模式）
                if self.display_label.pixmap() and not self.display_label.pixmap().isNull():
                    image_path = os.path.join(save_dir, "detection_image.png")
                    self.display_label.pixmap().save(image_path, "PNG")

                QMessageBox.information(
                    self,
                    "保存成功",
                    f"检测结果已保存至:\n{save_dir}\n\n包含CSV文件和检测图像。"
                )

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存检测结果时出错: {str(e)}")

    def _on_conf_progress_click(self, event):
        """置信度进度条点击事件处理"""
        if event.button() == Qt.LeftButton:
            # 计算点击位置对应的数值（0-100）
            width = self.conf_progress.width()
            pos = event.position().x() if hasattr(event, 'position') else event.x()
            value = max(0, min(100, int(pos / width * 100)))
            self.conf_progress.setValue(value)

    def _on_iou_progress_click(self, event):
        """IOU进度条点击事件处理"""
        if event.button() == Qt.LeftButton:
            # 计算点击位置对应的数值（0-100）
            width = self.iou_progress.width()
            pos = event.position().x() if hasattr(event, 'position') else event.x()
            value = max(0, min(100, int(pos / width * 100)))
            self.iou_progress.setValue(value)

    def _on_conf_changed(self, value):
        """置信度值变化处理"""
        # 将进度条值（0-100）转换为置信度（0-1）
        self.conf_value = value / 100.0
        # 更新置信度标签
        self.conf_value_label.setText(f"CONF: {self.conf_value:.2f}")
        # 更新检测器的置信度阈值
        self.detector.conf_threshold = self.conf_value

    def _on_iou_changed(self, value):
        """IOU值变化处理"""
        # 将进度条值（0-100）转换为IOU（0-1）
        self.iou_value = value / 100.0
        # 更新IOU标签
        self.iou_value_label.setText(f"IOU: {self.iou_value:.2f}")
        # 更新检测器的NMS IOU阈值
        if hasattr(self.detector.model, 'iou'):
            self.detector.model.iou = self.iou_value

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 如果正在处理视频，则停止线程
        if self.is_processing_video and self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread.wait()

        event.accept()

    def _on_select_model_clicked(self):
        """选择模型按钮点击处理"""
        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择YOLO模型",
            "",
            "模型文件 (*.pt *.pth)"
        )

        if not file_path:
            return

        try:
            # 确认是否切换模型
            reply = QMessageBox.question(
                self,
                "确认切换模型",
                f"确定加载模型：{file_path}？\n加载新模型可能需要几秒钟的时间。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 显示加载进度对话框
                progress_dialog = QProgressDialog("正在加载模型...", "取消", 0, 0, self)
                progress_dialog.setWindowTitle("加载模型")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.show()

                # 创建新的检测器
                QApplication.processEvents()
                self.detector = YOLODetector(model_path=file_path,
                                             conf_threshold=self.conf_value,
                                             iou_threshold=self.iou_value)

                # 关闭进度对话框
                progress_dialog.close()

                # 显示成功消息
                QMessageBox.information(
                    self,
                    "模型加载成功",
                    f"模型 {Path(file_path).name} 已成功加载。"
                )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载模型时出错: {str(e)}")

    def _on_select_image_list_clicked(self):
        """选择图片列表按钮点击处理"""
        # 打开文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择包含图片的文件夹",
            ""
        )

        if not folder_path:
            return

        try:
            # 搜索文件夹中的所有图片文件
            supported_formats = ['.jpg', '.jpeg', '.png', '.bmp']
            file_paths = []

            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in supported_formats):
                        file_paths.append(os.path.join(root, file))

            # 如果没有找到图片文件
            if not file_paths:
                QMessageBox.warning(
                    self,
                    "未找到图片",
                    f"在选择的文件夹中未找到支持的图片文件。\n支持的格式: {', '.join(supported_formats)}"
                )
                return

            # 创建批量处理进度对话框
            progress_dialog = QProgressDialog("正在处理图片...", "取消", 0, len(file_paths), self)
            progress_dialog.setWindowTitle("批量处理图片")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.show()

            # 记录开始时间
            start_time = time.time()

            # 清空之前的批量处理结果
            self.batch_results = []
            self.current_batch_index = -1

            # 创建保存结果的目录
            batch_save_dir = os.path.join("results",
                                          f"批量检测_{Path(folder_path).name}_{time.strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(batch_save_dir, exist_ok=True)

            # 创建CSV文件记录所有检测结果
            csv_path = os.path.join(batch_save_dir, "检测结果统计.csv")
            with open(csv_path, 'w', encoding='utf-8-sig') as csv_file:
                # 写入CSV头部
                csv_file.write("文件名,行人,小汽车,两轮车,公交车,卡车,总目标数\n")

                # 批量处理图片
                for i, file_path in enumerate(file_paths):
                    # 更新进度
                    progress_dialog.setValue(i)
                    progress_dialog.setLabelText(f"正在处理图片 {i + 1}/{len(file_paths)}: {Path(file_path).name}")
                    QApplication.processEvents()

                    # 检查是否取消
                    if progress_dialog.wasCanceled():
                        break

                    try:
                        # 执行检测
                        original_img = cv2.imread(file_path)
                        if original_img is None:
                            continue  # 跳过无法读取的图片

                        original_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)

                        # 执行检测，使用当前设置的置信度和IOU阈值
                        results = self.detector.model(original_img, conf=self.conf_value, iou=self.iou_value)[0]

                        # 统计各类别数量
                        class_counts = self.detector._count_objects(results)

                        # 在图像上绘制边界框和标签
                        processed_img = self.detector._draw_boxes(original_img.copy(), results)

                        # 获取相对路径和文件名
                        rel_path = os.path.relpath(file_path, folder_path)
                        file_name = Path(file_path).name

                        # 创建保存子目录结构（如果需要）
                        rel_dir = os.path.dirname(rel_path)
                        if rel_dir:
                            os.makedirs(os.path.join(batch_save_dir, rel_dir), exist_ok=True)

                        # 保存处理后的图片
                        out_path = os.path.join(batch_save_dir, rel_dir, f"{Path(file_name).stem}_检测结果.jpg")
                        cv2.imwrite(out_path, cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR))

                        # 写入CSV记录
                        total_count = sum(class_counts.values())
                        csv_line = f'"{rel_path}",'
                        csv_line += f'{class_counts.get("行人", 0)},'
                        csv_line += f'{class_counts.get("小汽车", 0)},'
                        csv_line += f'{class_counts.get("两轮车", 0)},'
                        csv_line += f'{class_counts.get("公交车", 0)},'
                        csv_line += f'{class_counts.get("卡车", 0)},'
                        csv_line += f'{total_count}\n'
                        csv_file.write(csv_line)

                        # 保存结果到批量处理列表中
                        self.batch_results.append({
                            'path': file_path,
                            'processed_img': processed_img,
                            'class_counts': class_counts,
                            'output_path': out_path,
                            'rel_path': rel_path
                        })

                    except Exception as e:
                        print(f"处理图片 {file_path} 时出错: {str(e)}")
                        continue  # 跳过处理失败的图片

            # 完成进度
            progress_dialog.setValue(len(file_paths))

            # 计算总用时
            elapsed_time = time.time() - start_time
            self.time_value_label.setText(f"{elapsed_time:.2f} s")

            # 如果有任何处理成功的图片
            successfully_processed = len(self.batch_results)
            if successfully_processed > 0:
                # 更新批量处理索引到第一张图片
                self.current_batch_index = 0
                self._update_batch_image_display()

                # 更新导航按钮状态
                self._update_navigation_buttons()

                # 显示处理成功的消息
                QMessageBox.information(
                    self,
                    "批量处理完成",
                    f"已成功处理 {successfully_processed}/{len(file_paths)} 张图片。\n\n"
                    f"所有检测结果已自动保存至：\n{batch_save_dir}\n\n"
                    f"使用上一张/下一张按钮可以浏览所有处理结果。"
                )
            else:
                QMessageBox.warning(
                    self,
                    "处理失败",
                    "没有成功处理任何图片，请检查图片格式或模型设置。"
                )

        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量处理图片时出错: {str(e)}")

    def _on_prev_image_clicked(self):
        """上一张图片按钮点击处理"""
        if not self.batch_results or self.current_batch_index <= 0:
            return

        self.current_batch_index -= 1
        self._update_batch_image_display()
        self._update_navigation_buttons()

    def _on_next_image_clicked(self):
        """下一张图片按钮点击处理"""
        if not self.batch_results or self.current_batch_index >= len(self.batch_results) - 1:
            return

        self.current_batch_index += 1
        self._update_batch_image_display()
        self._update_navigation_buttons()

    def _update_batch_image_display(self):
        """更新批量处理图片显示"""
        if not self.batch_results or self.current_batch_index < 0 or self.current_batch_index >= len(
                self.batch_results):
            return

        # 获取当前索引的处理结果
        result = self.batch_results[self.current_batch_index]

        # 更新索引标签
        self.image_index_label.setText(f"{self.current_batch_index + 1}/{len(self.batch_results)}")

        # 更新统计数据
        class_counts = result['class_counts']
        for target_type, (count_label, progress_bar) in self.target_count_labels.items():
            count = class_counts.get(target_type, 0)
            count_label.setText(str(count))

            # 更新进度条（相对于最大值计算百分比）
            max_count = max(max(class_counts.values()), 1)  # 避免除以零
            percentage = int((count / max_count) * 100)
            progress_bar.setValue(percentage)

        # 更新目标数目
        total_objects = sum(class_counts.values())
        self.target_value_label.setText(str(total_objects))

        # 显示处理后的图片
        processed_img = result['processed_img']
        h, w = processed_img.shape[:2]
        # 计算合适的显示尺寸，保持纵横比
        display_w = self.display_label.width()
        display_h = int(display_w * h / w)

        pixmap = cv2_to_qpixmap(processed_img, (display_w, display_h))
        self.display_label.setPixmap(pixmap)

        # 更新检测结果表格
        self._update_result_table(result['rel_path'], processed_img)

    def _update_navigation_buttons(self):
        """更新导航按钮状态"""
        # 启用/禁用上一张按钮
        self.prev_image_btn.setEnabled(self.batch_results and self.current_batch_index > 0)

        # 启用/禁用下一张按钮
        self.next_image_btn.setEnabled(self.batch_results and self.current_batch_index < len(self.batch_results) - 1)
