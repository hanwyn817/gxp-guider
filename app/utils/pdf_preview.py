import os
import tempfile
import uuid
from datetime import datetime
from flask import current_app
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    from PyPDF2 import PdfReader, PdfWriter

def create_preview_pdf(input_path, output_path, pages=10):
    """
    从完整PDF中提取前几页生成预览PDF
    
    Args:
        input_path (str): 输入PDF文件路径
        output_path (str): 输出预览PDF文件路径
        pages (int): 要提取的页数，默认为10
    
    Returns:
        bool: 是否成功创建预览文件
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            print(f"输入文件不存在: {input_path}")
            return False
            
        # 创建输出目录（如果不存在）
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取PDF文件
        reader = PdfReader(input_path)
        
        # 创建新的PDF写入器
        writer = PdfWriter()
        
        # 确定要提取的页数（不能超过总页数）
        total_pages = len(reader.pages)
        pages_to_extract = min(pages, total_pages)
        
        # 提取指定页数
        for i in range(pages_to_extract):
            writer.add_page(reader.pages[i])
        
        # 写入输出文件
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
            
        return True
    except Exception as e:
        print(f"创建预览PDF时出错: {str(e)}")
        return False

def generate_document_preview(organization_name, filename, full_file_path, is_chinese=False, use_r2=True):
    """
    为文档生成预览PDF
    
    Args:
        organization_name (str): 组织名称 (ispe, pda, who)
        filename (str): 文件名
        full_file_path (str): 完整PDF文件路径
        is_chinese (bool): 是否为中文版本
    
    Returns:
        str: 预览文件的URL路径，如果失败则返回None
    """
    try:
        # 使用与原文件名无关的不可推断名称，避免通过预览名推断原始路径/文件名
        # 采用日期分片 + UUID 的方式；预览文件统一使用 .pdf 扩展名
        date_shard = datetime.utcnow().strftime('%Y%m%d')
        random_id = uuid.uuid4().hex
        preview_filename = f"{random_id}.pdf"

        # 生成预览PDF到临时目录
        with tempfile.TemporaryDirectory() as td:
            preview_file_path = os.path.join(td, preview_filename)
            if not create_preview_pdf(full_file_path, preview_file_path):
                return None
            # 上传到 R2 或落地本地
            if use_r2:
                from .r2 import upload_file, build_public_url
                key = f"documents/preview/{organization_name}/{date_shard}/{preview_filename}"
                url = upload_file(preview_file_path, key, content_type='application/pdf')
                return url
            else:
                # 本地静态回退
                preview_dir = os.path.join(
                    current_app.root_path,
                    'static', 'uploads', 'documents', 'preview', organization_name, date_shard
                )
                os.makedirs(preview_dir, exist_ok=True)
                final_path = os.path.join(preview_dir, preview_filename)
                with open(preview_file_path, 'rb') as src, open(final_path, 'wb') as dst:
                    dst.write(src.read())
                return f"/static/uploads/documents/preview/{organization_name}/{date_shard}/{preview_filename}"
    except Exception as e:
        print(f"生成文档预览时出错: {str(e)}")
        return None
