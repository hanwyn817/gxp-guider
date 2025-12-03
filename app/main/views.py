from flask import render_template, request, jsonify, current_app
from . import main
from .. import db
from ..models import Document, Organization, Category
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import joinedload
from datetime import datetime
import os

try:
    from markdown import Markdown
except Exception:
    Markdown = None

@main.route('/')
def index():
    # 定义文件可用性条件（非空且非空白）
    non_empty_original = and_(
        Document.original_file_url.isnot(None),
        func.length(func.trim(Document.original_file_url)) > 0
    )
    non_empty_translation = and_(
        Document.translation_file_url.isnot(None),
        func.length(func.trim(Document.translation_file_url)) > 0
    )
    has_any_file = or_(non_empty_original, non_empty_translation)

    # 最近更新Top 4 (按出版日期排序) 不强制有文件
    recent_updated = Document.query.options(joinedload(Document.organization)).order_by(desc(Document.publish_date)).limit(4).all()
    total_docs_count = db.session.query(func.count(Document.id)).scalar()

    # 最新中文 Top 4（translation 有文件）
    latest_cn = Document.query.options(joinedload(Document.organization)).filter(non_empty_translation).order_by(desc(Document.publish_date)).limit(4).all()

    # 已移除首页“免费精选”模块，无需查询
    
    # 按组织分组，各组织最近更新Top 4
    org_docs = {}
    org_counts = {}
    organizations = Organization.query.all()
    for org in organizations:
        # 主页组织模块不过滤“有文件”，展示该组织最近更新Top 4
        docs = Document.query.options(joinedload(Document.organization)).filter_by(org_id=org.id).order_by(desc(Document.publish_date)).limit(4).all()
        if docs:
            org_docs[org.name] = docs
            # 统计该组织的文档总数（不过滤文件）
            count = db.session.query(func.count(Document.id)).filter_by(org_id=org.id).scalar()
            org_counts[org.name] = count
    
    return render_template('index.html', 
                          recent_updated=recent_updated,
                          latest_cn=latest_cn,
                          org_docs=org_docs,
                          org_counts=org_counts,
                          total_docs_count=total_docs_count)

@main.route('/about/organizations')
def organizations_intro():
    lang = request.args.get('lang', 'zh').lower()
    # 定位 Markdown 文件
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    md_filename = 'organizations_en.md' if lang == 'en' else 'organizations.md'
    md_path = os.path.join(base_dir, 'content', md_filename)

    # 读取内容
    if not os.path.exists(md_path):
        content_html = '<p>内容文件缺失：app/content/organizations.md</p>'
        toc_html = ''
        updated_at = None
    else:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_text = f.read()
        updated_at = datetime.fromtimestamp(os.path.getmtime(md_path))

        if Markdown is None:
            # 未安装 Markdown 依赖时的降级渲染
            content_html = '<pre style="white-space: pre-wrap;">' + (
                md_text.replace('<', '&lt;').replace('>', '&gt;')
            ) + '</pre>'
            toc_html = ''
        else:
            md = Markdown(extensions=['toc', 'fenced_code', 'tables'])
            content_html = md.convert(md_text)
            toc_html = getattr(md, 'toc', '')

    return render_template(
        'organizations_intro.html',
        title='组织介绍',
        content_html=content_html,
        toc_html=toc_html,
        updated_at=updated_at,
        current_lang=lang
    )

@main.route('/documents')
def documents():
    # 获取筛选参数
    org_id = request.args.get('org_id', type=int)
    # 支持通过组织名称筛选，例如 ?org=ISPE
    org_name = request.args.get('org', type=str)
    category_id = request.args.get('category_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    page = request.args.get('page', 1, type=int)
    file_filter = request.args.get('file', '').strip()  # '', 'any', 'original', 'translation'
    # 构建查询
    query = Document.query
    
    # 若传入组织名称且未指定org_id，则通过名称解析为org_id
    if org_name and not org_id:
        org_obj = Organization.query.filter(func.lower(Organization.name) == org_name.lower()).first()
        if org_obj:
            org_id = org_obj.id

    if org_id:
        query = query.filter_by(org_id=org_id)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if start_date:
        query = query.filter(Document.publish_date >= start_date)
    
    if end_date:
        query = query.filter(Document.publish_date <= end_date)
    
    if keyword:
        # 同时支持中文/英文标题与中文摘要搜索
        query = query.filter(
            db.or_(
                Document.title.contains(keyword),
                Document.chinese_title.contains(keyword),
                Document.chinese_summary.contains(keyword)
            )
        )

    # 文件可用性筛选
    if file_filter:
        non_empty_original = and_(
            Document.original_file_url.isnot(None),
            func.length(func.trim(Document.original_file_url)) > 0
        )
        non_empty_translation = and_(
            Document.translation_file_url.isnot(None),
            func.length(func.trim(Document.translation_file_url)) > 0
        )
        if file_filter == 'original':
            query = query.filter(non_empty_original)
        elif file_filter == 'translation':
            query = query.filter(non_empty_translation)
        elif file_filter == 'any':
            query = query.filter(or_(non_empty_original, non_empty_translation))
    
    # 价格筛选已移除（平台全部开放），但保留解析以兼容旧链接
    
    # 分页
    query = query.options(joinedload(Document.organization))
    pagination = query.order_by(desc(Document.publish_date)).paginate(
        page=page, per_page=20, error_out=False)
    docs = pagination.items
    
    # 获取组织和分类用于筛选
    organizations = Organization.query.all()
    categories = Category.query.all()
    categories_data = [
        {'id': cat.id, 'name': cat.name, 'org_id': cat.org_id}
        for cat in categories
    ]
    categories_for_filter = categories
    if org_id:
        categories_for_filter = [cat for cat in categories if cat.org_id == org_id]
    
    return render_template('documents.html', 
                          docs=docs,
                          pagination=pagination,
                          organizations=organizations,
                          categories=categories_for_filter,
                          categories_data=categories_data,
                          org_id=org_id,
                          category_id=category_id,
                          start_date=start_date,
                          end_date=end_date,
                          keyword=keyword,
                          file=file_filter)

@main.route('/documents/<int:id>')
def document_detail(id):
    doc = Document.query.options(joinedload(Document.organization), joinedload(Document.category)).get_or_404(id)
    return render_template('document_detail.html', doc=doc)

@main.route('/download-history')
def download_history():
    # This route would need to be implemented based on how download history is tracked in the application
    # For now, we'll return a simple placeholder
    return render_template('download_history.html')
