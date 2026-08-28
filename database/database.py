#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
import hashlib
import random
import string
import shutil
from pathlib import Path
from datetime import datetime, timedelta


class Database:
    """数据库管理类，负责用户数据的存储与验证"""
    
    def __init__(self, db_path='user_data.db'):
        """初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建用户表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            avatar_path TEXT,
            security_question TEXT,
            security_answer TEXT,
            reset_token TEXT,
            reset_token_expires TIMESTAMP,
            register_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _hash_password(self, password):
        """密码加密处理
        
        Args:
            password: 明文密码
            
        Returns:
            加密后的密码哈希值
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _generate_reset_token(self, length=20):
        """生成密码重置令牌
        
        Args:
            length: 令牌长度
            
        Returns:
            生成的令牌
        """
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def register_user(self, username, password, avatar_path=None, security_question=None, security_answer=None):
        """注册新用户
        
        Args:
            username: 用户名
            password: 密码
            avatar_path: 头像路径
            security_question: 安全问题
            security_answer: 安全问题答案
            
        Returns:
            (bool, str): (是否成功, 消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute("SELECT username FROM users WHERE username=?", (username,))
            if cursor.fetchone():
                return False, "用户名已存在"
            
            # 如果提供了头像，拷贝到用户头像目录
            final_avatar_path = avatar_path
            if avatar_path and os.path.exists(avatar_path):
                # 创建用户头像目录
                os.makedirs('resources/user_avatars', exist_ok=True)
                
                # 拷贝头像文件到用户目录
                file_ext = os.path.splitext(avatar_path)[1]
                avatar_filename = f"{username}{file_ext}"
                final_avatar_path = os.path.join('resources/user_avatars', avatar_filename)
                
                try:
                    shutil.copy2(avatar_path, final_avatar_path)
                except Exception as e:
                    return False, f"头像保存失败: {str(e)}"
            
            # 如果提供了安全问题与答案，则加密答案
            hashed_answer = None
            if security_question and security_answer:
                hashed_answer = self._hash_password(security_answer.lower().strip())
            
            # 加密密码并存储
            hashed_password = self._hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password, avatar_path, security_question, security_answer) VALUES (?, ?, ?, ?, ?)",
                (username, hashed_password, final_avatar_path, security_question, hashed_answer)
            )
            
            conn.commit()
            conn.close()
            return True, "注册成功"
            
        except Exception as e:
            return False, f"注册失败: {str(e)}"
    
    def verify_user(self, username, password):
        """验证用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            (bool, str, str): (是否成功, 消息, 头像路径)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询用户
            cursor.execute(
                "SELECT password, avatar_path FROM users WHERE username=?",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, "用户不存在", None
            
            stored_password, avatar_path = result
            
            # 验证密码
            hashed_password = self._hash_password(password)
            if hashed_password != stored_password:
                return False, "密码错误", None
                
            conn.close()
            return True, "登录成功", avatar_path
            
        except Exception as e:
            return False, f"登录失败: {str(e)}", None
    
    def create_reset_token(self, username):
        """创建密码重置令牌
        
        Args:
            username: 用户名
            
        Returns:
            (bool, str, str): (是否成功, 消息, 令牌)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查用户是否存在
            cursor.execute("SELECT id FROM users WHERE username=?", (username,))
            user = cursor.fetchone()
            
            if not user:
                return False, "用户不存在", None
            
            # 生成令牌
            token = self._generate_reset_token()
            expires = datetime.now() + timedelta(hours=24)  # 24小时有效期
            
            # 更新用户信息
            cursor.execute(
                "UPDATE users SET reset_token=?, reset_token_expires=? WHERE username=?",
                (token, expires, username)
            )
            
            conn.commit()
            conn.close()
            
            return True, "已创建密码重置令牌", token
            
        except Exception as e:
            return False, f"创建重置令牌失败: {str(e)}", None
    
    def verify_security_answer(self, username, answer):
        """验证安全问题答案
        
        Args:
            username: 用户名
            answer: 安全问题答案
            
        Returns:
            (bool, str): (是否成功, 消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询安全问题答案
            cursor.execute(
                "SELECT security_answer FROM users WHERE username=?",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return False, "用户不存在或未设置安全问题"
            
            stored_answer = result[0]
            
            # 验证答案
            hashed_answer = self._hash_password(answer.lower().strip())
            if hashed_answer != stored_answer:
                return False, "安全问题答案错误"
                
            conn.close()
            return True, "安全问题验证成功"
            
        except Exception as e:
            return False, f"验证安全问题失败: {str(e)}"
    
    def get_security_question(self, username):
        """获取用户的安全问题
        
        Args:
            username: 用户名
            
        Returns:
            (bool, str, str): (是否成功, 消息, 安全问题)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询安全问题
            cursor.execute(
                "SELECT security_question FROM users WHERE username=?",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return False, "用户不存在或未设置安全问题", None
            
            security_question = result[0]
            
            conn.close()
            return True, "获取安全问题成功", security_question
            
        except Exception as e:
            return False, f"获取安全问题失败: {str(e)}", None
    
    def reset_password(self, username, new_password):
        """重置用户密码
        
        Args:
            username: 用户名
            new_password: 新密码
            
        Returns:
            (bool, str): (是否成功, 消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 加密新密码
            hashed_password = self._hash_password(new_password)
            
            # 更新密码并清除重置令牌
            cursor.execute(
                "UPDATE users SET password=?, reset_token=NULL, reset_token_expires=NULL WHERE username=?",
                (hashed_password, username)
            )
            
            if cursor.rowcount == 0:
                return False, "用户不存在"
            
            conn.commit()
            conn.close()
            
            return True, "密码重置成功"
            
        except Exception as e:
            return False, f"密码重置失败: {str(e)}"
    
    def get_user_avatar(self, username):
        """获取用户头像路径
        
        Args:
            username: 用户名
            
        Returns:
            头像路径或None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询头像路径
            cursor.execute(
                "SELECT avatar_path FROM users WHERE username=?",
                (username,)
            )
            result = cursor.fetchone()
            
            conn.close()
            
            if result and result[0]:
                return result[0]
            return None
            
        except Exception:
            return None 