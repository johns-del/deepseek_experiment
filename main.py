import os
import requests
import tkinter as tk
from tkinter import ttk
import threading
import ollama
import json
import re
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from urllib.parse import urljoin
from key_words_abstract import get_key_words
from web_crawler_server import search, get_full_content, is_readable_text, extract_text_with_selenium
from openai import OpenAI
api_keys=os.getenv("deepseek_api_key")
base_url="https://api.deepseek.com"

# 全局变量，用于跟踪是否启用联网搜索
enable_web_search = True

# 清理模型响应的函数
def clean_model_response(response_text):
    """
    清理模型响应，去除元数据但保留思考过程
    
    Args:
        response_text: 原始响应文本
        
    Returns:
        str: 清理后的响应文本
    """
    # 提取消息内容部分
    content_match = re.search(r"content='(.*?)', images=", response_text, re.DOTALL)
    if content_match:
        # 提取content字段内容并返回，保留思考过程
        content = content_match.group(1)
        return content.strip()
    else:
        # 如果无法匹配标准格式，尝试直接清理元数据
        result = re.sub(r'^model=.*?\n', '', response_text, flags=re.MULTILINE)
        result = re.sub(r'^created_at=.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^done=.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^done_reason=.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^total_duration=.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^load_duration=.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^prompt_eval.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^eval_.*?\n', '', result, flags=re.MULTILINE)
        result = re.sub(r'^message=.*?\n', '', result, flags=re.MULTILINE)
        
        # 保留思考过程，不再删除<think>标签
        return result.strip()

# 定义文本格式处理函数
def format_model_output(text_widget, text):
    """
    处理模型输出文本的格式，包括：
    1. 将\n转换为实际换行
    2. 将**文本**格式转换为加粗文本
    """
    # 先清理可能存在的旧标签
    text_widget.tag_delete("bold")
    
    # 创建加粗标签
    text_widget.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
    
    # 将可能存在的字面\n替换为实际换行
    text = text.replace("\\n", "\n")
    
    # 正则表达式查找**加粗文本**模式
    bold_pattern = r'\*\*(.*?)\*\*'
    
    # 添加文本并处理加粗格式
    last_end = 0
    for match in re.finditer(bold_pattern, text):
        # 添加加粗前的普通文本
        start, end = match.span()
        if start > last_end:
            text_widget.insert(tk.END, text[last_end:start])
        
        # 添加加粗文本
        bold_text = match.group(1)  # 提取**之间的文本
        bold_pos = text_widget.index(tk.END)
        text_widget.insert(tk.END, bold_text)
        # 计算文本结束位置
        end_pos = text_widget.index(tk.END)
        # 应用加粗标签
        text_widget.tag_add("bold", bold_pos, end_pos)
        
        last_end = end
    
    # 添加剩余文本
    if last_end < len(text):
        text_widget.insert(tk.END, text[last_end:])

def search_online(question):
    try:
        key_words=get_key_words(question)
        search_results=search(key_words)
        return search_results
    except Exception as e:
        print(f"联网搜索出错: {e}")
        return None

def toggle_search():
    global enable_web_search
    enable_web_search = not enable_web_search
    search_button.config(text="联网搜索：开启" if enable_web_search else "联网搜索：关闭")
    status_label.config(text=f"当前模式：{'联网搜索已开启' if enable_web_search else '仅使用本地模型'}")

