from datetime import datetime

# 延迟导入db以避免循环导入
from app import db

class Organization(db.Model):
    __tablename__ = 'organizations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    categories = db.relationship('Category', backref='organization', lazy='dynamic')
    documents = db.relationship('Document', backref='organization', lazy='dynamic')
    
    def __repr__(self):
        return f'<Organization {self.name}>'