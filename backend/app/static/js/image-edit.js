// 检查登录
(function() {
    const token = localStorage.getItem('token');
    if (!token) window.location.href = '/login';
})();

// 从 URL 参数获取原图路径
const params = new URLSearchParams(window.location.search);
const IMAGE_SRC = params.get('src') || '';
if (!IMAGE_SRC) {
    alert('缺少图片参数');
    window.location.href = '/image';
}

console.log('image-edit.js 已加载, src:', IMAGE_SRC);

// ========== Canvas 状态 ==========
const bgCanvas = document.getElementById('bgCanvas');
const maskCanvas = document.getElementById('maskCanvas');
const ctx = bgCanvas.getContext('2d');
const mctx = maskCanvas.getContext('2d');

// 蒙版绘制数据：存储绘制过的笔画路径（用于撤销）
// 每个 stroke: { points: [{x,y}], size: number }
const strokes = [];

let currentTool = 'brush';  // 'brush' | 'eraser'
let brushSize = 30;
let isDrawing = false;
let lastPoint = null;
let currentStroke = null;
let imageLoaded = false;

// ========== 加载原图到背景 Canvas ==========
function loadImage() {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
        // 限制最大显示尺寸
        const maxW = 800;
        const maxH = 600;
        let w = img.naturalWidth;
        let h = img.naturalHeight;
        if (w > maxW || h > maxH) {
            const ratio = Math.min(maxW / w, maxH / h);
            w = Math.round(w * ratio);
            h = Math.round(h * ratio);
        }

        bgCanvas.width = w;
        bgCanvas.height = h;
        maskCanvas.width = w;
        maskCanvas.height = h;

        ctx.drawImage(img, 0, 0, w, h);

        // 设置蒙版 canvas 样式（半透明覆盖层）
        maskCanvas.style.width = w + 'px';
        maskCanvas.style.height = h + 'px';

        imageLoaded = true;
        console.log(`原图已加载: ${w}x${h}`);
    };
    img.onerror = () => {
        alert('加载原图失败，请检查图片路径');
    };
    img.src = IMAGE_SRC;
}

// ========== 工具切换 ==========
function setTool(tool) {
    currentTool = tool;
    document.getElementById('btnBrush').classList.toggle('tool-active', tool === 'brush');
    document.getElementById('btnEraser').classList.toggle('tool-active', tool === 'eraser');
    maskCanvas.style.cursor = tool === 'eraser' ? 'cell' : 'crosshair';
}

function setBrushSize(val) {
    brushSize = parseInt(val);
    document.getElementById('brushSizeLabel').textContent = brushSize + 'px';
}

// ========== 绘制逻辑 ==========
function getPos(e) {
    const rect = maskCanvas.getBoundingClientRect();
    const scaleX = maskCanvas.width / rect.width;
    const scaleY = maskCanvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
    };
}

function drawBrush(ctx2d, from, to, size) {
    ctx2d.lineWidth = size;
    ctx2d.lineCap = 'round';
    ctx2d.lineJoin = 'round';
    ctx2d.beginPath();
    ctx2d.moveTo(from.x, from.y);
    ctx2d.lineTo(to.x, to.y);
    ctx2d.stroke();
}

maskCanvas.addEventListener('mousedown', (e) => {
    if (!imageLoaded) return;
    isDrawing = true;
    const pos = getPos(e);
    lastPoint = pos;
    currentStroke = { points: [pos], size: brushSize, tool: currentTool };

    if (currentTool === 'brush') {
        mctx.globalCompositeOperation = 'source-over';
    } else {
        mctx.globalCompositeOperation = 'destination-out';
    }
    mctx.fillStyle = 'rgba(255, 80, 80, 0.45)';
    mctx.strokeStyle = 'rgba(255, 80, 80, 0.45)';
    mctx.beginPath();
    mctx.arc(pos.x, pos.y, brushSize / 2, 0, Math.PI * 2);
    mctx.fill();
});

maskCanvas.addEventListener('mousemove', (e) => {
    if (!isDrawing || !imageLoaded) return;
    const pos = getPos(e);
    if (currentTool === 'brush') {
        mctx.globalCompositeOperation = 'source-over';
    } else {
        mctx.globalCompositeOperation = 'destination-out';
    }
    mctx.fillStyle = 'rgba(255, 80, 80, 0.45)';
    mctx.strokeStyle = 'rgba(255, 80, 80, 0.45)';
    drawBrush(mctx, lastPoint, pos, brushSize);
    currentStroke.points.push(pos);
    lastPoint = pos;
});

maskCanvas.addEventListener('mouseup', () => {
    if (!isDrawing) return;
    isDrawing = false;
    if (currentStroke && currentStroke.points.length > 0) {
        strokes.push(currentStroke);
    }
    currentStroke = null;
    lastPoint = null;
});

