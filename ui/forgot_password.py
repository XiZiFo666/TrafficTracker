#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QGridLayout, QFrame, QStackedWidget
)

from database.database import Database


class ForgotPasswordWindow(QWidget):
    """忘记密码窗口"""

    # 定义信号
    switch_to_login = Signal()  # 切换到登录页面信号

    def __init__(self):
        super().__init__()

        # 初始化数据库
        self.db = Database()

        # 设置窗口属性
        self.setWindowTitle("车辆行人检测系统 - 找回密码")
        self.setFixedSize(350, 320)  # 进一步缩小窗口尺寸

        # 创建UI
        self._init_ui()

        # 当前步骤 (0: 验证用户名, 1: 验证安全问题, 2: 重置密码)
        self.current_step = 0

        # 存储验证过程中的数据
        self.verified_username = ""
        self.security_question = ""

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
                padding: 3px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
                font-size: 12px;
                height: 18px;
                max-height: 18px;
                min-height: 18px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 5px 10px;
                font-weight: bold;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QFrame {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)  # 缩小边距
        main_layout.setSpacing(10)  # 减小间距

        # 标题
        title_label = QLabel("找回密码")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        """)
        title_label.setAlignment(Qt.AlignCenter)

        # 步骤提示
        self.step_label = QLabel("第1步: 输入您的用户名")
        self.step_label.setStyleSheet("""
            font-size: 14px;
            color: #7f8c8d;
            margin-bottom: 5px;
        """)
        self.step_label.setAlignment(Qt.AlignCenter)

        # 创建堆叠部件用于管理不同步骤的表单
        self.stacked_widget = QStackedWidget()

        # 1. 用户名验证页面
        username_widget = QWidget()
        username_layout = QVBoxLayout(username_widget)
        username_layout.setContentsMargins(10, 10, 10, 10)  # 缩小内边距
        username_layout.setSpacing(10)

        username_form = QGridLayout()
        username_form.setVerticalSpacing(10)
        username_form.setHorizontalSpacing(10)

        username_form.addWidget(QLabel("用户名:"), 0, 0)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入您的用户名")
        self.username_input.setFixedHeight(25)
        username_form.addWidget(self.username_input, 0, 1)

        username_layout.addLayout(username_form)
        username_layout.addStretch(1)

        # 2. 安全问题验证页面
        security_widget = QWidget()
        security_layout = QVBoxLayout(security_widget)
        security_layout.setContentsMargins(10, 10, 10, 10)  # 缩小内边距
        security_layout.setSpacing(10)

        security_form = QGridLayout()
        security_form.setVerticalSpacing(10)
        security_form.setHorizontalSpacing(10)

        self.security_question_label = QLabel("安全问题:")
        security_form.addWidget(self.security_question_label, 0, 0)
        self.security_answer_input = QLineEdit()
        self.security_answer_input.setPlaceholderText("请输入问题答案")
        self.security_answer_input.setFixedHeight(25)
        security_form.addWidget(self.security_answer_input, 0, 1)

        security_layout.addLayout(security_form)
        security_layout.addStretch(1)

        # 3. 重置密码页面
        reset_widget = QWidget()
        reset_layout = QVBoxLayout(reset_widget)
        reset_layout.setContentsMargins(10, 10, 10, 10)  # 缩小内边距
        reset_layout.setSpacing(10)

        reset_form = QGridLayout()
        reset_form.setVerticalSpacing(10)
        reset_form.setHorizontalSpacing(10)

        reset_form.addWidget(QLabel("新密码:"), 0, 0)
        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("请输入新密码")
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setFixedHeight(25)
        reset_form.addWidget(self.new_password_input, 0, 1)

        reset_form.addWidget(QLabel("确认密码:"), 1, 0)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("请再次输入新密码")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setFixedHeight(25)
        reset_form.addWidget(self.confirm_password_input, 1, 1)

        reset_layout.addLayout(reset_form)
        reset_layout.addStretch(1)

        # 添加页面到堆叠部件
        self.stacked_widget.addWidget(username_widget)
        self.stacked_widget.addWidget(security_widget)
        self.stacked_widget.addWidget(reset_widget)

        # 创建表单框架包裹堆叠部件
        form_frame = QFrame()
        form_frame.setFixedHeight(120)  # 进一步缩小表单区域高度
        form_frame_layout = QVBoxLayout(form_frame)
        form_frame_layout.setContentsMargins(0, 0, 0, 0)
        form_frame_layout.addWidget(self.stacked_widget)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)

        # 返回登录按钮
        back_button = QPushButton("返回登录")
        back_button.setFixedSize(80, 28)  # 缩小按钮尺寸
        back_button.setStyleSheet("""
            background-color: #95a5a6;
            color: white;
            border: none;
            padding: 5px 10px;
            font-weight: bold;
            border-radius: 4px;
            font-size: 13px;
        """)
        back_button.clicked.connect(self._on_back_button_clicked)

        # 下一步按钮
        self.next_button = QPushButton("下一步")
        self.next_button.setFixedSize(80, 28)  # 缩小按钮尺寸
        self.next_button.clicked.connect(self._on_next_button_clicked)

        button_layout.addWidget(back_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.next_button)

        # 将组件添加到主布局
        main_layout.addWidget(title_label)
        main_layout.addWidget(self.step_label)
        main_layout.addWidget(form_frame)
        main_layout.addLayout(button_layout)

    def _on_next_button_clicked(self):
        """下一步按钮点击处理"""
        if self.current_step == 0:
            # 验证用户名
            username = self.username_input.text().strip()

            if not username:
                QMessageBox.warning(self, "验证失败", "请输入用户名")
                return

            # 从数据库获取安全问题
            success, message, question = self.db.get_security_question(username)

            if not success:
                QMessageBox.warning(self, "验证失败", message)
                return

            if not question:
                QMessageBox.warning(self, "验证失败", "该账号未设置安全问题，无法找回密码")
                return

            # 保存验证信息
            self.verified_username = username
            self.security_question = question

            # 显示安全问题
            self.security_question_label.setText(f"安全问题: {self.security_question}")

            # 进入下一步
            self.current_step = 1
            self.step_label.setText("第2步: 验证安全问题")
            self.stacked_widget.setCurrentIndex(1)

        elif self.current_step == 1:
            # 验证安全问题答案
            answer = self.security_answer_input.text().strip()

            if not answer:
                QMessageBox.warning(self, "验证失败", "请输入安全问题答案")
                return

            # 从数据库验证答案
            success, message = self.db.verify_security_answer(self.verified_username, answer)

            if not success:
                QMessageBox.warning(self, "验证失败", message)
                return

            # 进入下一步
            self.current_step = 2
            self.step_label.setText("第3步: 设置新密码")
            self.stacked_widget.setCurrentIndex(2)
            self.next_button.setText("重置密码")

        elif self.current_step == 2:
            # 重置密码
            new_password = self.new_password_input.text().strip()
            confirm_password = self.confirm_password_input.text().strip()

            if not new_password:
                QMessageBox.warning(self, "重置失败", "请输入新密码")
                return

            if new_password != confirm_password:
                QMessageBox.warning(self, "重置失败", "两次输入的密码不一致")
                return

            # 调用数据库重置密码
            success, message = self.db.reset_password(self.verified_username, new_password)

            if success:
                QMessageBox.information(self, "重置成功", "密码已成功重置，请使用新密码登录")
                self.switch_to_login.emit()
            else:
                QMessageBox.warning(self, "重置失败", message)

    def _on_back_button_clicked(self):
        """返回登录按钮点击处理"""
        self.hide()  # 隐藏当前窗口
        self.switch_to_login.emit()  # 发送返回登录信号

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        self.switch_to_login.emit()  # 确保关闭窗口时也会返回登录界面
        event.accept()

    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._on_next_button_clicked()
        else:
            super().keyPressEvent(event)
