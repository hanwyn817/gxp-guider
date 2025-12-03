#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GMP药指汇日志配置
用于配置应用的日志记录
"""

import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """设置应用日志"""
    # 确保日志目录存在
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # 配置文件处理器
    file_handler = RotatingFileHandler(
        'logs/gmp_seeker.log', 
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)
    
    # 设置日志级别
    file_handler.setLevel(logging.INFO)
    
    # 添加处理器到应用
    app.logger.addHandler(file_handler)
    
    # 设置应用日志级别
    app.logger.setLevel(logging.INFO)
    
    # 记录应用启动日志
    app.logger.info('GMP药指汇启动')

def setup_crawler_logging():
    """设置爬虫日志"""
    # 确保日志目录存在
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # 配置文件处理器
    file_handler = RotatingFileHandler(
        'logs/crawler.log', 
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # 设置日志级别
    file_handler.setLevel(logging.INFO)
    
    # 创建爬虫日志记录器
    crawler_logger = logging.getLogger('crawler')
    crawler_logger.setLevel(logging.INFO)
    crawler_logger.addHandler(file_handler)
    
    return crawler_logger
