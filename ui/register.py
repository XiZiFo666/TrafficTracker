#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import random
import string
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QFileDialog,
    QComboBox, QGridLayout, QFrame, QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QPen

from database.database import Database


class CaptchaGenerator:
    """验证码生成器"""
    
    def __init__(self, width=100, height=40, length=4):
        """初始化验证码生成器
        
        Args:
            width: 验证码图片宽度
            height: 验证码图片高度
            length: 验证码长度
        """
        self.width = width
        self.height = height
        self.length = length
        
    def generate(self):
        """生成验证码
        
        Returns:
            (QPixmap, str): (验证码图片, 验证码文本)
        """
        # 创建空白图片
        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.white)
        
        # 创建画布
        painter = QPainter(pixmap)
        
        # 随机验证码文本
        captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=self.length))
        
        # 设置字体
        font = QFont("Arial", 20, QFont.Bold)
        painter.setFont(font)
        
        # 绘制文本
        for i, char in enumerate(captcha_text):
            x = i * (self.width / self.length) + random.randint(0, 10)
            y = self.height // 2 + random.randint(-10, 10)
            
            # 随机颜色
            color = QColor(
                random.randint(0, 160),
                random.randint(0, 160),
                random.randint(0, 160)
            )
            painter.setPen(color)
            
            # 旋转
            painter.save()
            painter.translate(x, y)
            painter.rotate(random.randint(-30, 30))
            painter.drawText(0, 0, char)
            painter.restore()
        
        # 添加干扰线
        for _ in range(5):
            color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            painter.setPen(QPen(color, random.randint(1, 2)))
            painter.drawLine(
                random.randint(0, self.width),
                random.randint(0, self.height),
                random.randint(0, self.width),
                random.randint(0, self.height)
            )
            
        # 添加干扰点
        for _ in range(100):
            color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            painter.setPen(color)
            painter.drawPoint(random.randint(0, self.width), random.randint(0, self.height))
        
        painter.end()
        
        return pixmap, captcha_text


