#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox
)

from database.database import Database
from ui.forgot_password import ForgotPasswordWindow


class LoginWindow(QWidget):
    """登录窗口"""
    
    # 定义信号
    login_success = Signal(str)  # 登录成功信号，传递用户名
    switch_to_register = Signal()  # 切换到注册页面信号
    
    def __init__(self):
        super().__init__()
        
        # 初始化数据库
        self.db = Database()
        
        # 设置窗口属性
        self.setWindowTitle("车辆行人检测系统 - 登录")
        self.setFixedSize(400, 300)
        
        # 创建UI
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)
        
        # 头像部分
        avatar_layout = QHBoxLayout()
        avatar_label = QLabel()
        avatar_label.setFixedSize(80, 80)  # 设置固定大小
        avatar_label.setAlignment(Qt.AlignCenter)  # 居中对齐
        
        # 尝试加载头像图片 (注意修正了路径为avator.jpg)
        avatar_pixmap = QPixmap(os.path.join("resources", "icons", "avator.jpg"))
        if avatar_pixmap.isNull():
            # 如果找不到图标，使用文字代替
            avatar_label.setText("👤")
            avatar_label.setStyleSheet("font-size: 40px; color: #3498db; background-color: #ecf0f1; border-radius: 40px;")
        else:
            # 缩放图片并设置为圆形
            scaled_pixmap = avatar_pixmap.scaled(
                80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            avatar_label.setPixmap(scaled_pixmap)
            avatar_label.setStyleSheet("border-radius: 40px; background-color: #ecf0f1;")
        
        avatar_layout.addStretch()
        avatar_layout.addWidget(avatar_label)
        avatar_layout.addStretch()
        main_layout.addLayout(avatar_layout)
        main_layout.addSpacing(20)
        
        # 用户名
        username_layout = QHBoxLayout()
        username_icon = QLabel("👤")
        username_layout.addWidget(username_icon)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("用户名")
        self.username_input.setMinimumHeight(40)
        username_layout.addWidget(self.username_input)
        
        main_layout.addLayout(username_layout)
        main_layout.addSpacing(10)
        
        # 密码
        password_layout = QHBoxLayout()
        password_icon = QLabel("🔒")
        password_layout.addWidget(password_icon)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        password_layout.addWidget(self.password_input)
        
        main_layout.addLayout(password_layout)
        main_layout.addSpacing(20)
        
        # 登录按钮
        self.login_button = QPushButton("登录")
        self.login_button.setMinimumHeight(40)
        self.login_button.setStyleSheet(
            "background-color: #3498db; color: white; font-size: 16px; border-radius: 5px;"
        )
        self.login_button.clicked.connect(self._on_login_button_clicked)
        main_layout.addWidget(self.login_button)
        
        # 记住密码和忘记密码
        checkbox_layout = QHBoxLayout()
        
        self.remember_password = QLabel("记住密码")
        self.remember_password.setStyleSheet("color: gray; font-size: 12px;")
        checkbox_layout.addWidget(self.remember_password)
        
        checkbox_layout.addStretch()
        
        self.forgot_password = QLabel("忘记密码")
        self.forgot_password.setStyleSheet(
            "color: #3498db; font-size: 12px; text-decoration: underline; cursor: pointer;"
        )
        self.forgot_password.mousePressEvent = self._on_forgot_password_clicked
        checkbox_layout.addWidget(self.forgot_password)
        
        main_layout.addLayout(checkbox_layout)
        main_layout.addStretch()
        
        # 注册账号链接
        register_layout = QHBoxLayout()
        register_layout.addStretch()
        
        self.register_link = QLabel("注册账号")
        self.register_link.setStyleSheet(
            "color: #3498db; font-size: 14px; text-decoration: underline; cursor: pointer;"
        )
        self.register_link.mousePressEvent = self._on_register_link_clicked
        register_layout.addWidget(self.register_link)
        
        main_layout.addLayout(register_layout)
        
    def _on_login_button_clicked(self):
        """登录按钮点击处理"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        # 简单验证
        if not username or not password:
            QMessageBox.warning(self, "登录失败", "用户名和密码不能为空")
            return
            
        # 验证用户
        success, message, _ = self.db.verify_user(username, password)
        
        if success:
            # 登录成功，发送信号
            self.login_success.emit(username)
        else:
            # 登录失败，显示错误信息
            QMessageBox.warning(self, "登录失败", message)
    
    def _on_register_link_clicked(self, event):
        """注册链接点击处理"""
        self.switch_to_register.emit()
    
    def _on_forgot_password_clicked(self, event):
        """忘记密码链接点击处理"""
        # 创建忘记密码窗口
        self.forgot_password_window = ForgotPasswordWindow()
        
        # 连接信号
        self.forgot_password_window.switch_to_login.connect(self.show)
        
        # 隐藏当前窗口并显示忘记密码窗口
        self.hide()
        self.forgot_password_window.show()
        
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._on_login_button_clicked()
        else:
            super().keyPressEvent(event) 