from typing import Optional

try:
    from markdown import Markdown
except Exception:
    Markdown = None  # type: ignore

try:
    import bleach
except Exception:
    bleach = None  # type: ignore

from markupsafe import Markup, escape


ALLOWED_TAGS = [
    'p', 'br', 'hr', 'pre', 'code', 'blockquote',
    'ul', 'ol', 'li',
    'strong', 'em', 'b', 'i', 'u', 's',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td'
]

ALLOWED_ATTRS = {
    'a': ['href', 'title', 'rel', 'target'],
    'img': ['src', 'alt', 'title'],
    '*': ['class'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def _markdown_to_html(text: str) -> str:
    if not Markdown:
        # 无 markdown 依赖时，按纯文本段落处理
        lines = [l.strip() for l in (text or '').split('\n\n') if l and l.strip()]
        return ''.join(f'<p>{escape(l)}</p>' for l in lines) or ''

    # 基础 Markdown 渲染，启用常用扩展
    md = Markdown(extensions=['fenced_code', 'tables', 'sane_lists'])
    return md.convert(text or '')


def render_markdown_safe(text: Optional[str]) -> Markup:
    """将 Markdown 渲染为安全 HTML。若缺少依赖，降级为安全纯文本段落。

    返回 Markup，供 Jinja 直接输出。
    """
    raw_html = _markdown_to_html(text or '')

    if bleach:
        cleaned = bleach.clean(
            raw_html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRS,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
        )
        # 自动链接化纯文本 URL
        cleaned = bleach.linkify(cleaned, skip_tags=['pre', 'code'])
        return Markup(cleaned)

    # 无 bleach 时，不信任 HTML：转义后按段落输出
    # 直接对原始文本做段落安全包装（避免潜在原生 HTML 注入）
    lines = [l.strip() for l in (text or '').split('\n\n') if l and l.strip()]
    safe_html = ''.join(f'<p>{escape(l)}</p>' for l in lines) or ''
    return Markup(safe_html)


def paragraphs(text: Optional[str]) -> Markup:
    """将文本按空行切段并包裹 <p>，进行 HTML 转义。"""
    if not text:
        return Markup('')
    lines = [l.strip() for l in text.split('\n\n') if l and l.strip()]
    return Markup(''.join(f'<p>{escape(l)}</p>' for l in lines))

