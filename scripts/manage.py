#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GxP Guider管理脚本
用于管理用户、文档等
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 添加项目路径到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Document, Organization, Category

def create_user(username, email, password, is_admin=False):
    """创建用户"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        # 检查用户是否已存在
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"错误: 邮箱 {email} 已存在")
            return
        
        # 创建新用户
        user = User(username=username, email=email, role='admin' if is_admin else 'user')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"用户 {username} 创建成功")

def delete_user(email):
    """删除用户"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"错误: 未找到邮箱为 {email} 的用户")
            return
        
        db.session.delete(user)
        db.session.commit()
        print(f"用户 {user.username} 删除成功")

def list_users():
    """列出所有用户"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        users = User.query.all()
        if not users:
            print("没有用户")
            return
        
        print("用户列表:")
        print("ID\t用户名\t\t邮箱\t\t\t角色\t\t注册时间")
        print("-" * 80)
        for user in users:
            print(f"{user.id}\t{user.username}\t\t{user.email}\t\t{user.role}\t\t{user.created_at.strftime('%Y-%m-%d') if user.created_at else ''}")

def set_admin(email):
    """设置用户为管理员"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"错误: 未找到邮箱为 {email} 的用户")
            return
        
        user.role = 'admin'
        db.session.commit()
        print(f"用户 {user.username} 已设置为管理员")

def remove_admin(email):
    """取消用户管理员权限"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"错误: 未找到邮箱为 {email} 的用户")
            return
        
        user.role = 'user'
        db.session.commit()
        print(f"用户 {user.username} 的管理员权限已取消")

def list_documents():
    """列出所有文档"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        documents = Document.query.all()
        if not documents:
            print("没有文档")
            return
        
        print("文档列表:")
        print("ID\t标题\t\t\t\t组织\t\t分类\t\t发布日期")
        print("-" * 100)
        for doc in documents:
            org_name = doc.organization.name if doc.organization else '未知'
            cat_name = doc.category.name if doc.category else '未分类'
            publish_date = doc.publish_date.strftime('%Y-%m-%d') if doc.publish_date else '未知'
            print(f"{doc.id}\t{doc.title[:20]}\t\t{org_name}\t\t{cat_name}\t\t{publish_date}")

def delete_document(doc_id):
    """删除文档"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        doc = Document.query.get(doc_id)
        if not doc:
            print(f"错误: 未找到ID为 {doc_id} 的文档")
            return
        
        db.session.delete(doc)
        db.session.commit()
        print(f"文档 '{doc.title}' 删除成功")

def set_document_status(doc_id, status):
    """设置文档状态"""
    app = create_app(os.getenv('FLASK_ENV') or 'default')
    with app.app_context():
        doc = Document.query.get(doc_id)
        if not doc:
            print(f"错误: 未找到ID为 {doc_id} 的文档")
            return
        
        doc.status = status
        db.session.commit()
        print(f"文档 '{doc.title}' 状态已设置为 {status}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法:")
        print("  python manage.py create-user <username> <email> <password> [--admin]  # 创建用户")
        print("  python manage.py delete-user <email>  # 删除用户")
        print("  python manage.py list-users  # 列出所有用户")
        print("  python manage.py set-admin <email>  # 设置用户为管理员")
        print("  python manage.py remove-admin <email>  # 取消用户管理员权限")
        print("  python manage.py list-documents  # 列出所有文档")
        print("  python manage.py delete-document <doc_id>  # 删除文档")
        print("  python manage.py set-document-status <doc_id> <status>  # 设置文档状态")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'create-user':
        if len(sys.argv) < 5:
            print("请提供用户名、邮箱和密码")
            sys.exit(1)
        username = sys.argv[2]
        email = sys.argv[3]
        password = sys.argv[4]
        is_admin = '--admin' in sys.argv
        create_user(username, email, password, is_admin)
    
    elif command == 'delete-user':
        if len(sys.argv) < 3:
            print("请提供邮箱")
            sys.exit(1)
        email = sys.argv[2]
        delete_user(email)
    
    elif command == 'list-users':
        list_users()
    
    elif command == 'set-admin':
        if len(sys.argv) < 3:
            print("请提供邮箱")
            sys.exit(1)
        email = sys.argv[2]
        set_admin(email)
    
    elif command == 'remove-admin':
        if len(sys.argv) < 3:
            print("请提供邮箱")
            sys.exit(1)
        email = sys.argv[2]
        remove_admin(email)
    
    elif command == 'list-documents':
        list_documents()
    
    elif command == 'delete-document':
        if len(sys.argv) < 3:
            print("请提供文档ID")
            sys.exit(1)
        doc_id = int(sys.argv[2])
        delete_document(doc_id)
    
    elif command == 'set-document-status':
        if len(sys.argv) < 4:
            print("请提供文档ID和状态")
            sys.exit(1)
        doc_id = int(sys.argv[2])
        status = sys.argv[3]
        set_document_status(doc_id, status)
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)
