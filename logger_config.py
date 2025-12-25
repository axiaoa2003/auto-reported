#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康打卡助手 - 简化版日志配置模块
提供基本的日志配置功能，使用Python标准库logging
"""

import logging
import os
from pathlib import Path

# 定义日志级别常量，保持与原系统兼容
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

class VirtualHandler:
    """简化的处理器类，保持与原virtual_logger接口兼容"""
    def __init__(self, filename, encoding=None):
        self.baseFilename = filename
        self.encoding = encoding

class FileHandler(VirtualHandler):
    """文件处理器，保持接口兼容"""
    pass

class StreamHandler:
    """流处理器，保持接口兼容"""
    pass

class GUILogHandler(logging.Handler):
    """自定义GUI日志处理器，将日志消息发送到GUI界面"""
    def __init__(self, gui_callback=None):
        super().__init__()
        self.gui_callback = gui_callback
    
    def set_gui_callback(self, callback):
        """设置GUI回调函数"""
        self.gui_callback = callback
    
    def emit(self, record):
        """处理日志记录，发送到GUI"""
        try:
            # 格式化日志记录
            msg = self.format(record)
            if self.gui_callback:
                # 调用GUI回调函数显示日志
                self.gui_callback(msg)
        except Exception:
            self.handleError(record)

# 创建全局GUI日志处理器实例
gui_log_handler = GUILogHandler()

def setup_logger(name=__name__, level=logging.INFO, log_file=None):
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                     datefmt='%Y-%m-%d %H:%M:%S')
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 添加GUI日志处理器
        gui_log_handler.setFormatter(formatter)
        logger.addHandler(gui_log_handler)
        
        # 添加文件处理器（如果指定了日志文件）
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                Path(log_dir).mkdir(exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    return logger

def getLogger(name=None):
    """
    获取或创建日志记录器
    模拟logging.getLogger接口
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器
    """
    return logging.getLogger(name)

def basicConfig(**kwargs):
    """
    基础日志配置
    模拟logging.basicConfig接口，保持兼容性
    
    Args:
        **kwargs: 配置参数
        
    Returns:
        logging.Logger: 根日志记录器
    """
    # 提取配置参数
    level = kwargs.get('level', logging.INFO)
    format_str = kwargs.get('format', '%(asctime)s - %(levelname)s - %(message)s')
    datefmt = kwargs.get('datefmt', '%Y-%m-%d %H:%M:%S')
    filename = kwargs.get('filename')
    handlers = kwargs.get('handlers', [])
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除已有的处理器
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # 创建格式化器
    formatter = logging.Formatter(format_str, datefmt=datefmt)
    
    # 如果指定了文件名，添加文件处理器
    if filename:
        log_dir = os.path.dirname(filename)
        if log_dir:
            Path(log_dir).mkdir(exist_ok=True)
        file_handler = logging.FileHandler(filename, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # 添加额外的处理器
    for handler in handlers:
        # 处理兼容的处理器对象
        if hasattr(handler, 'baseFilename'):
            # 这是我们的虚拟FileHandler
            real_handler = logging.FileHandler(handler.baseFilename, 
                                             encoding=getattr(handler, 'encoding', 'utf-8'))
            real_handler.setFormatter(formatter)
            root_logger.addHandler(real_handler)
        elif isinstance(handler, StreamHandler):
            # 这是我们的虚拟StreamHandler
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加GUI日志处理器
    gui_log_handler.setFormatter(formatter)
    root_logger.addHandler(gui_log_handler)
    
    return root_logger

# 为了保持完全兼容性，添加直接的全局函数
def debug(msg, *args, **kwargs):
    """记录DEBUG级别的全局日志"""
    _root_logger = logging.getLogger()
    _root_logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """记录INFO级别的全局日志"""
    _root_logger = logging.getLogger()
    _root_logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """记录WARNING级别的全局日志"""
    _root_logger = logging.getLogger()
    _root_logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """记录ERROR级别的全局日志"""
    _root_logger = logging.getLogger()
    _root_logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """记录CRITICAL级别的全局日志"""
    _root_logger = logging.getLogger()
    _root_logger.critical(msg, *args, **kwargs)