def process_message(message):
    search_results = None
    if enable_web_search:
        display_text.config(state=tk.NORMAL)
        display_text.insert(tk.END, "正在联网搜索相关信息...\n")
        display_text.config(state=tk.DISABLED)
        display_text.see(tk.END)
        root.update()
        search_results = search_online(message)
    
    try:
        if search_results:
            # 将search_results列表转换为字符串
            if isinstance(search_results, list):
                formatted_results = ""
                for i, item in enumerate(search_results):
                    formatted_results += f"\n结果 {i+1}:\n"
                    if 'title' in item:
                        formatted_results += f"标题: {item['title']}\n"
                    if 'snippet' in item:
                        formatted_results += f"摘要: {item['snippet']}\n"
                    if 'content' in item:
                        # 限制正文长度，避免提示词过长
                        content = item['content']
                        if len(content) > 1000:
                            content = content[:1000] + "...(内容已截断)"
                        formatted_results += f"正文: {content}\n"
                    formatted_results += "\n"
            else:
                formatted_results = str(search_results)
                
            augmented_message = message + "\t" + "以下是联网搜索的结果，请你结合联网搜索的结果和你自身的记忆回答用户的问题，如果记忆和联网搜索有出入，请以联网搜索的结果为准，搜索结果为：" + formatted_results
        else:
            augmented_message = message
            
        # 使用ollama调用本地的deepseek-r1:7b来回答
        display_text.config(state=tk.NORMAL)
        display_text.insert(tk.END, "DeepSeek思考中...\n")
        display_text.config(state=tk.DISABLED)
        display_text.see(tk.END)
        root.update()
        
        try:
            # 调用模型API
            response = ollama.chat(model="deepseek-r1:7b", messages=[{"role":"user", "content":augmented_message}])
            
            # 添加调试信息
            print("API响应类型:", type(response))
            print("API响应内容:", response)
            
            # 检查响应格式并提取回答内容
            if isinstance(response, dict):
                if "response" in response:
                    model_response = response["response"]
                elif "message" in response and isinstance(response["message"], dict):
                    model_response = response["message"].get("content", str(response))
                else:
                    # 尝试查找可能的响应字段
                    model_response = str(response)
            else:
                model_response = str(response)
            
            # 清理模型响应
            model_response = clean_model_response(model_response)
            
            # 显示模型回答
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, "DeepSeek：")
            format_model_output(display_text, model_response)
            display_text.insert(tk.END, "\n\n")
            display_text.config(state=tk.DISABLED)
            
        except Exception as e:
            # 模型API调用失败，尝试备用方法
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"API调用出错：{str(e)}\n")
            display_text.insert(tk.END, "尝试使用备用方法获取响应...\n")
            
            try:
                # 备用方法：直接使用命令行调用ollama
                import subprocess
                cmd = ["ollama", "run", "deepseek-r1:7b", "-m", message]
                print(f"执行命令: {' '.join(cmd)}")
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
                
                if result.returncode == 0:
                    model_response = result.stdout.strip()
                    
                    # 清理模型响应
                    model_response = clean_model_response(model_response)
                    
                    display_text.insert(tk.END, "DeepSeek：")
                    format_model_output(display_text, model_response)
                    display_text.insert(tk.END, "\n\n")
                else:
                    display_text.insert(tk.END, f"命令行调用失败: {result.stderr}\n\n")
            except Exception as e2:
                display_text.insert(tk.END, f"备用方法也失败了: {str(e2)}\n\n")
            
            display_text.config(state=tk.DISABLED)
        
    except Exception as e:
        # 整个处理过程的异常处理
        display_text.config(state=tk.NORMAL)
        display_text.insert(tk.END, f"处理消息时出错：{str(e)}\n\n")
        display_text.config(state=tk.DISABLED)
    
    # 完成处理，滚动到最新消息
    display_text.see(tk.END)
    
    # 重新启用发送按钮和输入框
    input_field.config(state=tk.NORMAL)
    send_button.config(state=tk.NORMAL)
    status_label.config(text=f"当前模式：{'联网搜索已开启' if enable_web_search else '仅使用本地模型'}")

def send_message():
    message = input_field.get()
    if not message.strip():
        return
    
    # 禁用输入框和发送按钮，防止重复发送
    input_field.config(state=tk.DISABLED)
    send_button.config(state=tk.DISABLED)
    status_label.config(text="正在处理...")
    
    display_text.config(state=tk.NORMAL)
    display_text.insert(tk.END, "你：" + message + "\n")
    display_text.config(state=tk.DISABLED)
    display_text.see(tk.END)
    input_field.delete(0, tk.END)
    
    # 使用线程处理耗时操作，防止UI卡死
    threading.Thread(target=process_message, args=(message,), daemon=True).start()

# 创建一个tkinter窗口
root = tk.Tk()
root.title("DeepSeek问答系统")
root.geometry("1000x700")  # 设置一个更合理的窗口大小

# 创建主框架
main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill=tk.BOTH, expand=True)

# 创建状态栏
status_frame = ttk.Frame(main_frame, padding="5")
status_frame.pack(fill=tk.X, side=tk.TOP)

# 显示当前状态的标签
status_label = ttk.Label(status_frame, text="当前模式：联网搜索已开启")
status_label.pack(side=tk.LEFT)

# 联网搜索切换按钮
search_button = ttk.Button(status_frame, text="联网搜索：开启", command=toggle_search)
search_button.pack(side=tk.RIGHT)

# 创建显示区域
display_frame = ttk.Frame(main_frame)
display_frame.pack(fill=tk.BOTH, expand=True, pady=10)

# 创建一个显示文本的组件
display_text = tk.Text(display_frame, wrap=tk.WORD, state=tk.DISABLED)
display_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 创建一个滚动条
scrollbar = ttk.Scrollbar(display_frame, command=display_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# 将滚动条与显示文本组件关联
display_text.config(yscrollcommand=scrollbar.set)

# 创建输入区域
input_frame = ttk.Frame(main_frame)
input_frame.pack(fill=tk.X, side=tk.BOTTOM)

# 创建一个输入框
input_field = ttk.Entry(input_frame)
input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

# 创建一个发送按钮
send_button = ttk.Button(input_frame, text="发送", command=send_message)
send_button.pack(side=tk.RIGHT)

# 添加回车键发送消息的功能
root.bind('<Return>', lambda event: send_message())

# 初始欢迎消息
display_text.config(state=tk.NORMAL)
display_text.insert(tk.END, "DeepSeek：你好！我是DeepSeek助手，有什么可以帮到你的？\n\n")
display_text.config(state=tk.DISABLED)

# 启动主循环
root.mainloop()

