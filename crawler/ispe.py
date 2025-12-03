import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from crawler.translator import get_ai_translation

# 导入日志配置
from logging_config import setup_crawler_logging

# 设置日志
logger = setup_crawler_logging()

base_url = "https://guidance-docs.ispe.org"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0"
}

def get_main_page():
    """
    首先尝试从网络获取页面内容，如果失败则从本地ispe.html文件读取
    """
    try:
        # 尝试从网络获取
        print("正在尝试从网络获取页面内容...")
        session = requests.Session()
        session.headers.update(headers)
        
        url = f"{base_url}/action/showPublications?pageSize=200&startPage=0"
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        print("成功从网络获取页面内容")
        return resp.text
    except Exception as e:
        print(f"从网络获取失败: {e}")
        print("尝试从本地文件读取...")
        try:
            # 从与 ispe.py 同目录的本地文件读取
            current_dir = os.path.dirname(os.path.abspath(__file__))
            local_path = os.path.join(current_dir, "ispe.html")
            with open(local_path, "r", encoding="utf-8") as f:
                print(f"成功从本地文件读取内容: {local_path}")
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                "无法从网络获取页面内容，且在与 ispe.py 同目录下未找到 ispe.html 文件"
            )

def parse_main_page(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # 选择包含每个项目的父元素，而不是仅仅选择.item__body
    for item in soup.select(".search__item"):
        # 提取完整标题
        title_tag = item.select_one(".hlFld-Title")
        if title_tag:
            # 先处理HTML标签，再去掉®字符
            full_title = str(title_tag)
            # 去除HTML标签之前，先处理<sup>®</sup>标签
            full_title = re.sub(r"<sup>®</sup>", " ", full_title, flags=re.IGNORECASE)  # 用空格替换
            full_title = re.sub(r"®", " ", full_title)  # 用空格替换直接的®字符
            # 去除HTML标签
            soup_text = BeautifulSoup(full_title, "html.parser")
            full_title = soup_text.get_text(strip=True)
            # 清理多余的空格
            full_title = re.sub(r'\s+', ' ', full_title)
        else:
            full_title = "未知标题"
        
        # 从完整标题中提取类别（第一个冒号之前的内容）
        category = "未知类型"
        title = full_title  # 默认使用完整标题作为文档标题
        if ":" in full_title:
            parts = full_title.split(":", 1)
            category = parts[0].strip()
            # print(f"Debug - Original category: {repr(category)}")  # 调试输出
            # 去除分类中开头的ISPE
            if category.startswith("ISPE"):
                category = category[4:].strip()  # 去掉"ISPE"前缀及后面的空格
                # print(f"Debug - After removing ISPE: {repr(category)}")  # 调试输出
            # 去除®字符
            category = category.replace("®", "")
            # print(f"Debug - Final category: {repr(category)}")  # 调试输出
            title = parts[1].strip()  # 文档标题是第一个冒号之后的内容
        # 去除标题中的®字符
        title = title.replace("®", "")
        
        # 跳过包含"Translation"但不包含"English Translation"的项目
        if "Translation" in title and "English Translation" not in title:
            continue
        
        # 提取详情页链接
        link_tag = item.select_one(".meta__title a")  # 从标题中的链接提取
        source_url = ""
        if link_tag and link_tag.get("href"):
            source_url = link_tag["href"]
            if source_url.startswith("/"):
                source_url = base_url + source_url

        # 提取发布日期
        date_tag = item.select_one(".meta__coverDate")
        original_publish_date = date_tag.get_text(strip=True).replace("Published:", "").strip() if date_tag else None
        
        # 提取摘要
        summary_tag = item.select_one(".accordion__content.card--shadow")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""
        # 删除摘要中的换行符
        summary = summary.replace("\n", " ").replace("\r", " ")
        
        # 提取封面图片URL：只取文件名并根据环境生成路径（优先 CDN → R2 → 本地）
        img_tag = item.select_one(".item__image img")
        cover_url = ""
        if img_tag and img_tag.get("src"):
            # 只提取图片文件名
            cover_filename = img_tag["src"].split("/")[-1]
            # 优先使用 CDN_URL
            cdn_url = os.getenv("CDN_URL")
            if cdn_url:
                cover_url = f"{cdn_url.rstrip('/')}/thumbnails/ispe/{cover_filename}"
            else:
                # 次选使用 R2 直链（需公共可读或由 CDN 代理）
                r2_endpoint = os.getenv("R2_ENDPOINT_URL")
                r2_bucket = os.getenv("R2_BUCKET_NAME")
                if r2_endpoint and r2_bucket:
                    cover_url = f"{r2_endpoint.rstrip('/')}/{r2_bucket}/thumbnails/ispe/{cover_filename}"
                else:
                    # 回退到本地静态资源路径
                    cover_url = f"/static/images/thumbnails/ispe/{cover_filename}"
        
        results.append({
            "category": category,
            "title": title,  # 文档标题是第一个冒号之后的内容
            "source_url": source_url,
            "cover_url": cover_url,
            "original_publish_date": original_publish_date,
            "summary": summary
        })
    return results

def normalize_publish_date(date_str):
    """
    将如 'June 2025' 转为 '2025-06-01'，如 '2025' 转为 '2025-01-01'，无法解析则返回None。
    """
    if not date_str:
        return None
    try:
        # 先尝试 'Month YYYY'
        dt = datetime.strptime(date_str.strip(), "%B %Y")
        return dt.strftime("%Y-%m-01")
    except Exception:
        pass
    try:
        # 只给年份
        dt = datetime.strptime(date_str.strip(), "%Y")
        return dt.strftime("%Y-01-01")
    except Exception:
        pass
    return None

def get_ispe_documents(sleep_sec=0.2, show_progress=False):
    import time
    api_key = os.environ.get("TRANSLATOR_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 TRANSLATOR_API_KEY")
    html = get_main_page()
    docs = parse_main_page(html)
    total = len(docs)
    for idx, doc in enumerate(docs, 1):
        if show_progress:
            print(f"正在处理 ({idx}/{total}): {doc['title']}")
        try:
            # 处理发布日期
            doc["publish_date"] = normalize_publish_date(doc["original_publish_date"])
            # 翻译摘要
            try:
                doc["chinese_summary"] = get_ai_translation(doc.get("summary") or "", api_key) if doc.get("summary") else ""
            except Exception:
                doc["chinese_summary"] = "翻译失败"
            # 翻译标题
            try:
                doc["chinese_title"] = get_ai_translation(doc["title"], api_key)
            except Exception as e:
                doc["chinese_title"] = "翻译失败"
            time.sleep(sleep_sec)
        except Exception:
            doc["publish_date"] = None
            doc["chinese_title"] = None
            doc["chinese_summary"] = None
    return docs

if __name__ == "__main__":
    import csv
    print("开始获取和处理ISPE指南文档...")
    docs = get_ispe_documents(show_progress=True)
    print(f"共找到 {len(docs)} 个文档，正在导出为CSV...")
    with open("data/ispe_documents.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "title",
                "chinese_title",
                "publish_date",
                "original_publish_date",
                "source_url",
                "cover_url",
                "summary",
                "chinese_summary",
            ],
        )
        writer.writeheader()
        for doc in docs:
            writer.writerow(doc)
    print("导出完成，文件名：data/ispe_documents.csv")
