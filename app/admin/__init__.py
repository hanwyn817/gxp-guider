from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.filters import BaseSQLAFilter
from flask_admin import AdminIndexView, expose
from flask_admin.menu import MenuLink
from flask_login import current_user
from flask import redirect, url_for, request, render_template, flash, send_file
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.form import FileUploadField
from datetime import datetime
from sqlalchemy import func, and_, or_
import os
import logging
from werkzeug.utils import secure_filename
from ..utils.upload import save_file
from io import BytesIO
from openpyxl import Workbook

def format_datetime(view, context, model, name):
    """格式化时间显示到分钟"""
    dt = getattr(model, name)
    if dt:
        return dt.strftime('%Y-%m-%d %H:%M')
    return ''

class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        # 延迟导入以避免循环导入
        from ..models import User, Document, DownloadStat
        from .. import db
        
        if not current_user.is_authenticated or not current_user.is_admin():
            return redirect(url_for('auth.login', next=request.url))
        
        # 获取统计数据
        user_count = User.query.count()
        document_count = Document.query.count()
        total_downloads = 0
        
        # 获取今日新增数据
        from datetime import datetime, timedelta
        today = datetime.utcnow().date()
        today_users = User.query.filter(db.func.date(User.created_at) == today).count()
        today_documents = Document.query.filter(db.func.date(Document.created_at) == today).count()
        today_downloads = 0
        
        # 最近注册用户
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        # 最近上传文档
        recent_documents = Document.query.order_by(Document.created_at.desc()).limit(5).all()
        
        return self.render('admin/index.html',
                          user_count=user_count,
                          document_count=document_count,
                          total_downloads=total_downloads,
                          today_users=today_users,
                          today_documents=today_documents,
                          recent_users=recent_users,
                          recent_documents=recent_documents,
                          today_downloads=today_downloads)

class MyModelView(ModelView):
    column_formatters = {
        'created_at': format_datetime,
        'updated_at': format_datetime,
        'purchased_at': format_datetime,
        'downloaded_at': format_datetime,
        'paid_at': format_datetime,
    }
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin()
        
    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect(url_for('auth.login', next=request.url))

class UserAdminView(MyModelView):
    column_list = ("id", "username", "email", "role", "created_at")
    column_labels = {
        'id': 'ID',
        'username': '用户名',
        'email': '邮箱',
        'role': '角色',
        'created_at': '创建时间'
    }

    column_searchable_list = ('id', 'username')

