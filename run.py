#!/usr/bin/env python
import os
from app import create_app, db
from app.models import User, Organization, Category, Document, DownloadStat

app = create_app(os.getenv('FLASK_ENV') or 'default')

@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Organization=Organization, Category=Category,
                Document=Document, DownloadStat=DownloadStat)

if __name__ == '__main__':
    # 本地开发可通过 FLASK_ENV=development 启动 debug，生产禁止强制开启
    app.run(debug=app.config.get('DEBUG', False))
