#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的APIC详情页测试
"""

import requests

# 使用简单的请求来查看响应
url = "https://apic.cefic.org/publication/best-practices-guide-for-managing-suppliers-of-api-manufacturers/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

print("正在获取页面内容...")
response = requests.get(url, headers=headers)

print(f"状态码: {response.status_code}")
print(f"内容长度: {len(response.content)}")
print(f"内容类型: {response.headers.get('content-type')}")

# 保存原始内容
with open("raw_response.dat", "wb") as f:
    f.write(response.content)

print("原始响应已保存到 raw_response.dat")

# 尝试以文本形式保存
try:
    with open("response_text.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("文本内容已保存到 response_text.txt")
except Exception as e:
    print(f"保存文本内容时出错: {e}")

# 打印前1000个字符
print("\n响应内容的前1000个字符:")
print(response.text[:1000])