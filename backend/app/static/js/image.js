// 检查登录状态
(function() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
    }
})();

console.log('image.js 已加载');

// 调试日志存储
const debugLogs = [];
let debugPanelVisible = false;

// 翻译功能
async function doTranslate() {
    const input = document.getElementById('promptInput');
    const btn = document.getElementById('translateBtn');
    const text = input.value.trim();
    if (!text) return;

    btn.disabled = true;
    const origHTML = btn.innerHTML;
    btn.innerHTML = '<svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="3" class="opacity-25"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" class="opacity-75"/></svg>';

    const token = localStorage.getItem('token') || '';
    try {
        const response = await fetch('/api/v1/image/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({ text: text }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || '翻译失败');
        }

        const data = await response.json();
        input.value = data.translated;
        input.focus();

    } catch (e) {
        alert('翻译失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHTML;
    }
}

// 初始化用户信息
(function initUserInfo() {
    const u = localStorage.getItem('username') || '用户';
    const r = localStorage.getItem('role') || 'employee';
    document.getElementById('displayUsername').textContent = u;
    document.getElementById('avatarLetter').textContent = u.charAt(0).toUpperCase();
    document.getElementById('menuUsername').textContent = u;
    document.getElementById('menuRole').textContent = r === 'hr' ? 'HR 管理员' : r === 'boss' ? '超级管理员' : '普通员工';
})();

// 调试窗口功能
function addDebugLog(taskId, data, status) {
    const timestamp = new Date().toLocaleString('zh-CN');
    const log = {
        id: Date.now(),
        taskId: taskId,
        data: data,
        status: status,
        timestamp: timestamp
    };

    debugLogs.unshift(log);
    updateDebugPanel();

    if (!debugPanelVisible) {
        showDebugPanel();
    }
}

function updateDebugPanel() {
    const debugContent = document.getElementById('debugContent');
    const debugCount = document.getElementById('debugCount');

    if (!debugContent) return;

    debugCount.textContent = debugLogs.length;

    if (debugLogs.length === 0) {
        debugContent.innerHTML = '<div class="text-xs text-slate-400 text-center py-8">暂无调试记录</div>';
        return;
    }

    debugContent.innerHTML = debugLogs.map(log => {
        const statusClass = `debug-status-${log.status}`;
        const statusInfo = statusMap[log.status] || { icon: '', text: '未知' };

        return `
            <div class="debug-log-item">
                <div class="debug-log-header">
                    <div class="debug-log-status">
                        <span class="text-xs px-2 py-0.5 rounded ${statusClass}">
                            ${statusInfo.icon} ${statusInfo.text}
                        </span>
                        <span class="text-xs text-slate-600 ml-2">任务 ID: ${log.taskId.substring(0, 8)}...</span>
                    </div>
                    <span class="debug-log-time">${log.timestamp}</span>
                </div>
                <div class="debug-log-json">${JSON.stringify(log.data, null, 2)}</div>
            </div>
        `;
    }).join('');
}

function showDebugPanel() {
    const panel = document.getElementById('debugPanel');
    if (panel) {
        panel.classList.remove('hidden');
        debugPanelVisible = true;
    }
}

function toggleDebugPanel() {
    const panel = document.getElementById('debugPanel');
    if (panel) {
        panel.classList.toggle('hidden');
        debugPanelVisible = !panel.classList.contains('hidden');
    }
}

function clearDebugLogs() {
    debugLogs.length = 0;
    updateDebugPanel();
}

// 用户菜单
function toggleUserMenu() {
    const m = document.getElementById('userMenu');
    m.classList.toggle('hidden');
    if (!m.classList.contains('hidden')) {
        document.addEventListener('click', function f(e) {
            if (!e.target.closest('#userDropdown')) {
                m.classList.add('hidden');
                document.removeEventListener('click', f);
            }
        });
    }
}

// 退出登录
async function handleLogout() {
    try {
        const t = localStorage.getItem('token');
        if (t) await fetch('/api/v1/logout', { method: 'POST', headers: { 'Authorization': 'Bearer ' + t } });
    } catch (e) {}
    localStorage.clear();
    window.location.href = '/login';
}

// 高级选项切换
let advancedVisible = false;
function toggleAdvanced() {
    advancedVisible = !advancedVisible;
    const el = document.getElementById('advancedOptions');
    if (advancedVisible) {
        el.classList.remove('hidden');
    } else {
        el.classList.add('hidden');
    }
}

// 填充提示词
function fillPrompt(text) {
    const input = document.getElementById('promptInput');
    if (input && !input.disabled) {
        input.value = text;
        input.focus();
    }
}

// 任务状态映射
const statusMap = {
    'pending': { text: '排队中', icon: '⏳', color: 'text-slate-500', bg: 'bg-slate-50' },
    'processing': { text: '生成中', icon: '🔄', color: 'text-emerald-500', bg: 'bg-emerald-50' },
    'completed': { text: '已完成', icon: '✅', color: 'text-emerald-500', bg: 'bg-emerald-50' },
    'failed': { text: '失败', icon: '❌', color: 'text-red-500', bg: 'bg-red-50' },
};

// 尺寸选项显示映射
const sizeLabels = {
    '1024x1024': '1024x1024 正方形',
    '1024x1536': '1024x1536 竖版',
    '1536x1024': '1536x1024 横版',
    '2000x1000': '2000x1000 宽屏',
    '1000x2000': '1000x2000 竖屏',
    '2000x667': '2000x667 超宽',
    '667x2000': '667x2000 超高',
};

// 活跃任务
const activeTasks = {};

// 生成图片
async function handleGenerate() {
    const prompt = document.getElementById('promptInput').value.trim();
    if (!prompt) {
        alert('请输入提示词');
        return;
    }

    const token = localStorage.getItem('token') || '';
    const generateBtn = document.getElementById('generateBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span>⏳ 提交中...</span>';

    const size = document.getElementById('sizeSelect').value;
    const quality = document.getElementById('qualitySelect').value;
    const n = parseInt(document.getElementById('nSelect').value);
    const thinking = document.getElementById('thinkingSelect').value;
    const background = document.getElementById('backgroundSelect').value;
    const seed = parseInt(document.getElementById('seedInput').value) || -1;

    // 构建请求体
    const reqBody = {
        prompt: prompt,
        size: size,
        quality: quality,
        n: n,
        thinking: thinking,
        background: background,
        seed: seed,
    };

    try {
        const response = await fetch('/api/v1/image/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify(reqBody),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP 错误！状态码: ${response.status}`);
        }

        const data = await response.json();
        const taskId = data.task_id;

        // 创建任务卡片
        createTaskCard(taskId, prompt, size, quality, n);

        // 开始轮询状态
        startPolling(taskId, prompt, size, quality, n);

        // 清空输入
        document.getElementById('promptInput').value = '';

    } catch (error) {
        console.error('提交任务失败:', error);
        alert('提交任务失败: ' + error.message);
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<span>✨ 生成</span>';
    }
}

// 创建任务卡片
function createTaskCard(taskId, prompt, size, quality, n) {
    const container = document.getElementById('resultsList');
    const card = document.createElement('div');
    card.id = `task-${taskId}`;
    card.className = 'bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden';
    card.innerHTML = `
        <div class="p-5">
            <div class="flex items-start justify-between mb-3">
                <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-2">
                        <span class="status-icon text-lg">⏳</span>
                        <span class="status-text text-sm font-medium text-slate-500">排队中</span>
                    </div>
                    <p class="task-prompt text-sm text-slate-700 leading-relaxed">${prompt}</p>
                </div>
                <button onclick="deleteTask('${taskId}')" class="text-slate-400 hover:text-red-500 p-1 rounded transition-colors" title="删除任务">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
            </div>
            <div class="flex items-center space-x-3 text-xs text-slate-400 mb-3">
                <span>📐 ${sizeLabels[size] || size}</span>
                <span>🎨 ${quality}</span>
                <span>📸 ${n}张</span>
                <span class="task-time text-xs"></span>
            </div>
            <div class="task-progress hidden">
                <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                    <div class="progress-bar bg-emerald-500 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                </div>
                <p class="text-xs text-slate-400 mt-2 text-center">🎨 AI 正在为您生成图片，请稍候（约 30秒-3分钟）...</p>
            </div>
            <div class="task-result hidden mt-4">
                <!-- 图片结果将在这里显示 -->
            </div>
            <div class="task-error hidden mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p class="text-xs text-red-600 error-message"></p>
            </div>
        </div>
    `;

    container.insertBefore(card, container.firstChild);

    activeTasks[taskId] = {
        prompt: prompt,
        size: size,
        quality: quality,
        n: n,
        polling: false,
    };
}

// 轮询任务状态
function startPolling(taskId, prompt, size, quality, n) {
    const token = localStorage.getItem('token') || '';
    const card = document.getElementById(`task-${taskId}`);
    if (!card) return;

    const progressBar = card.querySelector('.progress-bar');
    const taskProgress = card.querySelector('.task-progress');
    let progress = 0;

    // 显示进度条
    taskProgress.classList.remove('hidden');

    // 模拟进度动画
    const progressTimer = setInterval(() => {
        progress = Math.min(progress + Math.random() * 5, 90);
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
    }, 2000);

    // 开始轮询
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/v1/image/status/${taskId}`, {
                headers: { 'Authorization': 'Bearer ' + token },
            });

            if (!response.ok) {
                throw new Error(`HTTP 错误！状态码：${response.status}`);
            }

            const data = await response.json();
            const status = data.status;

            addDebugLog(taskId, data, status);
            updateTaskStatus(card, status, data);

            // 如果有原始中文 prompt，显示双语
            if (data.original_prompt) {
                const promptEl = card.querySelector('.task-prompt');
                if (promptEl) {
                    promptEl.innerHTML = `
                        <span class="prompt-highlight">${escapeHtml(data.prompt || '')}</span>
                        <span class="block text-xs text-slate-400 mt-1">原文：${escapeHtml(data.original_prompt)}</span>
                    `;
                }
            }

            if (status === 'completed') {
                clearInterval(pollInterval);
                clearInterval(progressTimer);
                showImageResult(card, data);
                loadHistory();
            } else if (status === 'failed') {
                clearInterval(pollInterval);
                clearInterval(progressTimer);
                showError(card, data.error_message);
                loadHistory();
            }

        } catch (error) {
            console.error('轮询状态失败:', error);
            addDebugLog(taskId, { error: error.message, status: 'error' }, 'failed');
            clearInterval(pollInterval);
            clearInterval(progressTimer);
            showError(card, '网络请求失败，请稍后重试');
        }
    }, 3000);

    activeTasks[taskId].polling = pollInterval;
}

// 更新任务状态
function updateTaskStatus(card, status) {
    const statusInfo = statusMap[status] || statusMap['pending'];
    const statusIcon = card.querySelector('.status-icon');
    const statusText = card.querySelector('.status-text');

    if (statusIcon) statusIcon.textContent = statusInfo.icon;
    if (statusText) {
        statusText.textContent = statusInfo.text;
        statusText.className = `status-text text-sm font-medium ${statusInfo.color}`;
    }
}

// 显示图片结果
function showImageResult(card, data) {
    const taskProgress = card.querySelector('.task-progress');
    const taskResult = card.querySelector('.task-result');

    taskProgress.classList.add('hidden');
    taskResult.classList.remove('hidden');

    const paths = data.image_paths || [];
    if (paths.length === 0) {
        taskResult.innerHTML = `
            <div class="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                <p class="text-sm text-emerald-600">✅ 图片生成完成！</p>
                <p class="text-xs text-emerald-500 mt-1">但未获取到图片路径</p>
            </div>
        `;
        return;
    }

    // 根据图片数量决定网格列数
    const gridCols = paths.length === 1 ? 'grid-cols-1' : paths.length === 2 ? 'grid-cols-2' : 'grid-cols-2';

    const imagesHtml = paths.map((path, i) => `
        <div class="image-result-item border border-slate-200 rounded-xl overflow-hidden bg-slate-900">
            <img src="${path}?t=${Date.now()}" alt="生成的图片 ${i+1}" class="w-full h-auto object-contain" loading="lazy" onclick="openLightbox('${path}')" style="cursor: pointer;">
        </div>
    `).join('');

    const downloadButtons = paths.map((path, i) => `
        <a href="${path}" download class="inline-flex items-center space-x-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-lg transition-colors cursor-pointer">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
            <span>下载${paths.length > 1 ? ' #'+(i+1) : ''}</span>
        </a>
    `).join('');

    const editButtons = paths.map((path, i) => `
        <a href="/image-edit?src=${encodeURIComponent(path)}" class="inline-flex items-center space-x-1 text-xs bg-orange-600 hover:bg-orange-700 text-white px-3 py-1.5 rounded-lg transition-colors cursor-pointer">
            <span>✏️ 微调${paths.length > 1 ? ' #'+(i+1) : ''}</span>
        </a>
    `).join('');

    taskResult.innerHTML = `
        <div class="grid ${gridCols} gap-3">
            ${imagesHtml}
        </div>
        <div class="flex flex-wrap items-center gap-2 mt-3">
            ${downloadButtons}
            ${editButtons}
            <button onclick="copyPrompt('${escapeHtml(data.prompt || '')}')" class="inline-flex items-center space-x-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-lg transition-colors cursor-pointer">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>
                <span>复制提示词</span>
            </button>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 灯箱预览
function openLightbox(src) {
    const existing = document.getElementById('lightbox');
    if (existing) existing.remove();

    const lb = document.createElement('div');
    lb.id = 'lightbox';
    lb.className = 'fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-8';
    lb.innerHTML = `
        <button onclick="closeLightbox()" class="absolute top-4 right-4 text-white/80 hover:text-white text-2xl cursor-pointer">&times;</button>
        <img src="${src}" class="max-w-full max-h-full object-contain rounded-lg shadow-2xl" onclick="event.stopPropagation()">
    `;
    lb.addEventListener('click', closeLightbox);
    document.body.appendChild(lb);
}

function closeLightbox() {
    const lb = document.getElementById('lightbox');
    if (lb) lb.remove();
}

// 显示错误
function showError(card, errorMessage) {
    const taskProgress = card.querySelector('.task-progress');
    const taskError = card.querySelector('.task-error');
    const errorMessageEl = card.querySelector('.error-message');

    taskProgress.classList.add('hidden');
    taskError.classList.remove('hidden');
    errorMessageEl.textContent = errorMessage || '未知错误';
}

// 删除任务
async function deleteTask(taskId) {
    if (!confirm('确定要删除这个任务吗？')) return;

    const token = localStorage.getItem('token') || '';

    try {
        const response = await fetch(`/api/v1/image/${taskId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token },
        });

        if (response.ok) {
            const card = document.getElementById(`task-${taskId}`);
            if (card) card.remove();

            if (activeTasks[taskId] && activeTasks[taskId].polling) {
                clearInterval(activeTasks[taskId].polling);
            }
            delete activeTasks[taskId];

            loadHistory();
        } else {
            alert('删除失败，请稍后重试');
        }
    } catch (error) {
        console.error('删除任务失败:', error);
        alert('删除失败，请稍后重试');
    }
}

// 复制提示词
function copyPrompt(prompt) {
    navigator.clipboard.writeText(prompt).then(() => {
        const btn = event.target.closest('button');
        if (btn) {
            const span = btn.querySelector('span');
            const orig = span.textContent;
            span.textContent = '已复制!';
            setTimeout(() => { span.textContent = orig; }, 1500);
        }
    }).catch(err => {
        console.error('复制失败:', err);
    });
}

// 加载历史记录
async function loadHistory() {
    const token = localStorage.getItem('token') || '';

    try {
        const response = await fetch('/api/v1/image/history?limit=10', {
            headers: { 'Authorization': 'Bearer ' + token },
        });

        if (!response.ok) return;

        const data = await response.json();
        const historyList = document.getElementById('historyList');

        if (!data.tasks || data.tasks.length === 0) {
            historyList.innerHTML = '<div class="text-xs text-slate-400 text-center py-4">暂无历史记录</div>';
            return;
        }

        historyList.innerHTML = data.tasks.map(task => {
            const statusInfo = statusMap[task.status] || statusMap['pending'];
            const time = task.created_at ? new Date(task.created_at).toLocaleString('zh-CN') : '';
            const previewImg = task.image_paths && task.image_paths.length > 0
                ? `<img src="${task.image_paths[0]}" class="w-full h-20 object-cover rounded mt-1" alt="">`
                : '';
            return `
                <div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200/60 hover:border-emerald-300 transition-colors cursor-pointer" onclick="scrollToTask('${task.task_id}')">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs">${statusInfo.icon} <span class="${statusInfo.color}">${statusInfo.text}</span></span>
                        <span class="text-[10px] text-slate-400">${time}</span>
                    </div>
                    <p class="text-xs text-slate-600 truncate">${task.prompt}</p>
                    ${previewImg}
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('加载历史失败:', error);
    }
}

// 滚动到任务卡片（不存在则从 API 加载并渲染）
async function scrollToTask(taskId) {
    let card = document.getElementById(`task-${taskId}`);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('ring-2', 'ring-emerald-500');
        setTimeout(() => card.classList.remove('ring-2', 'ring-emerald-500'), 2000);
        return;
    }

    // 卡片不在 DOM 中，从 API 获取状态再渲染
    const token = localStorage.getItem('token') || '';
    try {
        const response = await fetch(`/api/v1/image/status/${taskId}`, {
            headers: { 'Authorization': 'Bearer ' + token },
        });
        if (!response.ok) throw new Error('任务不存在');

        const data = await response.json();

        // 创建卡片
        createTaskCard(taskId, data.prompt || '(无提示词)', data.size || '1024x1024', data.quality || 'medium', data.n || 1);

        // 等待 DOM 更新
        await new Promise(r => setTimeout(r, 50));

        card = document.getElementById(`task-${taskId}`);
        if (!card) return;

        // 更新状态
        updateTaskStatus(card, data.status);

        // 如果有原始中文 prompt，显示双语
        if (data.original_prompt) {
            const promptEl = card.querySelector('.task-prompt');
            if (promptEl) {
                promptEl.innerHTML = `
                    <span class="prompt-highlight">${escapeHtml(data.prompt || '')}</span>
                    <span class="block text-xs text-slate-400 mt-1">原文：${escapeHtml(data.original_prompt)}</span>
                `;
            }
        }

        // 已完成：展示结果
        if (data.status === 'completed') {
            const taskProgress = card.querySelector('.task-progress');
            if (taskProgress) taskProgress.classList.add('hidden');
            showImageResult(card, data);
        }
        // 失败：展示错误
        else if (data.status === 'failed') {
            const taskProgress = card.querySelector('.task-progress');
            if (taskProgress) taskProgress.classList.add('hidden');
            showError(card, data.error_message);
        }
        // 进行中：开始轮询
        else if (data.status === 'pending' || data.status === 'processing') {
            const taskProgress = card.querySelector('.task-progress');
            if (taskProgress) taskProgress.classList.remove('hidden');
            startPolling(taskId, data.prompt || '', data.size || '1024x1024', data.quality || 'medium', data.n || 1);
        }

        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('ring-2', 'ring-emerald-500');
        setTimeout(() => card.classList.remove('ring-2', 'ring-emerald-500'), 2000);

    } catch (error) {
        console.error('加载历史任务失败:', error);
        alert('无法加载该任务');
    }
}

// 页面加载时加载历史
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
});
