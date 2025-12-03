import os
import sys
import csv
from datetime import datetime
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入翻译功能
from crawler.translator import get_ai_translation
from dotenv import load_dotenv
load_dotenv()

def parse_date(date_str):
    """
    将日期从 月月/日日/年年年年 格式转换为 年年年年-月月-日日 格式
    """
    try:
        # 处理日期格式 月月/日日/年年年年 (例如: 01/15/2023)
        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        try:
            # 处理可能的两位数年份格式 月月/日日/年年 (例如: 01/15/23)
            date_obj = datetime.strptime(date_str, '%m/%d/%y')
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            # 如果解析失败，返回原始字符串
            return date_str

def extract_documents_from_html(html_file_path):
    """
    从单个 HTML 文件中提取文档信息
    """
    documents = []
    
    with open(html_file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        
        # 查找表格
        table = soup.find('table', {'id': 'DataTables_Table_0'})
        if not table:
            print(f"在文件 {html_file_path} 中未找到 DataTables_Table_0 表格")
            return documents
            
        # 解析表格行
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:  # 确保有足够的列
                # 第一列: title 和 source_url
                title_cell = cols[0]
                title_link = title_cell.find('a')
                title = title_link.get_text(strip=True) if title_link else title_cell.get_text(strip=True)
                source_url = title_link.get('href') if title_link else ''
                
                # 第二列: original_file_url
                file_cell = cols[1]
                file_link = file_cell.find('a')
                original_file_url = file_link.get('href') if file_link else ''
                
                # 第三列: publish_date
                date_cell = cols[2]
                publish_date_str = date_cell.get_text(strip=True)
                publish_date = parse_date(publish_date_str)
                
                # 创建文档字典
                document = {
                    'title': title,
                    'source_url': source_url,
                    'original_file_url': original_file_url,
                    'publish_date': publish_date,
                    'category': 'FDA Guidance'
                }
                
                documents.append(document)
    
    return documents

def process_fda_guidance_documents():
    """
    主函数：处理所有以 fda-guidance 开头的 HTML 文件
    """
    # 获取当前脚本所在目录（crawler目录）
    crawler_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取项目根目录和数据目录
    project_root = os.path.dirname(crawler_dir)
    data_dir = os.path.join(project_root, 'data')
    output_csv = os.path.join(data_dir, 'fda_guidance_documents.csv')
    
    # 确保 data 目录存在
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # 获取API密钥
    api_key = os.environ.get("TRANSLATOR_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 TRANSLATOR_API_KEY")
    
    # 存储所有文档，避免重复
    all_documents = []
    seen_documents = set()  # 用于跟踪已处理的文档
    
    # 查找所有以 fda-guidance 开头的 HTML 文件（在crawler目录中）
    html_files = [f for f in os.listdir(crawler_dir) if f.startswith('fda-guidance') and f.endswith('.html')]
    
    print(f"找到 {len(html_files)} 个 HTML 文件")
    
    for html_file in html_files:
        html_file_path = os.path.join(crawler_dir, html_file)
        print(f"正在处理: {html_file}")
        
        # 从 HTML 文件中提取文档
        documents = extract_documents_from_html(html_file_path)
        print(f"从 {html_file} 中提取到 {len(documents)} 个文档")
        
        # 检查重复并添加新文档
        for doc in documents:
            # 使用 title 和 original_file_url 作为唯一标识符
            doc_identifier = (doc['title'], doc['original_file_url'])
            
            if doc_identifier not in seen_documents:
                all_documents.append(doc)
                seen_documents.add(doc_identifier)
            else:
                print(f"跳过重复文档: {doc['title']}")
    
    # 为文档添加翻译
    print(f"正在翻译 {len(all_documents)} 个文档...")
    
    for doc in all_documents:
        try:
            # 翻译标题
            try:
                doc["chinese_title"] = get_ai_translation(doc["title"], api_key)
            except Exception as e:
                doc["chinese_title"] = "翻译失败"
        except Exception as e:
            print(f"翻译文档 '{doc['title']}' 时出错: {e}")
            doc["chinese_title"] = "翻译失败"
    
    # 写入 CSV 文件到项目根目录下的data目录
    if all_documents:
        fieldnames = ['title', 'chinese_title', 'source_url', 'original_file_url', 'publish_date', 'category']
        
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for doc in all_documents:
                writer.writerow(doc)
        
        print(f"总共处理了 {len(all_documents)} 个唯一文档，已保存到 {output_csv}")
    else:
        print("未找到任何文档")

if __name__ == "__main__":
    process_fda_guidance_documents()