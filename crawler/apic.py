import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import json
import re
import time
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from crawler.translator import get_ai_translation

# 导入日志配置
from logging_config import setup_crawler_logging

load_dotenv()

# ==================== 日志与常量 ====================
logger = setup_crawler_logging()

BASE_URL = "https://apic.cefic.org"
PUBLICATIONS_URL = f"{BASE_URL}/publications/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

DOC_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf")
DOWNLOAD_PATTERNS = ("download", "pdf", "doc", "下载", "Download", "PDF", "DOC")
LOCAL_HTML_NAME = "apic.html"
CSV_OUT_PATH = "data/apic_documents.csv"


# ==================== 会话与通用工具 ====================
def get_session() -> requests.Session:
    """创建并返回一个带默认请求头的会话。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def is_document_url(url: Optional[str]) -> bool:
    """判断URL是否指向文档文件。"""
    if not url:
        return False
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    return path.endswith(DOC_EXTENSIONS)


def absolutize(href: str, base: str) -> str:
    """将相对链接转为绝对链接。"""
    return urljoin(base, href)


def normalize_publish_date(date_str: Optional[str]) -> Optional[str]:
    """将如 '13/06/2025' 转为 '2025-06-13'，无法解析则返回None。"""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


# ==================== 页面获取与解析 ====================
def _read_local_html() -> Optional[str]:
    """尝试从与脚本同目录下的本地文件读取HTML。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_file_path = os.path.join(script_dir, LOCAL_HTML_NAME)
    if not os.path.exists(local_file_path):
        return None
    with open(local_file_path, "r", encoding="utf-8") as f:
        logger.info("成功从本地文件读取内容: %s", LOCAL_HTML_NAME)
        return f.read()


def _fetch_remote_html(url: str) -> str:
    """从网络获取HTML。失败抛出异常。"""
    logger.info("本地文件不存在，尝试从网络获取页面内容: %s", url)
    session = get_session()
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    logger.info("成功从网络获取页面内容")
    return resp.text


def get_publications_page() -> str:
    """优先从本地读取，失败则从网络获取。"""
    html = _read_local_html()
    if html is not None:
        return html
    return _fetch_remote_html(PUBLICATIONS_URL)


