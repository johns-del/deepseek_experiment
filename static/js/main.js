// 全局变量
let enableWebSearch = true;
let currentConversationId = null;
let isProcessing = false;
let searchAnimation = null; // 用于存储Lottie动画实例

// DOM元素
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatContainer = document.getElementById('chat-container');
const searchToggleBtn = document.getElementById('search-toggle-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const historyList = document.getElementById('history-list');

// 初始化页面
document.addEventListener('DOMContentLoaded', () => {
    // 加载Lottie动画库
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.11.0/lottie.min.js', () => {
        console.log('Lottie库加载完成');
    });
    
    // 自动调整输入框高度
    userInput.addEventListener('input', autoResizeTextarea);
    
    // 监听发送按钮点击
    sendBtn.addEventListener('click', sendMessage);
    
    // 监听回车键发送消息
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // 监听搜索开关
    searchToggleBtn.addEventListener('change', () => {
        enableWebSearch = searchToggleBtn.checked;
        
        // 发送切换请求到服务器
        fetch('/api/toggle-search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ enable_web_search: enableWebSearch }),
        });
    });
    
    // 监听新建会话按钮
    newChatBtn.addEventListener('click', createNewChat);
    
    // 监听历史会话点击
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            loadConversation(item.dataset.id);
        });
    });
    
    // 自动聚焦输入框
    userInput.focus();
});

// 加载外部JS脚本
function loadScript(url, callback) {
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = url;
    script.onload = callback;
    document.head.appendChild(script);
}

// 发送消息
async function sendMessage() {
    const message = userInput.value.trim();
    
    if (!message || isProcessing) {
        return;
    }
    
    // 添加用户消息到聊天界面
    addMessage(message, 'user');
    
    // 清空输入框并重置大小
    userInput.value = '';
    userInput.style.height = 'auto';
    
    // 添加动画加载指示器
    const loadingElement = addAnimatedLoadingIndicator(message);
    
    // 设置处理状态
    isProcessing = true;
    sendBtn.disabled = true;
    
    try {
        // 发送请求到服务器
        const response = await fetch('/api/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                enable_web_search: enableWebSearch,
                return_search_progress: true  // 请求服务器返回搜索进度和标题
            }),
        });
        
        // 处理响应
        if (response.ok) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            // 循环读取响应流
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                
                try {
                    // 尝试解析JSON响应
                    const data = JSON.parse(chunk);
                    
                    // 如果是搜索进度更新
                    if (data.type === 'search_progress' && data.title) {
                        updateSearchText(data.title);
                    } 
                    // 如果是最终回复
                    else if (data.type === 'final_response') {
                        // 移除加载指示器
                        if (loadingElement) {
                            loadingElement.remove();
                            if (searchAnimation) {
                                searchAnimation.destroy();
                                searchAnimation = null;
                            }
                        }
                        
                        // 添加机器人回复
                        addMessage(data.response, 'bot', data.has_search_results);
                        
                        // 更新当前会话ID
                        if (data.conversation_id) {
                            currentConversationId = data.conversation_id;
                            updateHistoryList();
                        }
                    }
                } catch (e) {
                    // 如果不是JSON，可能是其他格式的响应
                    console.error('解析响应时出错:', e);
                }
            }
        } else {
            // 处理错误响应
            const data = await response.json();
            
            // 移除加载指示器
            if (loadingElement) {
                loadingElement.remove();
                if (searchAnimation) {
                    searchAnimation.destroy();
                    searchAnimation = null;
                }
            }
            
            addErrorMessage(data.error || '服务器错误，请稍后再试');
        }
    } catch (error) {
        // 移除加载指示器
        if (loadingElement) {
            loadingElement.remove();
            if (searchAnimation) {
                searchAnimation.destroy();
                searchAnimation = null;
            }
        }
        
        addErrorMessage('网络错误，请检查您的连接');
        console.error('发送消息时出错:', error);
    } finally {
        // 重置处理状态
        isProcessing = false;
        sendBtn.disabled = false;
        userInput.focus();
        
        // 清除定时器
        if (window.searchUpdateTimer) {
            clearInterval(window.searchUpdateTimer);
            window.searchUpdateTimer = null;
        }
    }
}

