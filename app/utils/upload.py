import os
import tempfile
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from .pdf_preview import generate_document_preview
from .r2 import upload_file, build_public_url

def _key_base(organization_name: str) -> str:
    return f"documents/{organization_name.lower()}"

def generate_filename(title, original_filename, is_chinese=False):
    """Generate filename based on title or original filename with timestamp"""
    # Use title if provided, otherwise use original filename
    base_name = title if title else os.path.splitext(original_filename)[0]
    
    # Add CN suffix for Chinese documents
    if is_chinese:
        base_name = f"{base_name}_CN"
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = os.path.splitext(original_filename)[1]
    
    # Create filename and make it secure
    filename = f"{base_name}_{timestamp}{extension}"
    return secure_filename(filename)

def save_file(file, organization_name, title, is_chinese=False):
    """Save file to Cloudflare R2 and return the public URL (and preview for PDFs).
    Falls back to local static storage only if R2 config is missing.
    """
    filename = generate_filename(title, file.filename, is_chinese)
    org_dir_name = organization_name.lower()
    key = f"{_key_base(organization_name)}/{filename}"

    # Write to a temporary file first
    with tempfile.TemporaryDirectory() as td:
        temp_path = os.path.join(td, filename)
        file.save(temp_path)

        # Try R2 upload
        try:
            public_url = upload_file(temp_path, key)
            if filename.lower().endswith('.pdf'):
                preview_url = generate_document_preview(org_dir_name, filename, temp_path, is_chinese, use_r2=True)
            else:
                preview_url = None
            return public_url, preview_url
        except Exception as e:
            # Fallback to local static if R2 not configured/failed
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'documents', org_dir_name)
            os.makedirs(upload_dir, exist_ok=True)
            final_path = os.path.join(upload_dir, filename)
            with open(temp_path, 'rb') as src, open(final_path, 'wb') as dst:
                dst.write(src.read())
            file_url = f"/static/uploads/documents/{org_dir_name}/{filename}"
            if filename.lower().endswith('.pdf'):
                preview_url = generate_document_preview(org_dir_name, filename, final_path, is_chinese, use_r2=False)
            else:
                preview_url = None
            return file_url, preview_url
