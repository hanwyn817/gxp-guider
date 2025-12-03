from flask import Blueprint, request, render_template, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from ..models.document import Document
from ..models.organization import Organization
from ..models.category import Category
from .. import db, csrf
import os
import logging
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from ..utils.r2 import _get_config, _s3_client, build_public_url, download_to_temp, upload_file
from ..utils.upload import generate_filename
from werkzeug.utils import secure_filename
from flask import current_app

# Set up logging
logger = logging.getLogger(__name__)

admin = Blueprint('admin_panel', __name__)

@admin.before_request
@login_required
def check_admin():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))

@admin.route('/upload', methods=['GET', 'POST'])
def upload_document():
    # 获取所有组织和分类（延迟导入避免循环依赖）
    from ..models.organization import Organization
    from ..models.category import Category
    from ..utils.upload import save_file

    # 获取所有组织和分类
    organizations = Organization.query.all()
    categories = Category.query.all()
    
    if request.method == 'GET':
        return render_template('admin/upload_document.html', 
                             organizations=organizations, 
                             categories=categories)
    
    # 处理POST请求
    try:
        logger.info("Starting document upload process")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Request form data: {request.form}")
        logger.info(f"Request files: {request.files}")
        
        # 获取表单数据
        organization_id = request.form.get('organization')
        category_id = request.form.get('category')
        document_type = request.form.get('document_type')
        title = request.form.get('title')
        
        logger.info(f"Form data - organization_id: {organization_id}, category_id: {category_id}, document_type: {document_type}, title: {title}")
        
        # 获取上传的文件
        document_file = request.files.get('document_file')
        
        logger.info(f"Document file: {document_file}")
        logger.info(f"Document filename: {document_file.filename if document_file else 'None'}")
        logger.info(f"Document content type: {document_file.content_type if document_file else 'None'}")
        
        # 验证必填字段
        if not organization_id or not category_id or not document_type or not document_file:
            missing_fields = []
            if not organization_id:
                missing_fields.append('organization')
            if not category_id:
                missing_fields.append('category')
            if not document_type:
                missing_fields.append('document_type')
            if not document_file:
                missing_fields.append('document_file')
            
            error_msg = f'请填写所有必填字段。缺少字段: {", ".join(missing_fields)}'
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg})
        
        # 验证文件
        if document_file.filename == '':
            error_msg = '请选择要上传的文件'
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg})
        
        # 验证文件类型
        allowed_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.7z'}
        file_extension = os.path.splitext(document_file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            error_msg = f'不支持的文件类型: {file_extension}。支持的文件类型: {", ".join(allowed_extensions)}'
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg})
        
        # 获取组织信息
        organization = Organization.query.get(organization_id)
        if not organization:
            error_msg = '选择的组织不存在'
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg})
        
        logger.info(f"Organization: {organization.name}")
        
        # 获取分类信息
        category = Category.query.get(category_id)
        if not category:
            error_msg = '选择的分类不存在'
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg})
        
        logger.info(f"Category: {category.name}")
        
        # 确定是否为中文文档
        is_chinese = document_type == 'translation'
        
        logger.info(f"Is Chinese document: {is_chinese}")
        
        try:
            # 保存文件
            file_url, preview_url = save_file(
                file=document_file,
                organization_name=organization.name,
                title=title,
                is_chinese=is_chinese
            )
            
            logger.info(f"File saved successfully. File URL: {file_url}, Preview URL: {preview_url}")
            
            # 确定字段名
            file_url_field = 'translation_file_url' if is_chinese else 'original_file_url'
            preview_url_field = 'translation_preview_url' if is_chinese else 'original_preview_url'
            
            # 检查是否已存在相同标题的文档
            existing_document = Document.query.filter_by(title=title).first()
            
            if existing_document:
                # 更新现有文档
                setattr(existing_document, file_url_field, file_url)
                setattr(existing_document, preview_url_field, preview_url)
                # 不要在上传中文文件时覆盖已有的中文标题
                existing_document.updated_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Document updated successfully. ID: {existing_document.id}")
            else:
                # 创建新文档记录（不自动同步中文标题）
                new_document = Document(
                    title=title if title else os.path.splitext(document_file.filename)[0],
                    org_id=organization.id,
                    category_id=category.id
                )
                # 设置文件URL字段
                setattr(new_document, file_url_field, file_url)
                setattr(new_document, preview_url_field, preview_url)
                
                db.session.add(new_document)
                db.session.commit()
                logger.info(f"Document record created successfully. ID: {new_document.id}")
            
            # 返回成功响应
            return jsonify({
                'success': True,
                'file_url': file_url,
                'preview_url': preview_url,
                'message': '文档上传成功'
            })
        except Exception as e:
            db.session.rollback()
            error_msg = f'保存文件时出错: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return jsonify({'success': False, 'error': error_msg})
            
    except Exception as e:
        logger.error(f"Error during document upload: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@admin.route('/presign-upload', methods=['POST'])
@csrf.exempt
def presign_upload():
    try:
        data = request.get_json() or {}
        org_id = data.get('organization_id')
        document_type = data.get('document_type')  # 'original' | 'translation'
        title = data.get('title')
        original_filename = data.get('filename')
        content_type = data.get('content_type') or 'application/octet-stream'

        if not org_id or not original_filename or not document_type:
            return jsonify({'error': '缺少必要参数'}), 400

        organization = Organization.query.get(org_id)
        if not organization:
            return jsonify({'error': '组织不存在'}), 400

        is_chinese = (document_type == 'translation')
        filename = generate_filename(title, original_filename, is_chinese)
        key = f"documents/{organization.name.lower()}/{filename}"

        # Presign
        bucket, access_key, secret_key, endpoint, _ = _get_config()
        client = _s3_client()
        params = {
            'Bucket': bucket,
            'Key': key,
            'ContentType': content_type,
        }
        url = client.generate_presigned_url(
            'put_object', Params=params, ExpiresIn=600
        )
        return jsonify({
            'url': url,
            'key': key,
            'public_url': build_public_url(key),
            'content_type': content_type,
            'expires_in': 600
        })
    except Exception as e:
        logger.exception('presign failed')
        return jsonify({'error': str(e)}), 500


@admin.route('/presign-cover', methods=['POST'])
@csrf.exempt
def presign_cover():
    """为封面缩略图生成直传 R2 的预签名 URL。"""
    try:
        data = request.get_json() or {}
        org_id = data.get('organization_id')
        filename = data.get('filename')
        content_type = data.get('content_type') or 'image/png'

        if not org_id or not filename:
            return jsonify({'error': '缺少必要参数'}), 400
        organization = Organization.query.get(org_id)
        if not organization:
            return jsonify({'error': '组织不存在'}), 400

        safe_name = _secure_timestamp_name(filename)
        # 统一缩略图路径到 thumbnails/{org}/
        key = f"thumbnails/{organization.name.lower()}/{safe_name}"

        bucket, access_key, secret_key, endpoint, _ = _get_config()
        client = _s3_client()
        params = {
            'Bucket': bucket,
            'Key': key,
            'ContentType': content_type,
        }
        url = client.generate_presigned_url('put_object', Params=params, ExpiresIn=600)
        return jsonify({
            'url': url,
            'key': key,
            'public_url': build_public_url(key),
            'content_type': content_type,
            'expires_in': 600
        })
    except Exception as e:
        logger.exception('presign cover failed')
        return jsonify({'error': str(e)}), 500


@admin.route('/finalize-cover', methods=['POST'])
@csrf.exempt
def finalize_cover():
    """封面上传完成后回填 Document.cover_url，失败时自动清理 R2 对象。"""
    try:
        data = request.get_json() or {}
        org_id = data.get('organization_id')
        document_id = data.get('document_id')  # 可选：创建页可能没有文档ID
        key = data.get('key')
        if not all([org_id, key]):
            _delete_r2_object_safely(key)
            return jsonify({'error': '缺少必要参数（organization_id 或 key）'}), 400

        organization = Organization.query.get(org_id)
        if not organization:
            _delete_r2_object_safely(key)
            return jsonify({'error': '组织不存在'}), 400

        # HEAD 校验图片类型与体积
        bucket, *_ = _get_config()
        client = _s3_client()
        try:
            head = client.head_object(Bucket=bucket, Key=key)
            size = int(head.get('ContentLength', 0))
            ctype = (head.get('ContentType') or '').lower()
            allowed = {'image/png','image/jpeg','image/jpg','image/webp','image/gif','image/svg+xml'}
            max_size = 20 * 1024 * 1024  # 20MB
            if size <= 0 or size > max_size:
                _delete_r2_object_safely(key)
                return jsonify({'error': f'封面大小不符合要求（最大 {max_size//1024//1024}MB）'}), 400
            if ctype and ctype not in allowed:
                _delete_r2_object_safely(key)
                return jsonify({'error': f'不支持的图片类型: {ctype}'}), 400
        except Exception:
            logger.exception('head_object failed for cover key %s', key)
            _delete_r2_object_safely(key)
            return jsonify({'error': '对象元数据校验失败，请稍后重试'}), 500

        # 更新文档封面，删除旧对象
        public_url = build_public_url(key)
        if document_id:
            doc = Document.query.get(document_id)
            if not doc:
                # 若提供了 document_id 但不存在，清理对象并提示
                _delete_r2_object_safely(key)
                return jsonify({'error': '文档不存在'}), 404
            # 删除旧封面（仅当旧封面在 R2 且 key 不同）
            try:
                old_cover_key = _extract_r2_key_from_url(getattr(doc, 'cover_url', None))
                if old_cover_key and old_cover_key != key:
                    _delete_r2_object_safely(old_cover_key)
            except Exception:
                logger.exception('failed to cleanup old cover for doc %s', document_id)
            doc.cover_url = public_url
            doc.updated_at = datetime.utcnow()
            db.session.commit()
        # 若未提供 document_id，为创建页：仅返回 URL 由前端回填到表单
        return jsonify({'success': True, 'url': public_url})
    except Exception as e:
        db.session.rollback()
        logger.exception('finalize cover failed')
        try:
            key = (locals().get('key') or '').lstrip('/')
            if key:
                _delete_r2_object_safely(key)
        except Exception:
            pass
        return jsonify({'error': str(e)}), 500


@admin.route('/finalize-upload', methods=['POST'])
@csrf.exempt
def finalize_upload():
    try:
        data = request.get_json() or {}
        org_id = data.get('organization_id')
        category_id = data.get('category_id')
        document_type = data.get('document_type')
        title = data.get('title')
        key = data.get('key')
        document_id = data.get('document_id')

        if not all([org_id, category_id, document_type, title, key]):
            return jsonify({'error': '缺少必要参数'}), 400

        organization = Organization.query.get(org_id)
        category = Category.query.get(category_id)
        if not organization or not category:
            _delete_r2_object_safely(key)
            return jsonify({'error': '组织或分类不存在'}), 400

        is_chinese = (document_type == 'translation')

        # HEAD 校验上传对象（大小/类型）
        try:
            bucket, *_ = _get_config()
            client = _s3_client()
            head = client.head_object(Bucket=bucket, Key=key)
            size = int(head.get('ContentLength', 0))
            ctype = head.get('ContentType') or ''
            # 允许类型（可根据需要扩展）
            allowed_types = {
                'application/pdf',
                'application/zip', 'application/x-zip-compressed',
                'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            }
            max_size = 200 * 1024 * 1024  # 200MB 上限
            if size <= 0 or size > max_size:
                _delete_r2_object_safely(key)
                return jsonify({'error': f'文件大小不符合要求（最大 {max_size//1024//1024}MB）'}), 400
            if ctype and ctype not in allowed_types:
                _delete_r2_object_safely(key)
                return jsonify({'error': f'不支持的文件类型: {ctype}'}), 400
        except Exception:
            logger.exception('head_object failed for key %s', key)
            _delete_r2_object_safely(key)
            return jsonify({'error': '对象元数据校验失败，请稍后重试'}), 500

        # Download uploaded object to temp for preview generation (if PDF)
        preview_url = None
        public_url = build_public_url(key)
        if key.lower().endswith('.pdf'):
            try:
                local_path = download_to_temp(key)
                preview_url = None
                from ..utils.pdf_preview import generate_document_preview
                preview_url = generate_document_preview(
                    organization.name.lower(),
                    os.path.basename(key),
                    local_path,
                    is_chinese=is_chinese,
                    use_r2=True
                )
                try:
                    os.remove(local_path)
                except Exception:
                    pass
            except Exception:
                logger.exception('preview generation failed for key %s', key)

        # Update or create document record
        file_url_field = 'translation_file_url' if is_chinese else 'original_file_url'
        preview_url_field = 'translation_preview_url' if is_chinese else 'original_preview_url'

        # 优先按 document_id 更新，回退按 title
        existing_document = None
        if document_id:
            try:
                existing_document = Document.query.get(int(document_id))
            except Exception:
                existing_document = None
        if not existing_document:
            existing_document = Document.query.filter_by(title=title).first()

        if existing_document:
            # 记录旧对象 key，用于清理
            try:
                old_file_key = _extract_r2_key_from_url(getattr(existing_document, file_url_field, None))
                old_preview_key = _extract_r2_key_from_url(getattr(existing_document, preview_url_field, None))
            except Exception:
                old_file_key = None
                old_preview_key = None

            setattr(existing_document, file_url_field, public_url)
            if preview_url:
                setattr(existing_document, preview_url_field, preview_url)
            # 不要在上传中文文件时覆盖已有的中文标题
            existing_document.org_id = organization.id
            existing_document.category_id = category.id
            existing_document.updated_at = datetime.utcnow()
            db.session.commit()
            # 清理旧对象（若存在且与新 key 不同）
            try:
                if old_file_key and old_file_key != key:
                    _delete_r2_object_safely(old_file_key)
                if preview_url and old_preview_key:
                    # 只有在本次生成了新预览时才清理旧预览
                    new_preview_key = _extract_r2_key_from_url(preview_url)
                    if old_preview_key != new_preview_key:
                        _delete_r2_object_safely(old_preview_key)
            except Exception:
                logger.exception('failed to cleanup old objects for doc %s', existing_document.id)
            doc_id = existing_document.id
        else:
            new_document = Document(
                title=title,
                org_id=organization.id,
                category_id=category.id
            )
            setattr(new_document, file_url_field, public_url)
            if preview_url:
                setattr(new_document, preview_url_field, preview_url)
            # 新建时也不自动设置中文标题，避免误覆盖
            db.session.add(new_document)
            db.session.commit()
            doc_id = new_document.id

        return jsonify({'success': True, 'file_url': public_url, 'preview_url': preview_url, 'document_id': doc_id})
    except Exception as e:
        db.session.rollback()
        logger.exception('finalize failed')
        try:
            # best-effort cleanup
            key = (locals().get('key') or '').lstrip('/')
            if key:
                _delete_r2_object_safely(key)
        except Exception:
            pass
        return jsonify({'error': str(e)}), 500

@admin.route('/export_documents')
def export_documents():
    """兼容旧入口：重定向到 Flask-Admin 文档导出端点。"""
    return redirect(url_for('admin_documents.export_all'))


@admin.route('/upload-thumbnail', methods=['POST'])
@csrf.exempt
def upload_thumbnail():
    """接收本地图片并上传为缩略图。

    优先上传到 R2 的 thumbnails/{org}/ 路径（与爬虫/迁移一致），
    若 R2 未配置或失败，则回退为保存到 /static/images/thumbnails/{org}/。

    请求: multipart/form-data
      - image: 文件 (必填)
      - organization_id: 组织ID (必填)
    响应: { success: bool, url?: str, error?: str }
    """
    try:
        image = request.files.get('image')
        org_id = request.form.get('organization_id')

        if not image or not org_id:
            return jsonify({'success': False, 'error': '缺少必要参数（image 或 organization_id）'}), 400

        # 校验组织
        organization = Organization.query.get(org_id)
        if not organization:
            return jsonify({'success': False, 'error': '组织不存在'}), 400

        # 允许的图片类型
        allowed_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
        ext = os.path.splitext(image.filename or '')[1].lower()
        if ext not in allowed_exts:
            return jsonify({'success': False, 'error': f'不支持的图片类型: {ext}'}), 400

        # 生成安全文件名，带时间戳避免冲突
        base = os.path.splitext(secure_filename(image.filename))[0] or 'thumb'
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{base}_{timestamp}{ext}"

        org_dir = organization.name.lower()

        # 尝试上传至 R2（统一路径 thumbnails/{org}/{filename}）
        key = f"thumbnails/{org_dir}/{filename}"
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                tmp_path = os.path.join(td, filename)
                image.save(tmp_path)
                public_url = upload_file(tmp_path, key)
            return jsonify({'success': True, 'url': public_url})
        except Exception:
            logger.exception('upload to R2 failed, fallback to local static')
            # 回退到本地静态目录
            rel_dir = os.path.join('static', 'images', 'thumbnails', org_dir)
            abs_dir = os.path.join(current_app.root_path, rel_dir)
            os.makedirs(abs_dir, exist_ok=True)
            abs_path = os.path.join(abs_dir, filename)
            image.save(abs_path)
            url = f"/static/images/thumbnails/{org_dir}/{filename}"
            return jsonify({'success': True, 'url': url})
    except Exception as e:
        logger.exception('upload-thumbnail failed')
        return jsonify({'success': False, 'error': str(e)}), 500


# --------- Helpers ---------
def _delete_r2_object_safely(key: str):
    try:
        if not key:
            return
        bucket, *_ = _get_config()
        client = _s3_client()
        client.delete_object(Bucket=bucket, Key=key)
        logger.info('Deleted R2 object due to failure: %s', key)
    except Exception:
        logger.exception('Failed to delete R2 object: %s', key)


def _secure_timestamp_name(original_filename: str) -> str:
    base, ext = os.path.splitext(original_filename or '')
    base = secure_filename(base or 'file')
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return f"{base}_{ts}{ext.lower()}"


def _extract_r2_key_from_url(url: str | None) -> str | None:
    """根据当前配置，从公开 URL 反推出 R2 的对象 key。
    支持两种形式：
    - CDN 前缀：CDN_URL/{key}
    - 直连前缀：{endpoint}/{bucket}/{key}
    其他前缀（如本地 /static）返回 None。
    """
    try:
        if not url:
            return None
        bucket, _, _, endpoint, cdn_base = _get_config()
        u = url.strip()
        if cdn_base:
            base = cdn_base.rstrip('/') + '/'
            if u.startswith(base):
                return u[len(base):]
        default_base = f"{endpoint.rstrip('/')}/{bucket}"
        base2 = default_base.rstrip('/') + '/'
        if u.startswith(base2):
            return u[len(base2):]
    except Exception:
        logger.exception('extract key from url failed: %s', url)
    return None
