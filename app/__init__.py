from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_admin import Admin as FlaskAdmin
from flask_wtf.csrf import CSRFProtect
from config import config
from sqlalchemy import event
import sqlite3

# 导入日志配置
from logging_config import setup_logging

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 可选：启用 gzip 压缩（如未安装 Flask-Compress 则忽略）
    try:
        from flask_compress import Compress
        Compress(app)
    except Exception:
        pass

    # 若使用 SQLite，设置 WAL/同步 等 PRAGMA 以提升小站点并发与稳定性
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if isinstance(db_uri, str) and db_uri.startswith('sqlite'):
            engine = db.engine

            def _set_sqlite_pragmas(dbapi_connection, connection_record):
                if isinstance(dbapi_connection, sqlite3.Connection):
                    cursor = dbapi_connection.cursor()
                    try:
                        cursor.execute('PRAGMA journal_mode=WAL')
                        cursor.execute('PRAGMA synchronous=NORMAL')
                        cursor.execute('PRAGMA temp_store=MEMORY')
                        # 负值表示 KB，-2000 约等于 2MB page cache
                        cursor.execute('PRAGMA cache_size=-2000')
                    finally:
                        cursor.close()

            event.listen(engine, 'connect', _set_sqlite_pragmas)
    
    # 设置登录视图
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录以访问此页面。'
    
    # 用户加载函数
    from .models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 设置日志
    setup_logging(app)

    # 注册 Jinja 过滤器：markdown 渲染与段落包装
    try:
        from .utils.markdown import render_markdown_safe, paragraphs as paragraphs_filter
        app.jinja_env.filters['markdown'] = render_markdown_safe
        app.jinja_env.filters['paragraphs'] = paragraphs_filter
    except Exception:
        # 过滤器注册失败不阻塞应用启动
        pass
    
    # 注册蓝图
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    # 初始化 Flask-Admin
    from .admin import MyAdminIndexView, init_admin, admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    flask_admin = FlaskAdmin(name='GxP Guider', template_mode='bootstrap4', index_view=MyAdminIndexView())
    flask_admin.init_app(app)
    init_admin(flask_admin, app)
    
    return app