// 更新搜索文本
function updateSearchText(title) {
    const searchTextElement = document.getElementById('search-text-content');
    if (searchTextElement) {
        searchTextElement.innerHTML = `正在搜索：<span class="search-query">"${title}"</span>`;
    }
}

// 添加消息到聊天界面
function addMessage(content, sender, hasSearchResults = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    
    if (sender === 'user') {
        avatarDiv.textContent = '你';
    } else {
        const avatarImg = document.createElement('img');
        avatarImg.src = '/static/images/bot-avatar.png';
        avatarImg.alt = 'DeepSeek';
        avatarDiv.appendChild(avatarImg);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // 如果是机器人回复且有搜索结果，添加搜索标志
    if (sender === 'bot' && hasSearchResults) {
        const searchBadge = document.createElement('div');
        searchBadge.className = 'search-badge';
        searchBadge.textContent = '联网搜索';
        contentDiv.appendChild(searchBadge);
    }
    
    // 处理思考过程
    if (sender === 'bot' && content.includes('<think>')) {
        // 提取思考过程
        const thinkMatches = content.match(/<think>([\s\S]*?)<\/think>/);
        
        if (thinkMatches && thinkMatches[1]) {
            const thinkContent = thinkMatches[1].trim();
            const thinkDiv = document.createElement('div');
            thinkDiv.className = 'thinking-process';
            thinkDiv.innerHTML = formatThinkingContent(thinkContent);
            contentDiv.appendChild(thinkDiv);
            
            // 移除思考过程，处理剩余内容
            content = content.replace(/<think>[\s\S]*?<\/think>/, '').trim();
        }
    }
    
    // 使用marked.js格式化Markdown内容
    const formattedContent = formatMessageContent(content);
    contentDiv.innerHTML += formattedContent;
    
    // 添加语法高亮
    contentDiv.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightBlock(block);
    });
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    chatContainer.appendChild(messageDiv);
    
    // 滚动到最新消息
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 格式化思考内容
function formatThinkingContent(content) {
    // 识别并处理\n字面字符
    content = content.replace(/\\n/g, '\n');
    
    // 配置marked.js针对思考内容
    marked.setOptions({
        breaks: true,
        gfm: true
    });
    
    // 使用marked解析Markdown
    try {
        return marked.parse(content);
    } catch (e) {
        // 退回到基本的HTML格式化
        return content.replace(/\n/g, '<br>');
    }
}

// 格式化消息内容，处理Markdown和加粗文本
function formatMessageContent(content) {
    // 处理\n字面字符
    content = content.replace(/\\n/g, '\n');
    
    // 配置marked.js选项
    marked.setOptions({
        breaks: true,        // 允许换行符转换为<br>
        gfm: true,           // 使用GitHub风格的Markdown
        smartLists: true,    // 使用更智能的列表行为
        smartypants: true,   // 使用更智能的标点符号
        headerIds: false,    // 不添加id到标题元素
        mangle: false,       // 不转义链接文本中的HTML
        pedantic: false,     // 不使用严格的Markdown规范
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(lang, code).value;
                } catch (e) {
                    console.error('高亮显示错误:', e);
                }
            }
            return hljs.highlightAuto(code).value;
        }
    });
    
    // 尝试使用marked处理Markdown
    try {
        const parsed = marked.parse(content);
        return parsed;
    } catch (e) {
        console.error('解析Markdown出错:', e);
        // 如果marked解析失败，确保换行符被正确处理
        return `<p>${content.replace(/\n/g, '<br>')}</p>`;
    }
}