def parse_publications_page(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: List[dict] = []

    for item in soup.select(".list-item.publication"):
        # 标题与详情页链接
        title_tag = item.select_one(".list-title a")
        title = title_tag.get_text(strip=True) if title_tag else "未知标题"
        source_url = ""
        if title_tag and title_tag.get("href"):
            href = title_tag["href"]
            source_url = absolutize(href, BASE_URL)

        # 下载链接（可能是网页也可能是文件）
        download_link = ""
        download_tag = item.select_one(".links .list-read-more")
        if download_tag and download_tag.get("href"):
            download_link = absolutize(download_tag["href"], BASE_URL)

        # 发布日期（原始）
        date_tag = item.select_one(".list-date")
        original_publish_date = date_tag.get_text(strip=True) if date_tag else None

        # original_file_url 与最终的 source_url 归一化，并新增 needs_detail 标记
        original_file_url = None
        final_source_url = source_url
        needs_detail = False
        if is_document_url(download_link):
            # 直接是文件链接：无需解析详情页
            original_file_url = download_link
            needs_detail = False
        elif download_link:
            # 不是文件链接：说明是网页，需要解析详情页
            final_source_url = download_link
            needs_detail = True

        results.append(
            {
                "title": title,
                "source_url": final_source_url,
                "original_file_url": original_file_url,
                "original_publish_date": original_publish_date,
                "category": "APIC Publication",
                "needs_detail": needs_detail,
            }
        )

    return results


def get_all_publications() -> List[dict]:
    """获取所有出版物列表（解析列表页）。"""
    html = get_publications_page()
    return parse_publications_page(html)


# ==================== 详情页面处理 ====================
def _find_document_links(soup: BeautifulSoup, source_url: str) -> List[str]:
    """在详情页中查找所有文档链接。"""
    links: List[str] = []

    # 方式1：所有 a[href] 直接判定是否为文档
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href:
            continue
        abs_url = absolutize(href, source_url)
        if is_document_url(abs_url):
            links.append(abs_url)

    # 方式2：关键词匹配（兜底）
    for pattern in DOWNLOAD_PATTERNS:
        for a in soup.find_all("a", href=True, string=re.compile(pattern, re.IGNORECASE)):
            href = a.get("href")
            if not href:
                continue
            abs_url = absolutize(href, source_url)
            if is_document_url(abs_url):
                links.append(abs_url)

    # 去重并优先返回 PDF 链接
    if not links:
        return []
    unique_links = []
    seen = set()
    for u in links:
        if u not in seen:
            seen.add(u)
            unique_links.append(u)
    # 排序时优先 PDF，其次按字母序稳定排序
    unique_links.sort(key=lambda u: (0 if u.lower().endswith('.pdf') else 1, u))
    return unique_links


def get_document_detail(source_url: str) -> Tuple[Optional[str], Optional[str]]:
    """获取详情页中的原始文档URL和摘要。"""
    if not source_url:
        return None, None

    logger.debug("  正在获取详情页面: %s", source_url)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        resp = requests.get(source_url, headers=headers)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("  获取详情页面失败: %s", e)
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    document_links = _find_document_links(soup, source_url)

    if not document_links:
        return None, None
    if len(document_links) == 1:
        return document_links[0], None

    # 多个文件时，保留第一个并给出摘要提示
    summary = "本文档包含多个文件，请到详情页面下载：" + "、".join(document_links)
    return document_links[0], summary


# ==================== 主要功能函数 ====================
def get_apic_documents(
    sleep_sec: float = 0.2, *, show_progress: bool = False, fetch_details: bool = False
) -> List[dict]:
    """抓取 APIC 列表并可选抓取详情页，返回文档字典列表。"""
    api_key = os.environ.get("TRANSLATOR_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 TRANSLATOR_API_KEY")

    docs = get_all_publications()
    total = len(docs)
    logger.info("共找到 %d 个文档", total)

    for idx, doc in enumerate(docs, 1):
        if show_progress:
            print(f"正在处理 ({idx}/{total}): {doc['title']}")

        try:
            # 处理发布日期
            doc["publish_date"] = normalize_publish_date(doc.get("original_publish_date"))

            # 详情页处理：仅当下载链接是网页（needs_detail 为 True）且有 source_url 时，才解析详情页
            if fetch_details and doc.get("needs_detail") and doc.get("source_url"):
                original_file_url, summary = get_document_detail(doc["source_url"])  # type: ignore[arg-type]
                if original_file_url:
                    doc["original_file_url"] = original_file_url
                if summary:
                    doc["summary"] = summary

            # 注：是否解析详情页与标题翻译互不影响
            # 翻译标题
            try:
                doc["chinese_title"] = get_ai_translation(doc["title"], api_key)
            except Exception as e:
                logger.warning("标题翻译失败: %s", e)
                doc["chinese_title"] = "翻译失败"

            time.sleep(sleep_sec)
        except Exception as e:
            logger.warning("处理文档 '%s' 时出错: %s", doc.get("title", ""), e)
            doc.setdefault("publish_date", None)
            doc.setdefault("chinese_title", None)

    return docs


# ==================== 程序入口 ====================
if __name__ == "__main__":
    print("开始获取和处理APIC文档...")
    docs = get_apic_documents(show_progress=True, fetch_details=True)

    # 确保输出目录存在
    out_dir = os.path.dirname(CSV_OUT_PATH)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    print(f"共找到 {len(docs)} 个文档，正在导出为CSV...")
    fieldnames = [
        "title",
        "chinese_title",
        "category",
        "original_publish_date",
        "publish_date",
        "source_url",
        "original_file_url",
        "summary",
    ]

    with open(CSV_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for doc in docs:
            # 确保缺失键存在
            for key in fieldnames:
                doc.setdefault(key, None)
            writer.writerow(doc)

    print(f"导出完成，文件名：{CSV_OUT_PATH}")