maskCanvas.addEventListener('mouseleave', () => {
    if (isDrawing) {
        isDrawing = false;
        if (currentStroke && currentStroke.points.length > 0) {
            strokes.push(currentStroke);
        }
        currentStroke = null;
        lastPoint = null;
    }
});

// ========== 撤销 / 清空 ==========
function undoStroke() {
    if (strokes.length === 0) return;
    strokes.pop();
    redrawMask();
}

function clearMask() {
    if (strokes.length === 0) return;
    strokes.length = 0;
    redrawMask();
}

function redrawMask() {
    mctx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    for (const stroke of strokes) {
        if (stroke.tool === 'brush') {
            mctx.globalCompositeOperation = 'source-over';
        } else {
            mctx.globalCompositeOperation = 'destination-out';
        }
        mctx.fillStyle = 'rgba(255, 80, 80, 0.45)';
        mctx.strokeStyle = 'rgba(255, 80, 80, 0.45)';

        // 绘制每个笔画
        if (stroke.points.length === 1) {
            const p = stroke.points[0];
            mctx.beginPath();
            mctx.arc(p.x, p.y, stroke.size / 2, 0, Math.PI * 2);
            mctx.fill();
        } else {
            for (let i = 1; i < stroke.points.length; i++) {
                drawBrush(mctx, stroke.points[i - 1], stroke.points[i], stroke.size);
            }
        }
    }
}

// ========== 生成蒙版 Canvas（白=编辑区, 黑=保持区）==========
function generateMaskDataURL() {
    const tmpCanvas = document.createElement('canvas');
    tmpCanvas.width = maskCanvas.width;
    tmpCanvas.height = maskCanvas.height;
    const tmpCtx = tmpCanvas.getContext('2d');

    // 黑色背景
    tmpCtx.fillStyle = '#000000';
    tmpCtx.fillRect(0, 0, tmpCanvas.width, tmpCanvas.height);

    // 白色 = 蒙版涂抹区域
    for (const stroke of strokes) {
        if (stroke.tool !== 'brush') continue;
        tmpCtx.fillStyle = '#ffffff';
        tmpCtx.strokeStyle = '#ffffff';
        if (stroke.points.length === 1) {
            const p = stroke.points[0];
            tmpCtx.beginPath();
            tmpCtx.arc(p.x, p.y, stroke.size / 2, 0, Math.PI * 2);
            tmpCtx.fill();
        } else {
            for (let i = 1; i < stroke.points.length; i++) {
                drawBrush(tmpCtx, stroke.points[i - 1], stroke.points[i], stroke.size);
            }
        }
    }

    return tmpCanvas.toDataURL('image/png');
}

// 获取原图的 base64
function getImageBase64() {
    // 从 bgCanvas 获取（已经是原图绘制在上面）
    // 但可能有缩放。用原始图片重新 toDataURL
    const tmpCanvas = document.createElement('canvas');
    tmpCanvas.width = bgCanvas.width;
    tmpCanvas.height = bgCanvas.height;
    const tmpCtx = tmpCanvas.getContext('2d');
    tmpCtx.drawImage(bgCanvas, 0, 0);
    return tmpCanvas.toDataURL('image/png');
}

// ========== 键盘快捷键 ==========
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        undoStroke();
        return;
    }
    if (e.key === 'b' || e.key === 'B') {
        setTool('brush');
    }
    if (e.key === 'e' || e.key === 'E') {
        setTool('eraser');
    }
});

// 滚轮调整画刷大小
maskCanvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -5 : 5;
    brushSize = Math.max(5, Math.min(120, brushSize + delta));
    document.getElementById('brushSize').value = brushSize;
    document.getElementById('brushSizeLabel').textContent = brushSize + 'px';
});

// ========== 翻译（复用图片页面的 /translate 接口）==========
async function doEditTranslate() {
    const input = document.getElementById('editPrompt');
    const btn = document.getElementById('editTranslateBtn');
    const text = input.value.trim();
    if (!text) return;

    btn.disabled = true;
    btn.textContent = '⏳ 翻译中...';

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
        btn.textContent = '🌐 翻译为英文';
    }
}

// ========== 提交编辑任务 ==========
async function handleEditGenerate() {
    const prompt = document.getElementById('editPrompt').value.trim();
    if (!prompt) {
        alert('请输入修改描述');
        return;
    }
    if (strokes.filter(s => s.tool === 'brush').length === 0) {
        alert('请先在图片上涂抹要修改的区域');
        return;
    }

    const btn = document.getElementById('editGenerateBtn');
    btn.disabled = true;
    btn.textContent = '⏳ 提交中...';

    const token = localStorage.getItem('token') || '';
    try {
        const imageBase64 = getImageBase64();
        const maskBase64 = generateMaskDataURL();

        const response = await fetch('/api/v1/image/edit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({
                image_base64: imageBase64,
                mask_base64: maskBase64,
                prompt: prompt,
                size: '1024x1024',
            }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || '提交失败');
        }

        const data = await response.json();
        const taskId = data.task_id;

        // 添加结果卡片
        addEditResultCard(taskId, prompt);

        // 开始轮询
        startEditPolling(taskId);

    } catch (e) {
        alert('提交失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '✨ 微调生成';
    }
}

