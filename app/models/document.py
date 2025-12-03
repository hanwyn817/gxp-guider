from datetime import datetime

# 延迟导入db以避免循环导入
from app import db

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    title = db.Column(db.String(256), unique=True, index=True)
    chinese_title = db.Column(db.String(256))  # 中文标题
    summary = db.Column(db.Text)
    chinese_summary = db.Column(db.Text)  # 中文概述
    cover_url = db.Column(db.String(512))  # 缩略图URL
    publish_date = db.Column(db.Date)  # 出版日期
    source_url = db.Column(db.String(512))  # 原网站链接
    original_file_url = db.Column(db.String(512))  # 原版PDF链接
    translation_file_url = db.Column(db.String(512))  # 中文版PDF链接
    original_preview_url = db.Column(db.String(512))  # 原版PDF预览链接（前10页）
    translation_preview_url = db.Column(db.String(512))  # 中文版PDF预览链接（前10页）
    price = db.Column(db.Integer, default=0)  # 价格(以人民币计价，单位元)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    org = db.relationship('Organization', backref=db.backref('org_documents', lazy='dynamic'))
    category = db.relationship('Category', backref=db.backref('cat_documents', lazy='dynamic'))
    # 下载统计已停用，保留字段可按需移除/迁移
    download_stats = db.relationship('DownloadStat', backref='document', lazy='dynamic')
    
    def __repr__(self):
        return f'<Document {self.chinese_title or self.title}>'
    
    def __str__(self):
        return self.chinese_title or self.title
    
    # --------------
    # 段落/Markdown 助手
    # --------------
    @property
    def summary_paragraphs(self):
        """按空行拆分英文概述为段落数组。"""
        text = (self.summary or '').strip()
        if not text:
            return []
        # 以一个或多个空行分段，去除首尾空白
        import re
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p and p.strip()]
        return parts

    @property
    def chinese_summary_paragraphs(self):
        """按空行拆分中文概述为段落数组。"""
        text = (self.chinese_summary or '').strip()
        if not text:
            return []
        import re
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p and p.strip()]
        return parts

    def set_summary_paragraphs(self, paragraphs):
        """传入段落数组，使用空行拼接为 Markdown 文本。"""
        if not paragraphs:
            self.summary = None
            return
        parts = [str(p).strip() for p in paragraphs if str(p).strip()]
        self.summary = "\n\n".join(parts) if parts else None

    def set_chinese_summary_paragraphs(self, paragraphs):
        """传入段落数组，使用空行拼接为 Markdown 文本（中文）。"""
        if not paragraphs:
            self.chinese_summary = None
            return
        parts = [str(p).strip() for p in paragraphs if str(p).strip()]
        self.chinese_summary = "\n\n".join(parts) if parts else None

    def summary_html(self):
        """将英文概述渲染为安全 HTML（依赖 Markdown + bleach）。"""
        from app.utils.markdown import render_markdown_safe
        return render_markdown_safe(self.summary or "")

    def chinese_summary_html(self):
        """将中文概述渲染为安全 HTML（依赖 Markdown + bleach）。"""
        from app.utils.markdown import render_markdown_safe
        return render_markdown_safe(self.chinese_summary or "")

    def to_json(self):
        return {
            'id': self.id,
            'org_id': self.org_id,
            'category_id': self.category_id,
            'title': self.title,
            'chinese_title': self.chinese_title,
            'summary': self.summary,
            'chinese_summary': self.chinese_summary,
            'cover_url': self.cover_url,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'source_url': self.source_url,
            'original_file_url': self.original_file_url,
            'translation_file_url': self.translation_file_url,
            'price': self.price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# 添加一个简单的修复，为Document模型提供一个默认的AdminView
def get_document_admin_view():
    from flask_admin.contrib.sqla import ModelView
    class DocumentAdminView(ModelView):
        column_list = ("id", "chinese_title", "title", "price", "created_at", "updated_at")
        column_labels = {
            'id': 'ID',
            'chinese_title': '中文标题',
            'title': '英文标题',
            'price': '价格',
            'created_at': '创建时间',
            'updated_at': '更新时间'
        }
    return DocumentAdminView
