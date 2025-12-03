import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
from dotenv import load_dotenv
load_dotenv()
from crawler.translator import get_ai_translation

# 导入日志配置
from logging_config import setup_crawler_logging

# 设置日志
logger = setup_crawler_logging()

base_urls = {
    "Development": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/development",
    "Production": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/production",
    "Distribution": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/distribution",
    "Inspections": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/inspections",
    "Quality control": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/quality-control",
    "Regulatory standards": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/regulatory-standards",
    "Prequalification": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/prequalification",
    "Quality Assurance": "https://www.who.int/teams/health-product-and-policy-standards/standards-and-specifications/norms-and-standards-for-pharmaceuticals/guidelines/quality-assurance"
}

headers = {
    "User-Agent": "Mozilla/5.0"
}

def parse_guideline_list(html, category):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a_tag in soup.select("a.sf-meeting-report-list__item"):
        # 标题
        title_tag = a_tag.select_one(".trimmed")
        title = title_tag.get_text(strip=True) if title_tag else None
        # 出版日期
        ts_tag = a_tag.select_one(".timestamp")
        pub_date = ts_tag.get_text(strip=True) if ts_tag else None
        # 链接
        source_url = a_tag.get("href")
        if source_url and not source_url.startswith("http"):
            source_url = "https://www.who.int" + source_url
        results.append({
            "title": title,
            "category": category,
            "original_publish_date": pub_date,
            "source_url": source_url
        })
    return results

def parse_guideline_detail(detail_url):
    try:
        resp = requests.get(detail_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # 下载链接
        dl_tag = soup.select_one(".button-blue-background a")
        original_file_url = dl_tag["href"] if dl_tag and dl_tag.has_attr("href") else None
        if original_file_url and not original_file_url.startswith("http"):
            original_file_url = "https://www.who.int" + original_file_url
        # 概述
        summary = None
        h3_tag = soup.find("h3")
        if h3_tag:
            p_tag = h3_tag.find_next_sibling("p")
            if p_tag:
                summary = p_tag.get_text(strip=True)
                # 去掉换行符
                if summary:
                    summary = summary.replace('\n', ' ').replace('\r', ' ')
                # 去掉可能存在的引号包裹
                if summary:
                    if (summary.startswith('"') and summary.endswith('"')) or (summary.startswith("'") and summary.endswith("'")):
                        summary = summary[1:-1]
        return summary, original_file_url
    except Exception:
        return None, None

def normalize_publish_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%d %B %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        dt = datetime.strptime(date_str.strip(), "%B %Y")
        return dt.strftime("%Y-%m-01")
    except Exception:
        pass
    try:
        dt = datetime.strptime(date_str.strip(), "%Y")
        return dt.strftime("%Y-01-01")
    except Exception:
        pass
    m = re.search(r"(\d{4})", date_str)
    if m:
        return f"{m.group(1)}-01-01"
    return None

def normalize_title_for_trs(title: str) -> str:
    """If title starts with 'trs' (case-insensitive), return the substring
    after the first colon, trimming a following space if present.

    Handles both ASCII ':' and full-width '：'. If no colon is found,
    returns the original title.
    """
    if not title:
        return title
    if not title.strip().lower().startswith("trs"):
        return title
    # Find the first occurrence among colon variants
    colon_chars = [":", "："]
    first_idx = -1
    for cc in colon_chars:
        idx = title.find(cc)
        if idx != -1 and (first_idx == -1 or idx < first_idx):
            first_idx = idx
    if first_idx == -1:
        return title
    new_title = title[first_idx + 1:]
    # Remove the space immediately after the colon (and any extra spaces)
    new_title = new_title.lstrip()
    return new_title

def get_who_guidelines(sleep_sec=1, show_progress=False):
    api_key = os.environ.get("TRANSLATOR_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 TRANSLATOR_API_KEY")
    all_results = []
    for category, url in base_urls.items():
        print(f"抓取分类: {category} ...")
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        guidelines = parse_guideline_list(resp.text, category)
        for idx, guideline in enumerate(guidelines, 1):
            if show_progress:
                print(f"  {category} 第{idx}条: {guideline['title']}")
            summary, original_file_url = parse_guideline_detail(guideline["source_url"]) if guideline["source_url"] else (None, None)
            if summary:
                summary = summary.replace('\n', ' ')
            guideline["summary"] = summary
            guideline["original_file_url"] = original_file_url
            guideline["publish_date"] = normalize_publish_date(guideline["original_publish_date"])
            # 翻译摘要
            try:
                guideline["chinese_summary"] = get_ai_translation(summary, api_key) if summary else ""
            except Exception:
                guideline["chinese_summary"] = "翻译失败"
            # 翻译标题
            try:
                # 若以 TRS 开头，仅在翻译前对标题进行规范化（不修改原 title）
                trans_input = normalize_title_for_trs(guideline["title"]) or guideline["title"]
                guideline["chinese_title"] = get_ai_translation(trans_input, api_key)
            except Exception as e:
                guideline["chinese_title"] = "翻译失败"
            time.sleep(sleep_sec)
        all_results.extend(guidelines)
    return all_results

if __name__ == "__main__":
    import csv
    print("开始抓取WHO指南...")
    docs = get_who_guidelines(show_progress=True)
    print(f"共抓取 {len(docs)} 条，正在导出为CSV...")
    fieldnames = [
        "title",
        "chinese_title",
        "category",
        "original_publish_date",
        "publish_date",
        "summary",
        "chinese_summary",
        "original_file_url",
        "source_url",
    ]
    with open("data/who_documents.csv", "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for doc in docs:
            writer.writerow(doc)
    print("导出完成，文件名：data/who_documents.csv")
