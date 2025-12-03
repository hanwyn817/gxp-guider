import os
import mimetypes
from flask import current_app

try:
    import boto3
    from botocore.config import Config as BotoConfig
except Exception:  # pragma: no cover
    boto3 = None
    BotoConfig = None


def _get_config():
    bucket = current_app.config.get('R2_BUCKET_NAME')
    access_key = current_app.config.get('R2_ACCESS_KEY_ID')
    secret_key = current_app.config.get('R2_SECRET_ACCESS_KEY')
    endpoint = current_app.config.get('R2_ENDPOINT_URL')
    cdn_base = current_app.config.get('CDN_URL')
    return bucket, access_key, secret_key, endpoint, cdn_base


# Cloudflare R2 兼容 S3，但要求：
# - 必须使用 Signature V4 进行预签名（返回 X-Amz-* 参数）；
# - 推荐使用 path-style addressing（避免虚拟主机式带来签名/解析问题）。
def _s3_client():
    if boto3 is None:
        raise RuntimeError('boto3 not installed; cannot use R2 client')
    bucket, access_key, secret_key, endpoint, _ = _get_config()
    if not all([bucket, access_key, secret_key, endpoint]):
        raise RuntimeError('R2 configuration missing; please set R2_* env vars in .env')
    session = boto3.session.Session()
    client = session.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='auto',
        config=BotoConfig(
            signature_version='s3v4',           # R2 需要 SigV4 预签名
            s3={'addressing_style': 'path'}     # 使用 path 样式 /<bucket>/<key>
        )
    )
    return client


def build_public_url(key: str) -> str:
    """Build a public URL for the given object key.
    Prefer CDN_URL if configured; otherwise use endpoint/bucket path.
    """
    bucket, _, _, endpoint, cdn_base = _get_config()
    key = key.lstrip('/')
    if cdn_base:
        return f"{cdn_base}/{key}"
    # Default to R2 HTTP URL (bucket must allow public read)
    return f"{endpoint}/{bucket}/{key}"


def upload_file(local_path: str, key: str, content_type: str | None = None):
    """Upload a local file to R2 under the given key.
    Detect content-type if not provided.
    """
    client = _s3_client()
    bucket, *_ = _get_config()
    key = key.lstrip('/')
    if not content_type:
        content_type, _ = mimetypes.guess_type(local_path)
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    with open(local_path, 'rb') as f:
        client.upload_fileobj(f, bucket, key, ExtraArgs=extra_args)
    return build_public_url(key)


def download_to_path(key: str, local_path: str):
    """Download an object to a specific local path."""
    client = _s3_client()
    bucket, *_ = _get_config()
    key = key.lstrip('/')
    # Ensure parent exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    client.download_file(bucket, key, local_path)
    return local_path


def download_to_temp(key: str) -> str:
    """Download an object to a temporary file and return the path."""
    import tempfile
    _, ext = os.path.splitext(key)
    fd, tmp_path = tempfile.mkstemp(suffix=ext or '')
    os.close(fd)
    return download_to_path(key, tmp_path)


# Helper to generate a SigV4 presigned PUT URL for direct-to-R2 uploads
def generate_presigned_put_url(key: str, content_type: str = 'application/octet-stream', expires_in: int = 600) -> str:
    """Generate a SigV4 presigned PUT URL for direct-to-R2 uploads.
    The returned URL will include X-Amz-* query parameters.
    """
    client = _s3_client()
    bucket, *_ = _get_config()
    safe_key = key.lstrip('/')
    params = {
        'Bucket': bucket,
        'Key': safe_key,
    }
    if content_type:
        params['ContentType'] = content_type
    return client.generate_presigned_url('put_object', Params=params, ExpiresIn=expires_in)