class RegisterWindow(QWidget):
    """注册窗口"""
    
    # 定义信号
    register_success = Signal()  # 注册成功信号
    switch_to_login = Signal()  # 切换到登录页面信号
    
    # 预设安全问题列表
    SECURITY_QUESTIONS = [
        "请选择安全问题",
        "您的出生地是?",
        "您母亲的姓名是?",
        "您父亲的姓名是?",
        "您的小学校名是?",
        "您的第一个宠物名字是?",
        "您最喜欢的书籍是?",
        "您最喜欢的电影是?",
        "您的座右铭是?"
    ]
    
    def __init__(self):
        super().__init__()
        
        # 初始化数据库
        self.db = Database()
        
        # 初始化验证码生成器
        self.captcha_generator = CaptchaGenerator()
        self.captcha_text = ""
        
        # 用户头像路径
        self.avatar_path = None
        
        # 设置窗口属性
        self.setWindowTitle("车辆行人检测系统 - 注册")
        # 不设置固定大小，而是允许窗口根据内容调整
        self.setMinimumSize(400, 520)  # 增加最小高度，确保所有内容可见
        
        # 创建UI
        self._init_ui()
        
        # 初始化验证码
        self._refresh_captcha()
    
    def _init_ui(self):
        """初始化UI"""
        # 设置窗口样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                font-family: 'Microsoft YaHei';
            }
            QLabel {
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
                font-size: 12px;
                height: 20px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 5px 10px;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                background-color: white;
                border-radius: 3px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 5px 10px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #3498db;
            }
        """)
        
        # 主布局 - 垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 10, 20, 20)  # 增加底部边距
        main_layout.setSpacing(10)
        
        # 头像部分
        avatar_frame = QFrame()
        avatar_frame.setMaximumHeight(60)
        avatar_layout = QHBoxLayout(avatar_frame)
        
        # 头像标签
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(40, 40)
        self.avatar_label.setStyleSheet("""
            background-color: #e0e0e0;
            border-radius: 20px;
        """)
        
        # 加载默认头像
        default_avatar_path = os.path.join("resources", "icons", "avator.jpg")
        avatar_pixmap = QPixmap(default_avatar_path)
        if not avatar_pixmap.isNull():
            scaled_pixmap = avatar_pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.avatar_label.setPixmap(scaled_pixmap)
            self.avatar_path = default_avatar_path
        else:
            self.avatar_label.setText("👤")
            self.avatar_label.setAlignment(Qt.AlignCenter)
        
        # 选择头像按钮
        avatar_button = QPushButton("选择头像")
        avatar_button.setFixedWidth(70)
        avatar_button.clicked.connect(self._on_select_avatar_clicked)
        
        # 添加到头像布局
        avatar_layout.addStretch(1)
        avatar_layout.addWidget(self.avatar_label)
        avatar_layout.addWidget(avatar_button)
        avatar_layout.addStretch(1)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        tab_widget.setMaximumHeight(320)  # 设置最大高度，确保不会占用太多空间
        
        # 1. 账号信息选项卡
        account_tab = QWidget()
        account_layout = QVBoxLayout(account_tab)
        account_layout.setContentsMargins(10, 10, 10, 10)
        
        account_form = QGridLayout()
        account_form.setVerticalSpacing(10)
        account_form.setHorizontalSpacing(5)
        
        # 用户名
        account_form.addWidget(QLabel("用户名:"), 0, 0)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setMaximumWidth(200)
        account_form.addWidget(self.username_input, 0, 1)
        
        # 密码
        account_form.addWidget(QLabel("密码:"), 1, 0)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMaximumWidth(200)
        account_form.addWidget(self.password_input, 1, 1)
        
        # 确认密码
        account_form.addWidget(QLabel("确认密码:"), 2, 0)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("请再次输入密码")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setMaximumWidth(200)
        account_form.addWidget(self.confirm_password_input, 2, 1)
        
        account_layout.addLayout(account_form)
        account_layout.addStretch(1)
        
        # 2. 安全设置选项卡
        security_tab = QWidget()
        security_layout = QVBoxLayout(security_tab)
        security_layout.setContentsMargins(10, 10, 10, 10)
        
        security_form = QGridLayout()
        security_form.setVerticalSpacing(10)
        security_form.setHorizontalSpacing(5)
        
        # 安全问题
        security_form.addWidget(QLabel("安全问题:"), 0, 0)
        self.security_question_combo = QComboBox()
        self.security_question_combo.addItems(self.SECURITY_QUESTIONS)
        self.security_question_combo.setMaximumWidth(200)
        security_form.addWidget(self.security_question_combo, 0, 1)
        
        # 问题答案
        security_form.addWidget(QLabel("问题答案:"), 1, 0)
        self.security_answer_input = QLineEdit()
        self.security_answer_input.setPlaceholderText("请输入安全问题答案")
        self.security_answer_input.setMaximumWidth(200)
        security_form.addWidget(self.security_answer_input, 1, 1)
        
        # 验证码
        security_form.addWidget(QLabel("验证码:"), 2, 0)
        
        captcha_layout = QHBoxLayout()
        self.captcha_input = QLineEdit()
        self.captcha_input.setPlaceholderText("验证码")
        self.captcha_input.setFixedWidth(70)
        
        self.captcha_label = QLabel()
        self.captcha_label.setFixedSize(80, 30)
        self.captcha_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        self.captcha_label.setCursor(Qt.PointingHandCursor)
        self.captcha_label.setToolTip("点击刷新验证码")
        self.captcha_label.mousePressEvent = lambda _: self._refresh_captcha()
        
        refresh_label = QLabel("点击刷新")
        refresh_label.setStyleSheet("color: #666; font-size: 10px;")
        
        captcha_layout.addWidget(self.captcha_input)
        captcha_layout.addWidget(self.captcha_label)
        captcha_layout.addWidget(refresh_label)
        captcha_layout.addStretch(1)
        
        security_form.addLayout(captcha_layout, 2, 1)
        
        security_layout.addLayout(security_form)
        security_layout.addStretch(1)
        
        # 添加选项卡
        tab_widget.addTab(account_tab, "账号信息")
        tab_widget.addTab(security_tab, "安全设置")
        
        # 按钮区域 - 调整为独立的水平布局直接添加到主布局
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(20, 5, 20, 5)  # 减小顶部边距从15到5
        button_layout.setSpacing(10)
        
        # 返回登录按钮
        back_button = QPushButton("返回登录")
        back_button.setFixedSize(120, 32)  # 按钮宽度增加，高度适中
        back_button.setStyleSheet("""
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 5px 10px;
            font-weight: bold;
            border-radius: 4px;
            font-size: 13px;
        """)
        back_button.clicked.connect(lambda: self.switch_to_login.emit())
        
        # 注册按钮
        self.register_button = QPushButton("注册账号")
        self.register_button.setFixedSize(120, 32)  # 与返回登录按钮保持一致
        self.register_button.setStyleSheet("""
            background-color: #3498db;
            color: white;
            border: none;
            padding: 5px 10px;
            font-weight: bold;
            border-radius: 4px;
            font-size: 13px;
        """)
        self.register_button.clicked.connect(self._on_register_button_clicked)
        
        # 添加按钮到水平布局
        button_layout.addWidget(back_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.register_button)
        
        # 将所有部分添加到主布局，直接添加布局而不是通过Frame
        main_layout.addWidget(avatar_frame)
        main_layout.addWidget(tab_widget)
        main_layout.addLayout(button_layout)  # 直接添加布局，不使用Frame
        main_layout.addStretch(1)  # 添加弹性空间在底部
    
    def _on_select_avatar_clicked(self):
        """选择头像按钮点击处理"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_path:
            self.avatar_path = file_path
            avatar_pixmap = QPixmap(file_path)
            if not avatar_pixmap.isNull():
                scaled_pixmap = avatar_pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.avatar_label.setPixmap(scaled_pixmap)
    
    def _refresh_captcha(self):
        """刷新验证码"""
        captcha_pixmap, self.captcha_text = self.captcha_generator.generate()
        scaled_pixmap = captcha_pixmap.scaled(80, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.captcha_label.setPixmap(scaled_pixmap)
    
    def _on_register_button_clicked(self):
        """注册按钮点击处理"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        confirm_password = self.confirm_password_input.text().strip()
        captcha_input = self.captcha_input.text().strip().upper()
        
        security_question_index = self.security_question_combo.currentIndex()
        security_question = self.security_question_combo.currentText() if security_question_index > 0 else None
        security_answer = self.security_answer_input.text().strip() if security_question_index > 0 else None
        
        # 简单验证
        if not username or not password:
            QMessageBox.warning(self, "注册失败", "用户名和密码不能为空")
            return
            
        if password != confirm_password:
            QMessageBox.warning(self, "注册失败", "两次输入的密码不一致")
            return
            
        if not captcha_input:
            QMessageBox.warning(self, "注册失败", "请输入验证码")
            return
            
        # 验证码校验
        if captcha_input != self.captcha_text:
            QMessageBox.warning(self, "注册失败", "验证码错误")
            self._refresh_captcha()
            return
        
        # 安全问题验证    
        if security_question_index > 0 and not security_answer:
            QMessageBox.warning(self, "注册失败", "请输入安全问题答案")
            return
            
        # 注册用户
        success, message = self.db.register_user(
            username, 
            password, 
            self.avatar_path,
            security_question,
            security_answer
        )
        
        if success:
            # 注册成功，提示并切换到登录页面
            QMessageBox.information(self, "注册成功", message)
            self.switch_to_login.emit()
        else:
            # 注册失败，显示错误信息
            QMessageBox.warning(self, "注册失败", message)
            self._refresh_captcha()
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._on_register_button_clicked()
        else:
            super().keyPressEvent(event) 