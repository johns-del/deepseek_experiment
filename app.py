import os
import json
import re
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
import ollama
from key_words_abstract import get_key_words
from web_crawler_server import search, get_search_title

# 创建Flask应用
app = Flask(__name__)
app.secret_key = os.urandom(24)  # 用于session加密

# 存储聊天历史的目录
HISTORY_DIR = "chat_history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# 清理模型响应的函数
def clean_model_response(response_text):
    """
    清理模型响应，去除元数据但保留思考过程
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
        
        # 保留思考过程
        return result.strip()

def search_online(question):
    """在线搜索相关信息"""
    try:
        key_words = get_key_words(question)
        search_results = search(key_words)
        return search_results
    except Exception as e:
        print(f"联网搜索出错: {e}")
        return None

def get_conversation_id():
    """获取当前会话ID，如果没有则创建一个新的"""
    if 'conversation_id' not in session:
        session['conversation_id'] = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return session['conversation_id']

def save_chat_history(conversation_id, user_message, bot_message, search_results=None):
    """保存聊天历史到本地文件"""
    history_file = os.path.join(HISTORY_DIR, f"{conversation_id}.json")
    
    # 获取现有历史记录
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
    else:
        history = []
    
    # 添加新消息
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_entry = {
        "timestamp": timestamp,
        "user": user_message,
        "bot": bot_message
    }
    
    if search_results:
        new_entry["search_results"] = search_results
        
    history.append(new_entry)
    
    # 保存更新后的历史记录
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_all_conversations():
    """获取所有会话列表"""
    conversations = []
    for filename in os.listdir(HISTORY_DIR):
        if filename.endswith('.json'):
            conv_id = filename.replace('.json', '')
            # 读取第一条消息作为会话标题
            try:
                with open(os.path.join(HISTORY_DIR, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data:
                        title = data[0]["user"][:20] + "..." if len(data[0]["user"]) > 20 else data[0]["user"]
                        timestamp = data[0]["timestamp"]
                    else:
                        title = "空会话"
                        timestamp = ""
                conversations.append({
                    "id": conv_id,
                    "title": title,
                    "timestamp": timestamp
                })
            except:
                continue
    
    # 按时间戳排序，最新的在前面
    conversations.sort(key=lambda x: x["timestamp"] if x["timestamp"] else "", reverse=True)
    return conversations

def get_chat_history(conversation_id):
    """获取特定会话的历史记录"""
    history_file = os.path.join(HISTORY_DIR, f"{conversation_id}.json")
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

@app.route('/')
def index():
    """渲染主页"""
    conversations = get_all_conversations()
    return render_template('index.html', conversations=conversations)

@app.route('/api/send', methods=['POST'])
def send_message():
    """处理用户发送的消息"""
    data = request.json
    message = data.get('message', '')
    enable_web_search = data.get('enable_web_search', True)
    return_search_progress = data.get('return_search_progress', False)
    conversation_id = get_conversation_id()
    
    if not message.strip():
        return jsonify({"error": "消息不能为空"}), 400
    
    # 如果客户端需要实时搜索进度，使用流式响应
    if return_search_progress and enable_web_search:
        return Response(
            stream_with_context(stream_search_and_response(message, conversation_id)),
            content_type='application/json'
        )
    
    # 否则使用传统响应方式
    # 联网搜索
    search_results = None
    formatted_results = None
    
    if enable_web_search:
        search_results = search_online(message)
        
        if isinstance(search_results, list):
            formatted_results = ""
            for i, item in enumerate(search_results):
                formatted_results += f"\n结果 {i+1}:\n"
                if 'title' in item:
                    formatted_results += f"标题: {item['title']}\n"
                if 'snippet' in item:
                    formatted_results += f"摘要: {item['snippet']}\n"
                if 'content' in item:
                    # 限制正文长度
                    content = item['content']
                    if len(content) > 1000:
                        content = content[:1000] + "...(内容已截断)"
                    formatted_results += f"正文: {content}\n"
                formatted_results += "\n"
        elif search_results:
            formatted_results = str(search_results)
    
    # 构建模型提示
    if formatted_results:
        augmented_message = message + "\t" + "以下是联网搜索的结果，请你结合联网搜索的结果和你自身的记忆回答用户的问题，如果记忆和联网搜索有出入，请以联网搜索的结果为准，搜索结果为：" + formatted_results
    else:
        augmented_message = message
    
    try:
        # 调用模型
        response = ollama.chat(model="deepseek-r1:7b", messages=[{"role": "user", "content": augmented_message}])
        
        if isinstance(response, dict):
            if "response" in response:
                model_response = response["response"]
            elif "message" in response and isinstance(response["message"], dict):
                model_response = response["message"].get("content", str(response))
            else:
                model_response = str(response)
        else:
            model_response = str(response)
        
        # 清理响应
        model_response = clean_model_response(model_response)
        
        # 保存历史记录
        save_chat_history(conversation_id, message, model_response, formatted_results)
        
        return jsonify({
            "response": model_response,
            "has_search_results": bool(formatted_results),
            "conversation_id": conversation_id
        })
        
    except Exception as e:
        print(f"调用模型出错: {e}")
        try:
            # 备用方法
            import subprocess
            cmd = ["ollama", "run", "deepseek-r1:7b", "-m", message]
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
            
            if result.returncode == 0:
                model_response = result.stdout.strip()
                model_response = clean_model_response(model_response)
                
                # 保存历史记录
                save_chat_history(conversation_id, message, model_response, formatted_results)
                
                return jsonify({
                    "response": model_response,
                    "has_search_results": bool(formatted_results),
                    "conversation_id": conversation_id
                })
            else:
                return jsonify({"error": f"命令行调用失败: {result.stderr}"}), 500
        except Exception as e2:
            return jsonify({"error": f"所有尝试都失败了: {str(e)} 和 {str(e2)}"}), 500

def stream_search_and_response(message, conversation_id):
    """流式生成搜索进度和最终响应"""
    try:
        key_words = get_key_words(message)
        
        # 先发送初始搜索标题
        initial_title = f"{key_words}_搜索中..."
        yield json.dumps({"type": "search_progress", "title": initial_title}) + '\n'
        
        # 启动搜索并实时获取搜索标题
        search_titles = get_search_title(key_words)
        
        # 同时进行搜索获取正文内容
        search_results = search(key_words)
        formatted_results = ""
        
        # 逐个生成标题更新
        for title in search_titles:
            yield json.dumps({"type": "search_progress", "title": title}) + '\n'
            time.sleep(0.5)  # 适当间隔，不要太频繁
        
        # 处理搜索结果
        if isinstance(search_results, list):
            formatted_results = ""
            for i, item in enumerate(search_results):
                formatted_results += f"\n结果 {i+1}:\n"
                if 'title' in item:
                    formatted_results += f"标题: {item['title']}\n"
                    # 发送最后的结果标题
                    if i == 0:  # 只发送第一个结果的标题作为最终标题
                        yield json.dumps({"type": "search_progress", "title": item['title']}) + '\n'
                if 'snippet' in item:
                    formatted_results += f"摘要: {item['snippet']}\n"
                if 'content' in item:
                    # 限制正文长度
                    content = item['content']
                    if len(content) > 1000:
                        content = content[:1000] + "...(内容已截断)"
                    formatted_results += f"正文: {content}\n"
                formatted_results += "\n"
        elif search_results:
            formatted_results = str(search_results)
        
        # 构建模型提示
        if formatted_results:
            augmented_message = message + "\t" + "以下是联网搜索的结果，请你结合联网搜索的结果和你自身的记忆回答用户的问题，如果记忆和联网搜索有出入，请以联网搜索的结果为准，搜索结果为：" + formatted_results
        else:
            augmented_message = message
        
        # 调用模型
        response = ollama.chat(model="deepseek-r1:7b", messages=[{"role": "user", "content": augmented_message}])
        
        if isinstance(response, dict):
            if "response" in response:
                model_response = response["response"]
            elif "message" in response and isinstance(response["message"], dict):
                model_response = response["message"].get("content", str(response))
            else:
                model_response = str(response)
        else:
            model_response = str(response)
        
        # 清理响应
        model_response = clean_model_response(model_response)
        
        # 保存历史记录
        save_chat_history(conversation_id, message, model_response, formatted_results)
        
        # 发送最终响应
        yield json.dumps({
            "type": "final_response",
            "response": model_response,
            "has_search_results": bool(formatted_results),
            "conversation_id": conversation_id
        }) + '\n'
        
    except Exception as e:
        print(f"流式响应出错: {e}")
        yield json.dumps({"type": "error", "error": str(e)}) + '\n'

@app.route('/api/history')
def get_history():
    """获取历史会话列表"""
    conversations = get_all_conversations()
    return jsonify(conversations)

@app.route('/api/history/<conversation_id>')
def get_conversation(conversation_id):
    """获取特定会话的历史记录"""
    history = get_chat_history(conversation_id)
    return jsonify(history)

@app.route('/api/new')
def new_conversation():
    """创建新会话"""
    session.pop('conversation_id', None)
    return jsonify({"conversation_id": get_conversation_id()})

@app.route('/api/toggle-search', methods=['POST'])
def toggle_search():
    """切换联网搜索状态"""
    data = request.json
    enable_web_search = data.get('enable_web_search', True)
    return jsonify({"enable_web_search": enable_web_search})

if __name__ == '__main__':
    app.run(debug=True) 