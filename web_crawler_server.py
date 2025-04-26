import requests
import json
import re
import selenium
import time
# 导入 bs4
import bs4
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from urllib.parse import urljoin # 用于处理相对 URL

# --- 配置 ---
# 设置浏览器驱动路径 (请确保路径正确)
driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"

# --- 新增：获取搜索标题函数 ---
def get_search_title(query):
    """
    实时获取搜索过程中的页面标题
    返回搜索结果页面标题列表
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--lang=zh-CN")
    options.add_argument('user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"')

    service = ChromeService(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # 初始化标题列表，先添加查询标题
        titles = [f"{query}_百度搜索"]
        
        # 访问百度搜索页面
        base_url = "https://www.baidu.com"
        search_url = f"{base_url}/s?wd={query}"
        driver.get(search_url)
        
        # 等待页面加载
        time.sleep(2)
        
        # 添加当前页面标题
        page_title = driver.title.strip()
        if page_title and page_title not in titles:
            titles.append(page_title)
        
        # 从搜索结果中获取链接
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        search_results = soup.select('div.result h3 a, div.c-container h3 a')
        
        # 限制链接数量，避免处理时间过长
        max_links = 3
        links = []
        
        for i, result in enumerate(search_results):
            if i >= max_links:
                break
                
            # 获取链接
            href = result.get('href')
            if href and href.startswith('http'):
                # 排除广告链接
                if not re.search(r'(广告|推广|baidu\.com/link)', href, re.I):
                    links.append(href)
        
        # 依次访问链接并获取标题
        for link in links:
            try:
                driver.get(link)
                # 等待页面加载
                time.sleep(2)
                
                # 获取并添加标题
                link_title = driver.title.strip()
                if link_title and link_title not in titles:
                    titles.append(link_title)
            except Exception as e:
                print(f"访问链接时出错: {e}")
                continue
        
        return titles
    except Exception as e:
        print(f"获取搜索标题时出错: {e}")
        # 返回默认标题
        return [f"{query}_搜索结果", f"{query} - 百度百科", f"关于{query}的信息"]
    finally:
        if driver:
            driver.quit()

# --- 新增：获取页面正文内容的函数 ---
def get_full_content(url):
    """
    尝试访问给定 URL 并提取主要文本内容。

    Args:
        url (str): 要访问的网页 URL。

    Returns:
        str: 提取到的主要文本内容，如果失败则返回 None。
    """
    print(f"正在尝试获取正文内容: {url}")
    
    # 直接使用 Selenium 提取文本内容，以避免编码问题
    return extract_text_with_selenium(url)

# 检查文本是否可读（非乱码）
def is_readable_text(text, threshold=0.3):
    """
    简单检查文本是否为乱码，通过计算特殊字符比例
    
    Args:
        text: 要检查的文本
        threshold: 特殊字符比例阈值，超过则视为乱码
        
    Returns:
        bool: 如果文本非乱码返回True，否则返回False
    """
    if not text:
        return False
    
    # 检查常见乱码特征
    if 'ï¿½' in text or 'â€' in text or 'ã€' in text:
        return False
    
    # 计算不可打印字符比例
    special_chars = sum(1 for c in text if not c.isprintable() or ord(c) > 127)
    if len(text) > 0 and special_chars / len(text) > threshold:
        return False
    
    return True

# 使用Selenium直接提取文本(处理乱码情况)
def extract_text_with_selenium(url):
    """
    使用Selenium直接访问页面并提取文本，避免编码问题
    """
    print("使用Selenium直接提取文本内容...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_argument('user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"')

    try:
        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(3)  # 等待页面加载
        
        # 移除不需要的元素
        for element_type in ['script', 'style', 'nav', 'footer', 'header']:
            elements = driver.find_elements(By.TAG_NAME, element_type)
            for element in elements:
                driver.execute_script("arguments[0].remove()", element)
        
        # 尝试查找主要内容区域
        main_selectors = [
            'article', 'main', 
            'div.content', 'div.main', 'div.article', 'div.post',
            '#content', '#main', '#article', '#post',
            '.article-content', '.post-content', '.entry-content',
            '.blog-post'
        ]
        
        for selector in main_selectors:
            try:
                main_element = driver.find_element(By.CSS_SELECTOR, selector)
                content = main_element.text
                if content and len(content) > 100:  # 确保有足够内容
                    driver.quit()
                    return content
            except:
                continue
        
        # 如果找不到特定容器，获取body文本
        body = driver.find_element(By.TAG_NAME, 'body')
        content = body.text
        driver.quit()
        return content
        
    except Exception as e:
        print(f"使用Selenium提取文本时出错: {e}")
        if 'driver' in locals():
            driver.quit()
        return "无法获取文本内容"


# --- 修改后的 search 函数 ---
def search(query):
    """
    搜索策略：
    查找多条结果的标题和摘要，并为前三条有效结果提取正文内容。
    """
    options=webdriver.ChromeOptions()
    options.add_argument("--headless") # 使用无头模式，不显示浏览器窗口
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--lang=zh-CN")
    options.add_argument('user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"')

    service=ChromeService(executable_path=driver_path)
    driver=webdriver.Chrome(service=service,options=options)
    driver.implicitly_wait(5)

    # 使用百度搜索
    base_url = "https://www.baidu.com" # 用于拼接相对 URL
    search_url=f"{base_url}/s?wd={query}"
    extract_data = [] # 存储最终结果
    content_count = 0  # 已经提取的正文数量
    max_content = 3    # 最多提取3篇正文

    try:
        driver.get(search_url)
        print(f"页面标题: {driver.title}")
        time.sleep(3) # 等待页面初步渲染

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        search_results = soup.select('div.result, div.c-container') # 查找结果容器
        print(f"找到 {len(search_results)} 个可能的搜索结果容器")

        count = 0
        max_results = 9 # 限制总结果数

        for result in search_results:
            if count >= max_results:
                break
                
            try:
                # --- 广告过滤 ---
                result_text = result.get_text()
                # 更严格的广告判断
                is_ad = False
                ad_selectors = ['span[data-tuiguang]', 'a[data-rank]', 'span.ec-tuiguang', '.ec_tuiguang_link']
                for ad_selector in ad_selectors:
                    if result.select_one(ad_selector):
                        is_ad = True
                        break
                if is_ad or "广告" in result_text[:20]: # 检查开头是否包含广告字样
                    print("跳过广告内容")
                    continue

                # --- 提取标题 ---
                title_element = result.select_one('h3, h3.t, a.c-title')
                if not title_element:
                    continue # 没有标题则跳过

                title = title_element.get_text().strip()
                # 再次检查标题附近是否有广告标记
                parent_text = title_element.parent.get_text() if title_element.parent else ""
                if "广告" in parent_text[:20] or "赞助" in parent_text[:20]:
                    print(f"跳过疑似广告内容 (标题附近): {title}")
                    continue
                print(f"找到标题: {title}")

                # --- 提取 URL (内部使用，不输出) ---
                url = None
                # 优先从标题的父级<a>标签获取
                if title_element.parent and title_element.parent.name == 'a':
                    url = title_element.parent.get('href')
                # 否则尝试从标题元素自身或其内部的<a>标签获取
                elif title_element.name == 'a':
                     url = title_element.get('href')
                elif title_element.select_one('a'):
                    url = title_element.select_one('a').get('href')

                # 处理可能的相对 URL (虽然百度现在较少见)
                if url and not url.startswith(('http://', 'https://')):
                    url = urljoin(base_url, url)

                # --- 提取摘要 ---
                snippet = ""
                snippet_element = result.select_one('div.c-abstract, div.c-span-last, span.content-right_8Zs40, .c-gap-top-small') # 添加更多可能的选择器
                if snippet_element:
                    snippet = snippet_element.get_text().strip()
                else:
                     # 备用方案：获取整个结果块的文本并清理
                    content_text = result.get_text(separator=' ', strip=True)
                    if title in content_text:
                        content_text = content_text.replace(title, '', 1).strip()
                    # 移除可能的 URL 显示文本
                    show_url_el = result.select_one('.c-showurl, .c-showurl-color')
                    if show_url_el:
                         content_text = content_text.replace(show_url_el.get_text(strip=True), '', 1).strip()
                    snippet = content_text[:200].strip() # 限制长度

                # 再次过滤包含广告词的摘要
                if "广告" in snippet or "赞助" in snippet:
                    print(f"摘要中含有广告标记，跳过: {title}")
                    continue
                print(f"找到摘要: {snippet[:30]}...")

                # --- 存储基础数据 ---
                if title and snippet:
                    result_data = {
                        "title": title,
                        "snippet": snippet
                    }

                    # --- 尝试提取正文 (最多提取3篇) ---
                    if url and content_count < max_content:
                        full_content = get_full_content(url)
                        if full_content:
                            result_data["content"] = full_content
                            content_count += 1 # 成功提取一篇正文
                            print(f"已提取 {content_count}/{max_content} 篇正文")
                        else:
                            print(f"未能获取 '{title}' 的正文内容。")

                    extract_data.append(result_data)
                    count += 1 # 只有成功提取标题和摘要才计数

            except Exception as e:
                print(f"处理单个结果时出错: {e}")
                continue

    except TimeoutException:
        print("页面加载超时")
    except Exception as e:
        print(f"搜索过程中出错: {e}")
    finally:
        if 'driver' in locals() and driver:
            driver.quit()
            print("浏览器已关闭。")

    return extract_data

# --- 主程序入口 ---
if __name__=="__main__":
    query = input("请输入搜索关键词: ")
    results = search(query)
    print("-" * 40)
    print(f"最终提取到 {len(results)} 条结果")
    print("-" * 40)
    
    # 保存结果到JSON文件
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = f"search_results_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"搜索结果已保存到 {output_file}")
    
    if results:
        # 为了更清晰地展示，只打印部分内容
        content_found = False
        for i, item in enumerate(results):
            print(f"\n--- 结果 {i+1} ---")
            print(f"标题: {item.get('title')}")
            print(f"摘要: {item.get('snippet')[:100]}...") # 打印部分摘要
            if 'content' in item:
                content_found = True
                print(f"正文 (部分): {item.get('content')[:150]}...") # 打印部分正文
                print("[正文内容已提取]")
        
        if not content_found:
            print("\n注意: 未能提取任何正文内容")
    else:
        print("未找到任何有效结果")
