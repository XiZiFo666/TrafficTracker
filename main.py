#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QStackedWidget, QMessageBox, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtCore import Qt

from ui.login import LoginWindow
from ui.register import RegisterWindow
from database.database import Database


class MockMainWindow(QWidget):
    """模拟主窗口，在无法加载YOLO模型时使用"""
    
    def __init__(self, username=None, avatar_path=None):
        super().__init__()
        
        # 用户信息
        self.username = username
        self.avatar_path = avatar_path
        
        # 设置窗口属性
        self.setWindowTitle("车辆行人检测系统 - 模型加载失败")
        self.resize(800, 600)
        
        # 创建UI
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        # 主布局
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 添加图标
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        warning_pixmap = QPixmap(os.path.join("resources", "icons", "warning.png"))
        if not warning_pixmap.isNull():
            icon_label.setPixmap(warning_pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_label.setText("⚠️")
            icon_label.setStyleSheet("font-size: 72px; color: #e74c3c;")
        layout.addWidget(icon_label)
        
        # 添加错误提示
        error_label = QLabel("YOLO模型加载失败")
        error_label.setFont(QFont("Arial", 24, QFont.Bold))
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: #e74c3c;")
        layout.addWidget(error_label)
        
        # 添加详细说明
        detail_label = QLabel(
            "无法加载YOLOv8检测模型。请确保以下事项：\n"
            "1. 已安装ultralytics库 (pip install ultralytics)\n"
            "2. YOLOv8模型文件(best.pt)存在且格式正确\n"
            "3. 已激活含有所需依赖的conda环境 (conda activate YOLOv8)"
        )
        detail_label.setFont(QFont("Arial", 12))
        detail_label.setAlignment(Qt.AlignCenter)
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)
        
        # 添加用户信息
        user_label = QLabel(f"已登录用户: {self.username}")
        user_label.setFont(QFont("Arial", 12))
        user_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(user_label)
        
    def update_user_info(self, username, avatar_path=None):
        """更新用户信息（兼容接口）"""
        self.username = username


class App(QStackedWidget):
    """应用程序主类，管理不同页面的切换"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化数据库
        self.db = Database()
        
        # 设置窗口属性
        self.setWindowTitle("基于YOLOv8的车辆行人检测系统")
        self.setFixedSize(400, 300)
        
        # 创建图标目录
        os.makedirs(os.path.join("resources", "icons"), exist_ok=True)
        os.makedirs(os.path.join("resources", "user_avatars"), exist_ok=True)
        
        # 初始化页面
        self._init_pages()
        
        # 显示登录页面
        self.show_login_page()
        
    def _init_pages(self):
        """初始化各个页面"""
        # 登录页面
        self.login_page = LoginWindow()
        self.login_page.login_success.connect(self._on_login_success)
        self.login_page.switch_to_register.connect(self.show_register_page)
        self.addWidget(self.login_page)
        
        # 注册页面
        self.register_page = RegisterWindow()
        self.register_page.switch_to_login.connect(self.show_login_page)
        self.addWidget(self.register_page)
        
        # 主页面（初始为None，在登录成功后创建）
        self.main_page = None
        
    def show_login_page(self):
        """显示登录页面"""
        self.setCurrentWidget(self.login_page)
        
    def show_register_page(self):
        """显示注册页面"""
        self.setCurrentWidget(self.register_page)
        
    def _on_login_success(self, username):
        """登录成功处理
        
        Args:
            username: 用户名
        """
        # 获取用户头像路径
        avatar_path = self.db.get_user_avatar(username)
        
        # 如果主窗口尚未创建，则创建一个
        if self.main_page is None:
            try:
                # 尝试导入主窗口
                try:
                    from ui.main_window import MainWindow
                    self.main_page = MainWindow(username, avatar_path)
                except ImportError as e:
                    # 如果模块导入失败，显示错误信息并使用模拟主窗口
                    QMessageBox.warning(
                        self, 
                        "模块导入错误", 
                        f"无法导入主窗口模块: {str(e)}\n使用模拟主窗口替代。"
                    )
                    self.main_page = MockMainWindow(username, avatar_path)
                except Exception as e:
                    # 加载主窗口失败，可能是模型问题，使用模拟主窗口
                    QMessageBox.warning(
                        self,
                        "模型加载错误",
                        f"加载YOLO模型失败: {str(e)}\n请确保已安装所需依赖并激活相应环境。"
                    )
                    self.main_page = MockMainWindow(username, avatar_path)
                    
                self.addWidget(self.main_page)
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "错误", 
                    f"加载主窗口时出错: {str(e)}"
                )
                return
        else:
            # 更新主窗口的用户信息
            self.main_page.update_user_info(username, avatar_path)
        
        # 显示主窗口
        self.setCurrentWidget(self.main_page)
        self.setFixedSize(1280, 720)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec()) 