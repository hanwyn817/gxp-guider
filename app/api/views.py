from flask import jsonify, request, url_for
from . import api
from ..models import Document, User
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func

@api.route('/documents')
def get_documents():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    file_filter = request.args.get('file', '').strip()  # '', 'any', 'original', 'translation'
    has_file = request.args.get('has_file', '').strip().lower() in ['1', 'true', 'yes']
    
    query = Document.query

    if file_filter or has_file:
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
        else:
            query = query.filter(or_(non_empty_original, non_empty_translation))

    pagination = query.paginate(
        page=page, per_page=per_page, error_out=False)
    docs = pagination.items
    
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_documents', page=page-1, per_page=per_page, file=file_filter or None, has_file=('true' if has_file else None), _external=True)
    
    next = None
    if pagination.has_next:
        next = url_for('api.get_documents', page=page+1, per_page=per_page, file=file_filter or None, has_file=('true' if has_file else None), _external=True)
    
    return jsonify({
        'documents': [doc.to_json() for doc in docs],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })

@api.route('/documents/<int:id>')
def get_document(id):
    doc = Document.query.get_or_404(id)
    return jsonify(doc.to_json())

@api.route('/users/me')
@login_required
def get_current_user():
    return jsonify(current_user.to_json())