// 添加动画加载指示器
function addAnimatedLoadingIndicator(queryText) {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot-message loading-indicator';
    loadingDiv.id = 'current-loading-indicator';
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    
    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/images/bot-avatar.png';
    avatarImg.alt = 'DeepSeek';
    avatarDiv.appendChild(avatarImg);
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // 搜索标记
    if (enableWebSearch) {
        const searchBadge = document.createElement('div');
        searchBadge.className = 'search-badge';
        searchBadge.textContent = '联网搜索';
        contentDiv.appendChild(searchBadge);
    }
    
    // 创建搜索动画和文本的容器，使它们水平排列
    const searchContainer = document.createElement('div');
    searchContainer.className = 'search-container';
    contentDiv.appendChild(searchContainer);
    
    // 动画容器
    const animContainer = document.createElement('div');
    animContainer.className = 'lottie-search-animation';
    animContainer.style.width = '60px';
    animContainer.style.height = '60px';
    searchContainer.appendChild(animContainer);
    
    // 显示搜索查询文本
    const searchTextDiv = document.createElement('div');
    searchTextDiv.className = 'search-text';
    searchTextDiv.id = 'search-text-content';
    searchTextDiv.innerHTML = `正在${enableWebSearch ? '搜索' : '思考'}：<span class="search-query">"${queryText.substring(0, 50)}${queryText.length > 50 ? '...' : ''}"</span>`;
    searchContainer.appendChild(searchTextDiv);
    
    loadingDiv.appendChild(avatarDiv);
    loadingDiv.appendChild(contentDiv);
    chatContainer.appendChild(loadingDiv);
    
    // 滚动到最新消息
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // 如果Lottie已加载，初始化动画
    if (window.lottie) {
        initSearchAnimation(animContainer, enableWebSearch);
    } else {
        // 如果Lottie未加载，使用传统加载动画作为后备方案
        const loadingDots = document.createElement('div');
        loadingDots.className = 'loading-dots';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            loadingDots.appendChild(dot);
        }
        
        animContainer.appendChild(loadingDots);
    }
    
    // 模拟搜索结果（当后端未实现时临时使用）
    if (enableWebSearch) {
        simulateSearchTitles(queryText);
    }
    
    return loadingDiv;
}

// 模拟搜索内容动态更新（临时方案，当后端不支持实时返回搜索标题时使用）
function simulateSearchTitles(originalQuery) {
    // 模拟可能的搜索结果标题
    const searchTitles = [
        `${originalQuery}_百度搜索`,
        `${originalQuery} - 知乎`,
        `${originalQuery}的相关资料_维基百科`,
        `关于${originalQuery}的最新研究_科学网`,
        `${originalQuery}详细解析_百度百科`
    ];
    
    let currentIndex = 0;
    
    // 更新搜索文本的函数
    function updateSimulatedText() {
        updateSearchText(searchTitles[currentIndex]);
        currentIndex = (currentIndex + 1) % searchTitles.length;
    }
    
    // 设置定时器，每3秒更新一次搜索内容
    const searchUpdateTimer = setInterval(updateSimulatedText, 3000);
    
    // 存储定时器ID，以便在需要时清除
    window.searchUpdateTimer = searchUpdateTimer;
    
    // 首次延迟1秒后开始更新，给用户一个缓冲时间看到原始查询
    setTimeout(updateSimulatedText, 1000);
}

// 初始化搜索动画
function initSearchAnimation(container, isSearch) {
    // 选择合适的动画
    const animationUrl = isSearch 
        ? 'https://assets7.lottiefiles.com/packages/lf20_t9gkkhz4.json'  // 搜索动画
        : 'https://assets10.lottiefiles.com/packages/lf20_kk62um5d.json'; // 思考动画
    
    try {
        searchAnimation = lottie.loadAnimation({
            container: container,
            renderer: 'svg',
            loop: true,
            autoplay: true,
            path: animationUrl,
            rendererSettings: {
                progressiveLoad: true,
                preserveAspectRatio: 'xMidYMid slice'
            }
        });
        
        // 动画加载错误处理
        searchAnimation.addEventListener('data_failed', () => {
            console.error('Lottie动画加载失败，使用备用动画');
            createFallbackAnimation(container);
        });
    } catch (error) {
        console.error('初始化Lottie动画时出错:', error);
        createFallbackAnimation(container);
    }
}

