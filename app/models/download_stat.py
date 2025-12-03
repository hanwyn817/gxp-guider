from datetime import datetime

# 延迟导入db以避免循环导入
from app import db

class DownloadStat(db.Model):
    __tablename__ = 'download_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DownloadStat {self.id}>'