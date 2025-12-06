import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data.sqlite')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 静态资源缓存时间（默认 7 天，可通过环境变量覆盖）
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get('SEND_FILE_MAX_AGE_DEFAULT', '604800'))
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in \
        ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    GMP_SEEKER_MAIL_SUBJECT_PREFIX = '[GxP Guider]'
    GMP_SEEKER_MAIL_SENDER = 'GxP Guider Admin <admin@gmpseeker.com>'
    GMP_SEEKER_ADMIN = os.environ.get('GMP_SEEKER_ADMIN')
    # R2配置
    R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
    R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
    R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
    R2_ENDPOINT_URL = os.environ.get('R2_ENDPOINT_URL')
    CDN_URL = os.environ.get('CDN_URL')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite://'

class ProductionConfig(Config):
    # 默认生产库与启动脚本一致，落在 /app/data/data.sqlite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'data.sqlite')

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
