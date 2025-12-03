import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv()
from crawler.translator import get_ai_translation

# 导入日志配置
from logging_config import setup_crawler_logging

# 设置日志
logger = setup_crawler_logging()

base_url = "https://pda.org"
list_url = "https://pda.org/bookstore/pda-bookstore/bookstore-search"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def get_pda_reports(start_row=0, rows_per_page=20):
    category_ids = [
        "9a3ee22c-a74b-4e1e-9571-9af7487c4f25",
        "c3f2b134-82fc-4561-8712-da8ad2451c1b",
        "d832f8f2-7571-4f3c-97b5-6568f4edf0d0",
        "23b1ef82-ed49-4eef-9e9f-1340bcf460c8"
    ]
    params = {
        "Keywords": "",
        "SortOrder": "DESC",
        "TypeFacet": "",
        "startRow": start_row,
        "rowsPerPage": rows_per_page
    }
    for cid in category_ids:
        params.setdefault("Categories", []).append(cid)
    resp = requests.get(list_url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.text

def parse_report_list(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for item in soup.select("ul.item-list > li.item-list__item"):
        a_tag = item.find("a", class_="item-list__link")
        if not a_tag:
            continue
        source_url = a_tag.get("href")
        if source_url and not source_url.startswith("http"):
            source_url = base_url + source_url
        content = a_tag.find("div", class_="item-list__content")
        if not content:
            continue
        title_tag = content.find("h4", class_="item-list__title")
        title = title_tag.get_text(strip=True) if title_tag else None
        # 删除标题中的 "(Single user digital version)"，不区分大小写
        if title:
            import re
            title = re.sub(r"\(?single user digital version\)?", "", title, flags=re.IGNORECASE).strip()
            # 如果标题以 "Technical Report" 或 "PDA Technical Report" 开头，则替换为 "TR"
            title = re.sub(r"^(PDA\s+)?Technical\s+Report", "TR", title, flags=re.IGNORECASE).strip()
        type_tag = content.select_one("div.item-list__tags > span.pill--tertiary")
        prod_type = type_tag.get_text(strip=True) if type_tag else None
        desc_tag = content.select_one("div.item-list__description > div")
        desc = desc_tag.get_text(separator=' ', strip=True).replace('\n', ' ') if desc_tag else None
        # 提取cover_url
        img_tag = item.select_one(".search-thumbnail")
        cover_url = img_tag["src"] if img_tag and img_tag.get("src") else None
        if cover_url:
            # 去掉.jpeg?sfvrsn=xxx 这种尾部参数
            cover_url = re.sub(r"\.jpe?g(\?.*)?$", "", cover_url, flags=re.IGNORECASE)
        results.append({
            "title": title,
            "source_url": source_url,
            "category": prod_type,
            "summary": desc,
            "cover_url": cover_url
        })
    return results

def get_total_count_and_per_page(html):
    soup = BeautifulSoup(html, "html.parser")
    info_tag = soup.select_one(".overview")
    if info_tag:
        m = re.search(r"of\s+(\d+)", info_tag.get_text())
        if m:
            total = int(m.group(1))
            m2 = re.search(r"(\d+)\s*-\s*(\d+)", info_tag.get_text())
            if m2:
                per_page = int(m2.group(2)) - int(m2.group(1)) + 1
            else:
                per_page = 20
            return total, per_page
    return None, 20

detail_cache = {}
def get_publish_date_from_detail(detail_url):
    if detail_url in detail_cache:
        return detail_cache[detail_url]
    try:
        resp = requests.get(detail_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # 1. 优先用精确选择器提取出版日期
        date_tag = soup.select_one("#ContentPlaceholder_TB1B11D42001_interiorLayoutNav > div.card.space-b-150 > div > dl > div:nth-child(1) > dd")
        if date_tag:
            date_text = date_tag.get_text(strip=True)
            if date_text:
                detail_cache[detail_url] = date_text
                return date_text
        # 2. 兜底：全页面查找
        text = soup.get_text(separator='\n')
        m = re.search(r"Published\s*:?\s*([A-Za-z]{3,9}\s+\d{4})", text)
        if m:
            detail_cache[detail_url] = m.group(1)
            return m.group(1)
    except Exception:
        pass
    detail_cache[detail_url] = None
    return None

def normalize_publish_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip().replace('\xa0', ' ').replace('  ', ' ')
    # 支持全英文月份
    try:
        dt = datetime.strptime(date_str, "%B %Y")
        return dt.strftime("%Y-%m-01")
    except Exception:
        pass
    # 支持英文月份缩写
    try:
        dt = datetime.strptime(date_str, "%b %Y")
        return dt.strftime("%Y-%m-01")
    except Exception:
        pass
    # 只给年份
    try:
        dt = datetime.strptime(date_str, "%Y")
        return dt.strftime("%Y-01-01")
    except Exception:
        pass
    # 尝试提取年份
    m = re.search(r"(\d{4})", date_str)
    if m:
        return f"{m.group(1)}-01-01"
    return None

def fetch_detail_date_batch(docs, sleep_sec, show_progress=False, page=1):
    api_key = os.environ.get("TRANSLATOR_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 TRANSLATOR_API_KEY")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_publish_date_from_detail, doc["source_url"]): doc for doc in docs if doc["source_url"]}
        for idx, future in enumerate(as_completed(futures), 1):
            doc = futures[future]
            date_text = future.result()
            doc["original_publish_date"] = date_text
            doc["publish_date"] = normalize_publish_date(date_text)
            # 翻译标题
            try:
                doc["chinese_title"] = get_ai_translation(doc["title"], api_key)
            except Exception as e:
                doc["chinese_title"] = "翻译失败"
            # 翻译摘要
            try:
                summary_text = doc.get("summary")
                doc["chinese_summary"] = get_ai_translation(summary_text, api_key) if summary_text else ""
            except Exception:
                doc["chinese_summary"] = "翻译失败"
            if show_progress:
                print(f"第{page}页 第{idx}条详情页: {doc['title']}")
            time.sleep(sleep_sec)
    return docs

def get_pda_documents(sleep_sec=1, show_progress=False, fetch_detail_date=False):
    all_results = []
    html = get_pda_reports(start_row=0, rows_per_page=20)
    total, per_page = get_total_count_and_per_page(html)
    results = parse_report_list(html)
    if fetch_detail_date:
        results = fetch_detail_date_batch(results, sleep_sec, show_progress=show_progress, page=1)
    else:
        for doc in results:
            doc["original_publish_date"] = None
            doc["publish_date"] = None
            doc["chinese_title"] = None
            doc["chinese_summary"] = None
    for idx, doc in enumerate(results, 1):
        if show_progress:
            print(f"第1页 第{idx}条: {doc['title']}")
    all_results.extend(results)
    if total is None:
        total = len(results)
    total_pages = math.ceil(total / per_page)
    for page in range(1, total_pages):
        html = get_pda_reports(start_row=page*per_page, rows_per_page=per_page)
        results = parse_report_list(html)
        if fetch_detail_date:
            results = fetch_detail_date_batch(results, sleep_sec, show_progress=show_progress, page=page+1)
        else:
            for doc in results:
                doc["original_publish_date"] = None
                doc["publish_date"] = None
                doc["chinese_title"] = None
                doc["chinese_summary"] = None
        # for idx, doc in enumerate(results, 1):
        #     if show_progress:
        #         print(f"第{page+1}页 第{idx}条: {doc['title']}")
        all_results.extend(results)
        time.sleep(sleep_sec)
    return all_results

if __name__ == "__main__":
    import csv
    print("开始爬取PDA技术报告...")
    docs = get_pda_documents(show_progress=True, fetch_detail_date=True)
    print(f"共找到 {len(docs)} 个文档，正在导出为CSV...")
    all_keys = set()
    for doc in docs:
        all_keys.update(doc.keys())
    # 去除format字段
    all_keys.discard("format")
    fieldnames = list(all_keys)
    if "chinese_title" not in fieldnames:
        fieldnames.append("chinese_title")
    if "cover_url" not in fieldnames:
        fieldnames.append("cover_url")
    if "chinese_summary" not in fieldnames:
        fieldnames.append("chinese_summary")
    with open("data/pda_documents.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for doc in docs:
            if "format" in doc:
                doc.pop("format")
            writer.writerow(doc)
    print("导出完成，文件名：data/pda_documents.csv")