class OrganizationAdminView(MyModelView):
    column_list = ("id", "name", "created_at")
    column_labels = {
        'id': 'ID',
        'name': '组织名称',
        'created_at': '创建时间'
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 自定义组织名称的显示方式
        self.column_formatters['name'] = self.organization_name_formatter
    
    def organization_name_formatter(self, view, context, model, name):
        """格式化组织名称，只显示名称本身，不显示 <Organization ...> 格式"""
        return model.name


class CategoryAdminView(MyModelView):
    column_list = ("id", "organization", "name", "parent_id", "created_at")
    column_labels = {
        'id': 'ID',
        'organization': '组织名称',
        'name': '分类名称',
        'parent_id': '父分类ID',
        'created_at': '创建时间'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 自定义关联组织的显示方式
        self.column_formatters['organization'] = self.organization_formatter
        # 使用自定义列表页模板（卡片式分组展示），保留表格模式可切换
        self.list_template = 'admin/categories/list.html'
        # 自定义创建页模板，用于显示“当前组织”提示
        self.create_template = 'admin/categories/create.html'

    def organization_formatter(self, view, context, model, name):
        """格式化关联组织的显示方式"""
        if model.organization:
            return model.organization.name
        return ''

    def create_form(self, obj=None):
        """在创建分类时，根据 URL 参数 org_id 预选组织。"""
        form = super().create_form(obj)
        try:
            # 仅在 GET 渲染时预填，避免覆盖 POST 提交的值
            if request.method == 'GET':
                org_id = request.args.get('org_id', type=int)
                if org_id and hasattr(form, 'organization') and not getattr(form.organization, 'data', None):
                    from ..models import Organization
                    org = self.session.query(Organization).get(org_id)
                    if org:
                        form.organization.data = org
                        if hasattr(form, 'org_id'):
                            try:
                                form.org_id.data = org.id
                            except Exception:
                                pass
        except Exception:
            pass
        return form

    @expose('/')
    def index_view(self):
        """分类列表：默认卡片式按组织分组展示；?mode=table 回退表格模式。"""
        mode = request.args.get('mode') or 'cards'
        if mode == 'table':
            # 使用原生列表视图（含搜索/筛选/分页）
            return super().index_view()

        # 卡片模式：查询组织及其分类，并统计文档数
        from ..models import Organization, Category, Document
        from sqlalchemy import func

        org_id = request.args.get('org_id', type=int)

        org_query = self.session.query(Organization).order_by(Organization.name.asc())
        if org_id:
            org_query = org_query.filter(Organization.id == org_id)
        orgs = org_query.all()

        # 一次性取分类
        categories_by_org = {}
        for org in orgs:
            cats = self.session.query(Category).filter_by(org_id=org.id).order_by(Category.name.asc()).all()
            categories_by_org[org] = cats

        # 统计每个分类下文档数量
        counts = dict(
            self.session.query(Document.category_id, func.count(Document.id))
            .group_by(Document.category_id)
            .all()
        )

        return self.render(
            'admin/categories/list.html',
            categories_by_org=categories_by_org,
            counts=counts,
            orgs=orgs,
            all_orgs=self.session.query(Organization).order_by(Organization.name.asc()).all(),
            current_org_id=org_id,
            mode='cards'
        )

class DocumentAdminView(MyModelView):
    column_list = ("id", "chinese_title", "title", "org", "cat", "updated_at")
    column_labels = {
        'id': 'ID',
        'chinese_title': '中文标题',
        'title': '英文标题',
        'chinese_summary': '中文概述',
        'org': '所属组织',
        'cat': '分类',
        'updated_at': '数据更新时间',
        'publish_date': '出版日期',
        'summary': '概述',
        'cover_url': '封面缩略图链接',
        'source_url': '源链接',
        'original_file_url': '原版文档下载链接',
        'translation_file_url': '中文版文档下载链接',
        'original_preview_url': '原版文档预览（前十页）链接',
        'translation_preview_url': '中文版文档预览（前十页）链接'
    }
    
    form_columns = ('org', 'cat', 'title', 'chinese_title', 'summary', 'chinese_summary', 'cover_url', 
                   'publish_date', 'source_url', 'original_file_url', 'translation_file_url', 'translation_preview_url','original_preview_url')
    
    column_searchable_list = ('title', 'chinese_title')
    column_filters = ('org.name', 'cat.name')
    
    # Use custom form templates for edit and create separately
    edit_template = 'admin/documents/edit.html'
    create_template = 'admin/documents/create.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 自定义关联组织的显示方式
        self.column_formatters['org'] = self.organization_formatter
        # 自定义分类的显示方式
        self.column_formatters['cat'] = self.category_formatter
        # 添加“文件可用性”筛选（任一/仅英文/仅中文/无文件）
        from ..models import Document
        self.column_filters = tuple(self.column_filters) + (
            FileAvailabilityFilter(Document.id, '文件'),
        )

    @expose('/export')
    def export_all(self):
        """导出全部文档为 XLSX（不受筛选影响）。"""
        docs = self.session.query(self.model).all()

        wb = Workbook()
        ws = wb.active
        ws.title = "Documents"

        headers = [
            'ID', '组织', '分类', '英文标题', '中文标题', '概述', '中文概述', '封面链接',
            '出版日期', '源链接', '原版文档链接', '中文版文档链接',
            '原版预览链接', '中文版预览链接', '创建时间', '更新时间'
        ]
        ws.append(headers)

        for doc in docs:
            row = [
                getattr(doc, 'id', ''),
                getattr(getattr(doc, 'org', None), 'name', ''),
                getattr(getattr(doc, 'category', None), 'name', ''),
                getattr(doc, 'title', '') or '',
                getattr(doc, 'chinese_title', '') or '',
                getattr(doc, 'summary', '') or '',
                getattr(doc, 'chinese_summary', '') or '',
                getattr(doc, 'cover_url', '') or '',
                doc.publish_date.strftime('%Y-%m-%d') if getattr(doc, 'publish_date', None) else '',
                getattr(doc, 'source_url', '') or '',
                getattr(doc, 'original_file_url', '') or '',
                getattr(doc, 'translation_file_url', '') or '',
                getattr(doc, 'original_preview_url', '') or '',
                getattr(doc, 'translation_preview_url', '') or '',
                doc.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(doc, 'created_at', None) else '',
                doc.updated_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(doc, 'updated_at', None) else ''
            ]
            ws.append(row)

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name='documents_export.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    def organization_formatter(self, view, context, model, name):
        """格式化关联组织的显示方式"""
        if model.org:
            return model.org.name
        return ''
    
    def category_formatter(self, view, context, model, name):
        """格式化关联分类的显示方式"""
        if model.cat:
            return model.cat.name
        return ''
    
    def on_model_change(self, form, model, is_created):
        """Handle file uploads when saving the model"""
        from ..utils.upload import save_file
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Starting document file upload process in admin panel")
        logger.info(f"Request files: {request.files}")
        logger.info(f"Original file upload in request: {'original_file_upload' in request.files}")
        logger.info(f"Translation file upload in request: {'translation_file_upload' in request.files}")
        
        # Handle original file upload
        if 'original_file_upload' in request.files:
            original_file = request.files['original_file_upload']
            logger.info(f"Original file object: {original_file}")
            logger.info(f"Original file filename: {original_file.filename}")
            
            if original_file and original_file.filename:
                try:
                    organization_name = model.org.name if model.org else "Unknown"
                    logger.info(f"Uploading original file: {original_file.filename} for organization: {organization_name}")
                    
                    # Save file and get both file URL and preview URL
                    file_url, preview_url = save_file(
                        file=original_file,
                        organization_name=organization_name,
                        title=model.title,
                        is_chinese=False
                    )
                    
                    model.original_file_url = file_url
                    model.original_preview_url = preview_url
                    
                    logger.info(f"Original file uploaded successfully. File URL: {file_url}, Preview URL: {preview_url}")
                except Exception as e:
                    error_msg = f"原版文件上传失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    flash(error_msg, "error")
            else:
                logger.info("Original file is empty or has no filename")
        else:
            logger.info("No original file upload in request")
        
        # Handle translation file upload
        if 'translation_file_upload' in request.files:
            translation_file = request.files['translation_file_upload']
            logger.info(f"Translation file object: {translation_file}")
            logger.info(f"Translation file filename: {translation_file.filename}")
            
            if translation_file and translation_file.filename:
                try:
                    organization_name = model.org.name if model.org else "Unknown"
                    logger.info(f"Uploading translation file: {translation_file.filename} for organization: {organization_name}")
                    
                    # Save file and get both file URL and preview URL
                    file_url, preview_url = save_file(
                        file=translation_file,
                        organization_name=organization_name,
                        title=model.title,
                        is_chinese=True
                    )
                    
                    model.translation_file_url = file_url
                    model.translation_preview_url = preview_url
                    
                    logger.info(f"Translation file uploaded successfully. File URL: {file_url}, Preview URL: {preview_url}")
                except Exception as e:
                    error_msg = f"中文版文件上传失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    flash(error_msg, "error")
            else:
                logger.info("Translation file is empty or has no filename")
        else:
            logger.info("No translation file upload in request")
        
        logger.info("Calling super().on_model_change")
        super().on_model_change(form, model, is_created)
        logger.info("Finished on_model_change")

    def _apply_default_filters(self, query):
        """支持通过 q_org / q_cat 查询参数进行默认过滤。"""
        try:
            q_org = (request.args.get('q_org') or '').strip()
            q_cat = (request.args.get('q_cat') or '').strip()
            if q_org:
                from ..models import Organization
                query = query.join(self.model.org).filter(Organization.name == q_org)
            if q_cat:
                from ..models import Category
                # 避免重复 join：仅在尚未 join 时追加。此处简单调用 join(self.model.category)
                query = query.join(self.model.category).filter(Category.name == q_cat)
            return query
        except Exception:
            return query

    def get_query(self):
        query = super().get_query()
        return self._apply_default_filters(query)

    def get_count_query(self):
        query = super().get_count_query()
        return self._apply_default_filters(query)

# 自定义 Admin 过滤器：按文件可用性筛选
class FileAvailabilityFilter(BaseSQLAFilter):
    def __init__(self, column=None, name='文件'):
        # 提供选项下拉
        options = (
            ('any', '任一可下载'),
            ('original', '仅英文'),
            ('translation', '仅中文'),
            ('none', '无文件'),
        )
        super().__init__(column, name, options=options)

    def apply(self, query, value, alias=None):
        # 延迟导入以避免循环依赖
        from ..models import Document
        non_empty_original = and_(
            Document.original_file_url.isnot(None),
            func.length(func.trim(Document.original_file_url)) > 0
        )
        non_empty_translation = and_(
            Document.translation_file_url.isnot(None),
            func.length(func.trim(Document.translation_file_url)) > 0
        )
        empty_original = or_(
            Document.original_file_url.is_(None),
            func.length(func.trim(Document.original_file_url)) == 0
        )
        empty_translation = or_(
            Document.translation_file_url.is_(None),
            func.length(func.trim(Document.translation_file_url)) == 0
        )

        if value == 'original':
            return query.filter(non_empty_original)
        if value == 'translation':
            return query.filter(non_empty_translation)
        if value == 'none':
            return query.filter(and_(empty_original, empty_translation))
        # 默认 any
        return query.filter(or_(non_empty_original, non_empty_translation))

    def operation(self):
        return '筛选'

class DownloadStatAdminView(MyModelView):
    column_list = ("id", "document_id", "user_id", "downloaded_at")
    column_labels = {
        'id': 'ID',
        'document_id': '文档ID',
        'user_id': '用户ID',
        'downloaded_at': '下载时间'
    }

def init_admin(admin, app):
    # Import models and db inside the function to avoid circular imports
    from ..models import User, Organization, Category, Document, DownloadStat
    from .. import db
    
    admin.add_view(UserAdminView(User, db.session, endpoint='admin_users'))
    admin.add_view(OrganizationAdminView(Organization, db.session, endpoint='admin_organizations'))
    admin.add_view(CategoryAdminView(Category, db.session, endpoint='admin_categories'))
    admin.add_view(DocumentAdminView(Document, db.session, endpoint='admin_documents'))
    # 顶部菜单添加导出入口（指向 DocumentAdminView 自带的导出端点）
    admin.add_link(MenuLink(name='导出文档', url='/admin/admin_documents/export'))
    # 下载记录视图已停用


# 导入并导出视图
from . import views
admin = views.admin
