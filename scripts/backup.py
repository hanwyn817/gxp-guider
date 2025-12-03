#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GMP药指汇数据库备份脚本
用于备份SQLite数据库
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def backup_database(db_path, backup_dir):
    """备份数据库"""
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 {db_path} 不存在")
        return False
    
    # 创建备份目录
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"创建备份目录: {backup_dir}")
    
    # 生成备份文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"gmp_seeker_backup_{timestamp}.sqlite"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # 执行备份
    try:
        shutil.copy2(db_path, backup_path)
        print(f"数据库备份成功: {backup_path}")
        return True
    except Exception as e:
        print(f"备份失败: {str(e)}")
        return False

def list_backups(backup_dir):
    """列出备份文件"""
    if not os.path.exists(backup_dir):
        print(f"备份目录 {backup_dir} 不存在")
        return
    
    backups = [f for f in os.listdir(backup_dir) if f.startswith('gmp_seeker_backup_') and f.endswith('.sqlite')]
    if not backups:
        print("没有找到备份文件")
        return
    
    print("备份文件列表:")
    for backup in sorted(backups, reverse=True):
        backup_path = os.path.join(backup_dir, backup)
        size = os.path.getsize(backup_path)
        mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
        print(f"  {backup}  (大小: {size} 字节, 修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')})")

def restore_database(db_path, backup_path):
    """从备份恢复数据库"""
    # 检查备份文件是否存在
    if not os.path.exists(backup_path):
        print(f"错误: 备份文件 {backup_path} 不存在")
        return False
    
    # 检查数据库文件是否存在
    db_exists = os.path.exists(db_path)
    
    # 如果数据库文件存在，先备份当前数据库
    if db_exists:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        current_backup = f"{db_path}.backup_{timestamp}"
        shutil.copy2(db_path, current_backup)
        print(f"当前数据库已备份为: {current_backup}")
    
    # 执行恢复
    try:
        shutil.copy2(backup_path, db_path)
        print(f"数据库恢复成功: {db_path}")
        return True
    except Exception as e:
        print(f"恢复失败: {str(e)}")
        return False

if __name__ == '__main__':
    # 默认数据库路径和备份目录
    default_db_path = 'data.sqlite'
    default_backup_dir = 'backups'
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python backup.py backup  # 备份数据库")
        print("  python backup.py list  # 列出备份文件")
        print("  python backup.py restore <backup_file>  # 从备份恢复数据库")
        print(f"默认数据库路径: {default_db_path}")
        print(f"默认备份目录: {default_backup_dir}")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        db_path = sys.argv[2] if len(sys.argv) > 2 else default_db_path
        backup_dir = sys.argv[3] if len(sys.argv) > 3 else default_backup_dir
        backup_database(db_path, backup_dir)
    
    elif command == 'list':
        backup_dir = sys.argv[2] if len(sys.argv) > 2 else default_backup_dir
        list_backups(backup_dir)
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("请提供备份文件路径")
            sys.exit(1)
        
        backup_path = sys.argv[2]
        db_path = sys.argv[3] if len(sys.argv) > 3 else default_db_path
        restore_database(db_path, backup_path)
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)