// 创建备用动画
function createFallbackAnimation(container) {
    container.innerHTML = '';
    const loadingDots = document.createElement('div');
    loadingDots.className = 'loading-dots';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('span');
        loadingDots.appendChild(dot);
    }
    
    container.appendChild(loadingDots);
}

// 添加错误消息
function addErrorMessage(errorText) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message bot-message';
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    
    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/images/bot-avatar.png';
    avatarImg.alt = 'DeepSeek';
    avatarDiv.appendChild(avatarImg);
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p style="color: #e53e3e;">${errorText}</p>`;
    
    errorDiv.appendChild(avatarDiv);
    errorDiv.appendChild(contentDiv);
    
    chatContainer.appendChild(errorDiv);
    
    // 滚动到最新消息
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 自动调整输入框高度
function autoResizeTextarea() {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
}

// 创建新会话
async function createNewChat() {
    try {
        const response = await fetch('/api/new');
        const data = await response.json();
        
        if (data.conversation_id) {
            // 清空聊天界面，只保留欢迎消息
            while (chatContainer.childElementCount > 1) {
                chatContainer.removeChild(chatContainer.lastChild);
            }
            
            // 更新当前会话ID
            currentConversationId = data.conversation_id;
            
            // 更新历史列表
            updateHistoryList();
            
            // 重置输入框
            userInput.value = '';
            userInput.style.height = 'auto';
            userInput.focus();
        }
    } catch (error) {
        console.error('创建新会话时出错:', error);
    }
}

// 加载会话历史
async function loadConversation(conversationId) {
    if (isProcessing) {
        return;
    }
    
    try {
        // 获取会话历史
        const response = await fetch(`/api/history/${conversationId}`);
        const history = await response.json();
        
        if (history.length > 0) {
            // 清空聊天界面，保留欢迎消息
            while (chatContainer.childElementCount > 1) {
                chatContainer.removeChild(chatContainer.lastChild);
            }
            
            // 加载历史消息
            history.forEach(item => {
                addMessage(item.user, 'user');
                addMessage(item.bot, 'bot', item.search_results ? true : false);
            });
            
            // 更新当前会话ID
            currentConversationId = conversationId;
            
            // 更新历史列表中的活动项
            updateActiveHistoryItem(conversationId);
            
            // 重置输入框
            userInput.value = '';
            userInput.style.height = 'auto';
            userInput.focus();
        }
    } catch (error) {
        console.error('加载会话历史时出错:', error);
    }
}

// 更新历史列表
async function updateHistoryList() {
    try {
        const response = await fetch('/api/history');
        const conversations = await response.json();
        
        // 清空历史列表
        historyList.innerHTML = '';
        
        // 添加历史会话
        conversations.forEach(conv => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            historyItem.dataset.id = conv.id;
            
            if (conv.id === currentConversationId) {
                historyItem.classList.add('active');
            }
            
            historyItem.innerHTML = `
                <i class="fas fa-comments"></i>
                <span class="history-title">${conv.title}</span>
                <span class="history-date">${conv.timestamp ? conv.timestamp.split(' ')[0] : ''}</span>
            `;
            
            historyItem.addEventListener('click', () => {
                loadConversation(conv.id);
            });
            
            historyList.appendChild(historyItem);
        });
    } catch (error) {
        console.error('更新历史列表时出错:', error);
    }
}

// 更新活动历史项
function updateActiveHistoryItem(conversationId) {
    // 移除所有活动状态
    document.querySelectorAll('.history-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // 添加活动状态到当前项
    const currentItem = document.querySelector(`.history-item[data-id="${conversationId}"]`);
    if (currentItem) {
        currentItem.classList.add('active');
    }
} 