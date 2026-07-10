// 检查登录状态
(function() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
    }
})();

console.log('video.js 已加载');

// 调试日志存储
const debugLogs = [];
let debugPanelVisible = false;

// 参考图存储 { name, base64 } 数组
let refImages = [];
const MAX_REF_IMAGES = 3;
const MAX_REF_FILE_SIZE = 10 * 1024 * 1024; // 10MB

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
    
    debugLogs.unshift(log); // 添加到开头
    
    // 更新调试面板
    updateDebugPanel();
    
    // 自动显示调试面板
    if (!debugPanelVisible) {
        showDebugPanel();
    }
}

function updateDebugPanel() {
    const debugContent = document.getElementById('debugContent');
    const debugCount = document.getElementById('debugCount');
    
    if (!debugContent) return;
    
    // 更新计数
    debugCount.textContent = debugLogs.length;
    
    if (debugLogs.length === 0) {
        debugContent.innerHTML = '<div class="text-xs text-slate-400 text-center py-8">暂无调试记录</div>';
        return;
    }
    
    // 生成调试日志 HTML
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

// ========== 参考图处理 ==========
function handleRefImageSelect(event) {
    const files = event.target.files;
    if (!files.length) return;

    const remaining = MAX_REF_IMAGES - refImages.length;
    if (remaining <= 0) {
        alert(`最多只能上传 ${MAX_REF_IMAGES} 张参考图`);
        event.target.value = '';
        return;
    }

    const toProcess = Math.min(files.length, remaining);
    let validCount = 0;
    let loadedCount = 0;

    for (let i = 0; i < toProcess; i++) {
        const file = files[i];
        if (file.size > MAX_REF_FILE_SIZE) {
            alert(`图片 "${file.name}" 超过 10MB 限制`);
            continue;
        }
        if (!file.type.startsWith('image/')) {
            alert(`"${file.name}" 不是图片文件`);
            continue;
        }

        validCount++;
        const reader = new FileReader();
        reader.onload = function(e) {
            refImages.push({
                name: file.name,
                base64: e.target.result,
            });
            loadedCount++;
            if (loadedCount === validCount) {
                renderRefPreviews();
            }
        };
        reader.readAsDataURL(file);
    }

    event.target.value = '';

    if (validCount === 0) {
        renderRefPreviews();
    }
}

function removeRefImage(index) {
    refImages.splice(index, 1);
    renderRefPreviews();
}

function renderRefPreviews() {
    const container = document.getElementById('refPreviews');
    if (!container) return;

    const promptInput = document.getElementById('promptInput');

    if (refImages.length === 0) {
        container.innerHTML = '<span class="text-xs text-slate-400">未选择参考图</span>';
        if (promptInput) {
            promptInput.placeholder = '描述您想要生成的视频内容（如：日系治愈插画少女站在初夏樱花街道）...';
        }
        return;
    }

    container.innerHTML = refImages.map((img, i) => `
        <div class="relative flex-shrink-0 group">
            <img src="${img.base64}" class="w-10 h-10 rounded-lg object-cover border border-slate-200" title="${img.name}">
            <button onclick="removeRefImage(${i})" class="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white rounded-full text-[10px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer leading-none">x</button>
        </div>
    `).join('');

    // 有参考图时更新提示词引导
    if (promptInput) {
        promptInput.placeholder = '已添加参考角色图片，请描述想让角色做什么（如：在樱花树下微笑走路，微风拂过头发）...';
        if (!promptInput.value.trim()) {
            promptInput.focus();
        }
    }
}

// 任务状态映射
const statusMap = {
    'pending': { text: '排队中', icon: '⏳', color: 'text-slate-500', bg: 'bg-slate-50' },
    'processing': { text: '生成中', icon: '🔄', color: 'text-blue-500', bg: 'bg-blue-50' },
    'completed': { text: '已完成', icon: '✅', color: 'text-emerald-500', bg: 'bg-emerald-50' },
    'failed': { text: '失败', icon: '❌', color: 'text-red-500', bg: 'bg-red-50' },
};

// 活跃的任务轮询
const activeTasks = {};

// 生成视频
async function handleGenerate() {
    console.log('🚨 [手动触发] handleGenerate 被调用！');
    const prompt = document.getElementById('promptInput').value.trim();
    if (!prompt) return;

    const token = localStorage.getItem('token') || '';
    const generateBtn = document.getElementById('generateBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span>⏳ 提交中...</span>';

    const duration = document.getElementById('durationSelect').value;
    const resolution = document.getElementById('resolutionSelect').value;
    const ratio = document.getElementById('ratioSelect').value;
    const seed = parseInt(document.getElementById('seedInput').value) || -1;

    // 收集参考图 base64
    const referenceImages = refImages.map(img => img.base64);

    try {
        const response = await fetch('/api/v1/video/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({
                prompt: prompt,
                duration: parseInt(duration),
                resolution: resolution,
                ratio: ratio,
                seed: seed,
                reference_images: referenceImages.length > 0 ? referenceImages : undefined,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP 错误！状态码: ${response.status}`);
        }

        const data = await response.json();
        const taskId = data.task_id;

        // 创建任务卡片
        createTaskCard(taskId, prompt, duration, resolution, refImages.length);

        // 开始轮询状态
        startPolling(taskId, prompt, duration, resolution);

        // 清空输入
        document.getElementById('promptInput').value = '';
        // 清空参考图
        refImages = [];
        renderRefPreviews();

    } catch (error) {
        console.error('提交任务失败:', error);
        alert('提交任务失败，请稍后重试');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<span>✨ 生成</span>';
    }
}

// 创建任务卡片
function createTaskCard(taskId, prompt, duration, resolution, refCount = 0) {
    const container = document.getElementById('resultsList');
    const card = document.createElement('div');
    card.id = `task-${taskId}`;
    card.className = 'bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden';
    const refBadge = refCount > 0 ? `<span class="text-xs bg-purple-100 text-purple-600 px-2 py-0.5 rounded-full">🖼 参考图 x${refCount}</span>` : '';
    card.innerHTML = `
        <div class="p-5">
            <div class="flex items-start justify-between mb-3">
                <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-2">
                        <span class="status-icon text-lg">⏳</span>
                        <span class="status-text text-sm font-medium text-slate-500">排队中</span>
                        ${refBadge}
                    </div>
                    <p class="text-sm text-slate-700 leading-relaxed">${prompt}</p>
                </div>
                <button onclick="deleteTask('${taskId}')" class="text-slate-400 hover:text-red-500 p-1 rounded transition-colors" title="删除任务">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
            </div>
            <div class="flex items-center space-x-3 text-xs text-slate-400 mb-3">
                <span>⏱ ${duration}秒</span>
                <span>📐 ${resolution}</span>
                <span class="task-time text-xs"></span>
            </div>
            <div class="task-progress hidden">
                <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                    <div class="progress-bar bg-purple-500 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                </div>
                <p class="text-xs text-slate-400 mt-2 text-center">🎬 AI 正在为您生成视频，请稍候（通常 1-3 分钟）...</p>
            </div>
            <div class="task-result hidden mt-4">
                <!-- 视频结果将在这里显示 -->
            </div>
            <div class="task-error hidden mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p class="text-xs text-red-600 error-message"></p>
            </div>
        </div>
    `;

    container.insertBefore(card, container.firstChild);

    // 保存任务信息
    activeTasks[taskId] = {
        prompt: prompt,
        duration: duration,
        resolution: resolution,
        polling: false,
    };
}

// 轮询任务状态
function startPolling(taskId, prompt, duration, resolution) {
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
        progress = Math.min(progress + Math.random() * 5, 95);
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
    }, 2000);

    // 开始轮询
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/v1/video/status/${taskId}`, {
                headers: {
                    'Authorization': 'Bearer ' + token,
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP 错误！状态码：${response.status}`);
            }

            const data = await response.json();
            const status = data.status;

            // 添加调试日志
            addDebugLog(taskId, data, status);

            // 更新状态显示
            updateTaskStatus(card, status, data);

            if (status === 'completed') {
                // 停止轮询
                clearInterval(pollInterval);
                clearInterval(progressTimer);

                // 显示视频结果
                showVideoResult(card, data);

                // 更新历史记录
                loadHistory();

            } else if (status === 'failed') {
                // 停止轮询
                clearInterval(pollInterval);
                clearInterval(progressTimer);

                // 显示错误信息
                showError(card, data.error_message);

                // 更新历史记录
                loadHistory();
            }

        } catch (error) {
            console.error('轮询状态失败:', error);
            // 添加错误调试日志
            addDebugLog(taskId, { error: error.message, status: 'error' }, 'failed');
            clearInterval(pollInterval);
            clearInterval(progressTimer);
            showError(card, '网络请求失败，请稍后重试');
        }
    }, 10000); // 每 10 秒查一次状态

    activeTasks[taskId].polling = pollInterval;
}

// 更新任务状态
function updateTaskStatus(card, status, data) {
    const statusInfo = statusMap[status] || statusMap['pending'];
    const statusIcon = card.querySelector('.status-icon');
    const statusText = card.querySelector('.status-text');

    if (statusIcon) statusIcon.textContent = statusInfo.icon;
    if (statusText) {
        statusText.textContent = statusInfo.text;
        statusText.className = `status-text text-sm font-medium ${statusInfo.color}`;
    }
}

// 显示视频结果
function showVideoResult(card, data) {
    const taskProgress = card.querySelector('.task-progress');
    const taskResult = card.querySelector('.task-result');
    const progressBar = card.querySelector('.progress-bar');

    // 隐藏进度条
    taskProgress.classList.add('hidden');

    // 显示结果
    taskResult.classList.remove('hidden');

    const videoPath = data.video_path || data.video_url;
    if (videoPath) {
        taskResult.innerHTML = `
            <div class="border border-slate-200 rounded-xl overflow-hidden">
                <video controls class="w-full max-h-96 bg-slate-900" preload="metadata">
                    <source src="${videoPath}" type="video/mp4">
                    您的浏览器不支持视频播放
                </video>
            </div>
            <div class="flex items-center space-x-3 mt-3">
                <a href="${videoPath}" download class="inline-flex items-center space-x-1 text-xs bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg transition-colors cursor-pointer">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                    <span>下载视频</span>
                </a>
                <button onclick="copyPrompt('${data.prompt}')" class="inline-flex items-center space-x-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-4 py-2 rounded-lg transition-colors cursor-pointer">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>
                    <span>复制提示词</span>
                </button>
            </div>
        `;
    } else {
        taskResult.innerHTML = `
            <div class="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                <p class="text-sm text-emerald-600">✅ 视频生成完成！</p>
                <p class="text-xs text-emerald-500 mt-1">视频 URL: ${data.video_url || '无'}</p>
            </div>
        `;
    }
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
        const response = await fetch(`/api/v1/video/${taskId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + token,
            },
        });

        if (response.ok) {
            // 移除卡片
            const card = document.getElementById(`task-${taskId}`);
            if (card) card.remove();

            // 停止轮询
            if (activeTasks[taskId] && activeTasks[taskId].polling) {
                clearInterval(activeTasks[taskId].polling);
            }
            delete activeTasks[taskId];

            // 更新历史
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
        alert('提示词已复制到剪贴板');
    }).catch(err => {
        console.error('复制失败:', err);
        alert('复制失败');
    });
}

// 加载历史记录
async function loadHistory() {
    const token = localStorage.getItem('token') || '';

    try {
        const response = await fetch('/api/v1/video/history?limit=10', {
            headers: {
                'Authorization': 'Bearer ' + token,
            },
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
            return `
                <div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200/60 hover:border-purple-300 transition-colors cursor-pointer" onclick="scrollToTask('${task.task_id}')">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs">${statusInfo.icon} <span class="${statusInfo.color}">${statusInfo.text}</span></span>
                        <span class="text-[10px] text-slate-400">${time}</span>
                    </div>
                    <p class="text-xs text-slate-600 truncate">${task.prompt}</p>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('加载历史失败:', error);
    }
}

// 滚动到任务卡片
function scrollToTask(taskId) {
    const card = document.getElementById(`task-${taskId}`);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('ring-2', 'ring-purple-500');
        setTimeout(() => {
            card.classList.remove('ring-2', 'ring-purple-500');
        }, 2000);
    }
}

// 页面加载时加载历史
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    renderRefPreviews();

    // 参考图上传事件
    const refInput = document.getElementById('refImageInput');
    if (refInput) {
        refInput.addEventListener('change', handleRefImageSelect);
    }

    // 回车键生成（已禁用，防止意外触发）
    // document.getElementById('promptInput').addEventListener('keydown', (e) => {
    //     if (e.key === 'Enter' && !e.shiftKey) {
    //         e.preventDefault();
    //         if (!document.getElementById('generateBtn').disabled) {
    //             handleGenerate();
    //         }
    //     }
    // });

    // 测试模式：自动创建测试任务（已关闭，需要手动点击生成）
    // if (window.location.hostname === 'localhost') {
    //     console.log(' 本地环境，5 秒后自动创建测试任务...');
    //     setTimeout(() => {
    //         console.log('🎬 开始创建测试任务...');
    //         testCreateTask();
    //     }, 5000);
    // }
});

// 测试创建任务（仅用于演示）
async function testCreateTask() {
    const token = localStorage.getItem('token') || '';
    try {
        const response = await fetch('/api/v1/video/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({
                prompt: '🎬 测试视频生成（固定火山引擎任务 ID）',
                duration: 5,
                resolution: '720p',
                seed: -1,
            }),
        });

        if (!response.ok) {
            console.error('测试任务创建失败:', response.status);
            return;
        }

        const data = await response.json();
        console.log('✅ 测试任务创建成功:', data);
        
        // 创建任务卡片
        createTaskCard(data.task_id, '🎬 测试视频生成（固定火山引擎任务 ID）', 5, '720p');
        
        // 开始轮询状态
        startPolling(data.task_id, '🎬 测试视频生成（固定火山引擎任务 ID）', 5, '720p');
        
    } catch (error) {
        console.error('测试任务创建失败:', error);
    }
}