// ========== 结果卡片 ==========
const editStatusMap = {
    'pending': { text: '排队中', icon: '⏳' },
    'processing': { text: '生成中', icon: '🔄' },
    'completed': { text: '已完成', icon: '✅' },
    'failed': { text: '失败', icon: '❌' },
};

function addEditResultCard(taskId, prompt) {
    const container = document.getElementById('editResults');
    // 移除空状态
    const empty = container.querySelector('.text-center');
    if (empty) empty.remove();

    const card = document.createElement('div');
    card.id = `edit-${taskId}`;
    card.className = 'bg-slate-50 border border-slate-200 rounded-xl p-3';
    card.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <span class="edit-status-icon text-sm">⏳</span>
            <span class="edit-status-text text-xs text-slate-500">排队中</span>
        </div>
        <p class="text-xs text-slate-600 truncate">${prompt}</p>
        <div class="edit-progress mt-2 hidden">
            <div class="w-full bg-slate-200 rounded-full h-1.5">
                <div class="edit-progress-bar bg-orange-500 h-1.5 rounded-full transition-all" style="width:0%"></div>
            </div>
        </div>
        <div class="edit-result mt-2 hidden"></div>
        <div class="edit-error mt-2 hidden p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600"></div>
    `;
    container.insertBefore(card, container.firstChild);
}

function startEditPolling(taskId) {
    const token = localStorage.getItem('token') || '';
    const card = document.getElementById(`edit-${taskId}`);
    if (!card) return;

    const progressDiv = card.querySelector('.edit-progress');
    const progressBar = card.querySelector('.edit-progress-bar');
    progressDiv.classList.remove('hidden');
    let progress = 0;

    const progressTimer = setInterval(() => {
        progress = Math.min(progress + Math.random() * 5, 90);
        progressBar.style.width = progress + '%';
    }, 2000);

    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/v1/image/status/${taskId}`, {
                headers: { 'Authorization': 'Bearer ' + token },
            });
            if (!response.ok) throw new Error('请求失败');

            const data = await response.json();
            const status = data.status;
            const info = editStatusMap[status] || editStatusMap['pending'];

            card.querySelector('.edit-status-icon').textContent = info.icon;
            card.querySelector('.edit-status-text').textContent = info.text;

            if (status === 'completed') {
                clearInterval(pollInterval);
                clearInterval(progressTimer);
                progressDiv.classList.add('hidden');
                showEditResult(card, data);
            } else if (status === 'failed') {
                clearInterval(pollInterval);
                clearInterval(progressTimer);
                progressDiv.classList.add('hidden');
                const errEl = card.querySelector('.edit-error');
                errEl.classList.remove('hidden');
                errEl.textContent = data.error_message || '未知错误';
            }
        } catch (e) {
            console.error('轮询失败:', e);
            clearInterval(pollInterval);
            clearInterval(progressTimer);
        }
    }, 3000);
}

function showEditResult(card, data) {
    const resultDiv = card.querySelector('.edit-result');
    resultDiv.classList.remove('hidden');

    const paths = data.image_paths || [];
    if (paths.length === 0) {
        resultDiv.innerHTML = '<p class="text-xs text-slate-400">未获取到结果图片</p>';
        return;
    }

    resultDiv.innerHTML = paths.map(p => `
        <div class="border border-slate-200 rounded-lg overflow-hidden mt-2">
            <img src="${p}?t=${Date.now()}" class="w-full object-contain bg-white cursor-pointer" onclick="openEditLightbox('${p}')" alt="微调结果">
            <a href="${p}" download class="block text-center text-xs bg-orange-600 hover:bg-orange-700 text-white py-1.5 transition-colors cursor-pointer">下载</a>
        </div>
    `).join('');
}

function openEditLightbox(src) {
    const existing = document.getElementById('editLightbox');
    if (existing) existing.remove();

    const lb = document.createElement('div');
    lb.id = 'editLightbox';
    lb.className = 'fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-8';
    lb.innerHTML = `
        <button onclick="this.parentElement.remove()" class="absolute top-4 right-4 text-white/80 hover:text-white text-2xl cursor-pointer">&times;</button>
        <img src="${src}" class="max-w-full max-h-full object-contain rounded-lg shadow-2xl">
    `;
    lb.addEventListener('click', (e) => { if (e.target === lb) lb.remove(); });
    document.body.appendChild(lb);
}

// ========== 初始化 ==========
loadImage();
