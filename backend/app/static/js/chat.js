(function() { const token = localStorage.getItem('token'); if (!token) { window.location.href = '/login'; } })();
console.log('chat.js 已加载 - 版本 20260626e');
(function initUserInfo(){ const u=localStorage.getItem('username')||'用户'; const r=localStorage.getItem('role')||'employee'; const kb=JSON.parse(localStorage.getItem('kb_access')||'["default"]'); document.getElementById('displayUsername').textContent=u; document.getElementById('avatarLetter').textContent=u.charAt(0).toUpperCase(); document.getElementById('menuUsername').textContent=u; document.getElementById('menuRole').textContent=r==='hr'?'HR管理员':r==='boss'?'超级管理员':'普通员工'; if(kb.length>1){ const sel=document.getElementById('kbSelect'); sel.classList.remove('hidden'); kb.forEach(function(k){ const o=document.createElement('option'); o.value=k; o.textContent=k==='default'?'默认库':k==='manage'?'管理库':k; sel.appendChild(o); }); sel.value=kb[0]; } })();
function toggleUserMenu(){ const m=document.getElementById('userMenu'); m.classList.toggle('hidden'); if(!m.classList.contains('hidden')){ document.addEventListener('click',function f(e){ if(!e.target.closest('#userDropdown')){m.classList.add('hidden');document.removeEventListener('click',f);} }); } }
let deepThinkOn = false;
function toggleDeepThink(){ deepThinkOn = !deepThinkOn; const b = document.getElementById('deepThinkBtn'); b.dataset.on = deepThinkOn; if(deepThinkOn){ b.className = b.className.replace('bg-slate-200/50','bg-blue-100').replace('text-slate-400','text-blue-600').replace('hover:bg-slate-100','hover:bg-blue-200').replace('hover:text-slate-500','hover:text-blue-700'); b.title = '已开启：AI 深度语义加工（较慢但更专业）'; } else { b.className = b.className.replace('bg-blue-100','bg-slate-200/50').replace('text-blue-600','text-slate-400').replace('hover:bg-blue-200','hover:bg-slate-100').replace('hover:text-blue-700','hover:text-slate-500'); b.title = '关闭：仅返回知识库原文 | 开启：AI 深度语义加工'; } }
function getSelectedKb(){ const s=document.getElementById('kbSelect'); return s.classList.contains('hidden')?['default']:[s.value]; }
async function handleLogout(){ try{ const t=localStorage.getItem('token'); if(t) await fetch('/api/v1/logout',{method:'POST',headers:{'Authorization':'Bearer '+t}}); }catch(e){} localStorage.clear(); window.location.href='/login'; }
const chatContainer = document.getElementById('chatContainer');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const clearContextBtn = document.getElementById('clearContextBtn');
const contextBadge = document.getElementById('contextBadge');
const contextBadgeText = document.getElementById('contextBadgeText');
const messageQueryMap = {}; const messageContentMap = {}; const activeRatings = {}; let lastUserQuery = "";
const MAX_HISTORY_TURNS = 3; let conversationHistory = [];
function updateContextUI() { const turns = Math.floor(conversationHistory.length / 2); if (turns > 0) { contextBadge.classList.remove('hidden'); contextBadge.classList.add('flex'); contextBadgeText.textContent = `上下文 ${turns} 轮`; clearContextBtn.classList.remove('hidden'); } else { contextBadge.classList.add('hidden'); contextBadge.classList.remove('flex'); clearContextBtn.classList.add('hidden'); } }
function clearContext() { if (chatContainer.classList.contains('chat-clearing')) return; chatContainer.classList.add('chat-clearing'); const overlay = document.getElementById('clearFlashOverlay'); overlay.classList.remove('active'); void overlay.offsetWidth; overlay.classList.add('active'); setTimeout(() => { conversationHistory = []; updateContextUI(); const welcomeNode = chatContainer.firstElementChild; chatContainer.innerHTML = ''; if (welcomeNode) chatContainer.appendChild(welcomeNode); const divider = document.createElement('div'); divider.className = "flex items-center justify-center my-2 chat-restored"; divider.innerHTML = `<div class="flex items-center space-x-2 text-xs text-slate-400"><div class="h-px w-16 bg-slate-200"></div><span class="bg-slate-100 border border-slate-200 px-3 py-1 rounded-full flex items-center space-x-1"><span>✨</span><span>已开启新话题，上下文已清除</span></span><div class="h-px w-16 bg-slate-200"></div></div>`; chatContainer.appendChild(divider); chatContainer.classList.remove('chat-clearing'); chatContainer.classList.add('chat-restored'); chatContainer.addEventListener('animationend', () => { chatContainer.classList.remove('chat-restored'); }, { once: true }); scrollToBottom(); }, 360); }
function scrollToBottom() { chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' }); }
function appendMessage(role, text) { const msgRow = document.createElement('div'); msgRow.className = role === 'user' ? "flex items-start space-x-3 max-w-[85%] ml-auto justify-end" : "flex items-start space-x-3 max-w-[85%]"; if (role === 'user') { msgRow.innerHTML = `<div class="bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-tr-none shadow-sm text-sm leading-relaxed whitespace-pre-wrap">${text}</div><div class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white flex-shrink-0 text-xs font-bold">我</div>`; } else { msgRow.innerHTML = `<div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 flex-shrink-0 text-xs">🤖</div><div class="bg-white border border-slate-200 text-slate-700 px-4 py-2.5 rounded-2xl rounded-tl-none shadow-sm text-sm leading-relaxed whitespace-pre-wrap">${text}</div>`; } chatContainer.appendChild(msgRow); scrollToBottom(); }

async function handleSend() { const query = userInput.value.trim(); if (!query) return; lastUserQuery = query; appendMessage('user', query); userInput.value = ''; userInput.disabled = true; sendBtn.disabled = true; sendBtn.innerHTML = '<span>思考中...</span>'; conversationHistory.push({ role: "user", content: query }); const historyToSend = conversationHistory.slice(0, -1).slice(-(MAX_HISTORY_TURNS * 2)); const msgRow = document.createElement('div'); const msgId = 'msg-' + Date.now(); messageQueryMap[msgId] = query; msgRow.className = "flex items-start space-x-3 max-w-[85%]"; msgRow.innerHTML = `<div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 flex-shrink-0 text-xs">🤖</div><div class="space-y-3 flex-1"><div id="text-${msgId}" class="bg-white border border-slate-200 text-slate-700 px-4 py-3 rounded-2xl rounded-tl-none shadow-sm text-sm leading-relaxed whitespace-pre-wrap flex items-center space-x-2"><span class="text-blue-500 font-medium animate-pulse">🔍 正在深度检索行业法规与GB标准数据库，请稍候...</span></div><div id="toolbar-${msgId}" class="flex items-center space-x-2 pl-1 hidden"><button onclick="downloadContent('${msgId}')" title="下载此回复内容到本地" class="flex items-center space-x-1 text-xs text-slate-500 hover:text-blue-600 bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 px-3 py-1.5 rounded-lg transition-all cursor-pointer"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg><span>下载</span></button></div><div id="extend-box-${msgId}" class="flex flex-col space-y-2 pl-1 hidden"></div><div class="bg-slate-100 border border-slate-200/60 p-3 rounded-xl max-w-md hidden" id="container-${msgId}"><div class="flex items-center space-x-1 text-xs text-slate-400"><span class="mr-1 text-[11px]">此次政策解答是否准确：</span><button class="star-btn cursor-pointer text-slate-300 text-sm" onclick="handleStarClick('${msgId}', 1)">★</button><button class="star-btn cursor-pointer text-slate-300 text-sm" onclick="handleStarClick('${msgId}', 2)">★</button><button class="star-btn cursor-pointer text-slate-300 text-sm" onclick="handleStarClick('${msgId}', 3)">★</button><button class="star-btn cursor-pointer text-slate-300 text-sm" onclick="handleStarClick('${msgId}', 4)">★</button><button class="star-btn cursor-pointer text-slate-300 text-sm" onclick="handleStarClick('${msgId}', 5)">★</button><span id="status-${msgId}" class="rating-status ml-2 text-[11px] text-slate-500"></span></div><div id="comment-box-${msgId}" class="hidden mt-3 pt-3 border-t border-slate-200/60 flex flex-col space-y-2"><textarea id="textarea-${msgId}" placeholder="如果您发现条例引用或国标条款有误，请留下您的宝贵意见（选填）..." class="w-full text-xs p-2 border border-slate-200 rounded-lg focus:outline-none focus:border-blue-400 bg-white" rows="2"></textarea><button onclick="submitAllFeedback('${msgId}')" class="self-end bg-blue-600 hover:bg-blue-700 text-white text-[11px] px-3 py-1.5 rounded-md shadow-sm cursor-pointer">提交反馈</button></div></div></div>`; chatContainer.appendChild(msgRow); scrollToBottom(); const textContainer = document.getElementById(`text-${msgId}`); let accumulatedText = ""; const loadingPhrases = ['<span class="text-blue-500 font-medium animate-pulse">🔍 正在检索国家、部委级危化品及运输法规库...</span>', '<span class="text-indigo-500 font-medium animate-pulse">🧠 正在对匹配的国标规范（GB）进行条款比对与提炼...</span>', '<span class="text-amber-500 font-medium animate-pulse">✍️ 正在将繁琐的安全技术条款转换为易读的合规指南...</span>']; let phraseIndex = 0; const visualTimer = setInterval(() => { if (accumulatedText === "") { phraseIndex = (phraseIndex + 1) % loadingPhrases.length; textContainer.innerHTML = loadingPhrases[phraseIndex]; } }, 5000); try { const response = await fetch('/api/v1/knowledge/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'') }, body: JSON.stringify({ query: query, history: historyToSend, deep_think: deepThinkOn, file_content: uploadedFileContent, file_name: uploadedFileName, tool_id: selectedToolId }) }); if (!response.ok) throw new Error(`HTTP 错误！状态码: ${response.status}`); const reader = response.body.getReader(); const decoder = new TextDecoder("utf-8"); while (true) { const { value, done } = await reader.read(); if (done) break; const chunk = decoder.decode(value, { stream: true }); const lines = chunk.split('\n'); for (const line of lines) { if (line.startsWith('data: ')) { const dataContent = line.slice(6).trim(); if (dataContent === '[DONE]') { if (accumulatedText) { conversationHistory.push({ role: "assistant", content: accumulatedText }); if (conversationHistory.length > MAX_HISTORY_TURNS * 2) { conversationHistory = conversationHistory.slice(-MAX_HISTORY_TURNS * 2); } updateContextUI(); } document.getElementById(`container-${msgId}`).classList.remove('hidden'); messageContentMap[msgId] = accumulatedText; document.getElementById('toolbar-'+msgId).classList.remove('hidden'); (async function loadExtends(){
    try {
        const r = await fetch('/api/v1/knowledge/chat/extend', {method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+(localStorage.getItem('token')||'')},body:JSON.stringify({query:query,answer:accumulatedText})});
        const d = await r.json();
        if (d.questions && d.questions.length) {
            const eb = document.getElementById('extend-box-'+msgId);
            window._extQ = window._extQ || {};
            window._extQ[msgId] = d.questions;
            eb.innerHTML = d.questions.map(function(q,i){
                return `<button onclick="fillSuggestion('${q.replace(/'/g, "\\'")}')" class="w-full text-left bg-white hover:bg-slate-50 border border-slate-200/80 hover:border-blue-200 text-slate-600 hover:text-blue-600 text-xs px-3 py-2 rounded-xl shadow-xs transition-all flex items-center space-x-1.5 cursor-pointer"><span class="text-blue-500 font-bold">↳</span><span>${q}</span></button>`;
            }).join('');
            eb.classList.remove('hidden');
        }
    } catch(e) { console.log('追问加载失败'); }
})(); break; } try { const parsed = JSON.parse(dataContent); if (parsed.text) { clearInterval(visualTimer); if (accumulatedText === "") textContainer.innerHTML = ""; let formattedChunk = parsed.text; accumulatedText += formattedChunk; textContainer.textContent = accumulatedText; scrollToBottom(); } } catch (e) { console.error("流块 JSON 解析失败:", e); } } } } } catch (error) { clearInterval(visualTimer); console.error('流式传输失败:', error); textContainer.innerHTML = '⚠️ 系统连接大模型超时或流数据中断，请稍后重试。'; if (conversationHistory.length > 0 && conversationHistory[conversationHistory.length - 1].role === 'user') { conversationHistory.pop(); updateContextUI(); } } finally { userInput.disabled = false; sendBtn.disabled = false; sendBtn.innerHTML = '<span>发送</span>'; userInput.focus(); scrollToBottom(); } }
function handleStarClick(msgId, score) { activeRatings[msgId] = score; const container = document.getElementById(`container-${msgId}`); const stars = container.querySelectorAll('.star-btn'); stars.forEach((star, index) => { if (index < score) star.classList.add('star-active'); else star.classList.remove('star-active'); }); const statusTxt = document.getElementById(`status-${msgId}`); const textMap = {1: '很不准确 ☹️', 2: '不太严谨 🙁', 3: '基本符合 😐', 4: '完全准确 🙂', 5: '非常专业 😍'}; statusTxt.innerText = textMap[score] || ''; document.getElementById(`comment-box-${msgId}`).classList.remove('hidden'); scrollToBottom(); }
async function submitAllFeedback(msgId) { const score = activeRatings[msgId]; if (!score) return; const comment = document.getElementById(`textarea-${msgId}`).value.trim(); const originalQuery = messageQueryMap[msgId] || ""; try { const response = await fetch('/api/v1/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token')||'') }, body: JSON.stringify({ msg_id: msgId, query: originalQuery, score: parseInt(score), comment: comment }) }); const resData = await response.json(); if (response.ok && resData.status === "success") { document.getElementById(`comment-box-${msgId}`).innerHTML = `<p class="text-xs text-emerald-600 font-medium pt-1">✓ 谢谢您的指正，合规专员将及时跟进核验该政策或标准文本。</p>`; } else { alert("同步数据库失败，请检查后端 MongoDB 连接状况。"); } } catch (err) { console.error("提交反馈出错:", err); alert("网络连接异常，无法写入本地数据库。"); } }
function fillSuggestion(text) { const inputField = document.getElementById('userInput'); if (inputField && !inputField.disabled) { inputField.value = text; inputField.focus(); handleSend(); } }
function downloadContent(msgId) { const content = messageContentMap[msgId]; if (!content) { alert('暂无内容可下载'); return; } const blob = new Blob([content], { type: 'text/plain;charset=utf-8' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `政策解答_${new Date().toISOString().slice(0,10)}.txt`; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url); }
sendBtn.addEventListener('click', handleSend);
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) handleSend();
    }
});

/* ========== 文件上传 ========== */
var uploadedFileContent = null;
var uploadedFileName = null;

async function openFilePicker(){
    // 优先使用 File System Access API（不卡）
    if (window.showOpenFilePicker) {
        try {
            var handle = await window.showOpenFilePicker({
                types: [{
                    description: '文档文件',
                    accept: {
                        'application/pdf': ['.pdf'],
                        'application/msword': ['.doc'],
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
                        'text/plain': ['.txt'],
                        'application/vnd.ms-excel': ['.xls'],
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
                        'text/csv': ['.csv'],
                        'image/png': ['.png'],
                        'image/jpeg': ['.jpg', '.jpeg']
                    }
                }]
            });
            var file = await handle[0].getFile();
            if (file.size > 10 * 1024 * 1024) { alert('文件大小不能超过 10MB'); return; }
            await readFileContent(file);
            return;
        } catch(e) {
            if (e.name === 'AbortError') return; // 用户取消
        }
    }
    // 降级到传统方式
    var fu = document.getElementById('fileUpload');
    if(fu) fu.click();
}
function handleFileSelect(input){
    var file = input.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { alert('文件大小不能超过 10MB'); input.value = ''; return; }
    readFileContent(file);
}
function readFileContent(file){
    uploadedFileName = file.name;
    var reader = new FileReader();
    reader.onload = function(e){
        uploadedFileContent = e.target.result;
        showFilePreview(file);
    };
    reader.onerror = function(){
        alert('文件读取失败');
    };
    reader.readAsText(file);
}
function showFilePreview(file){
    var ext = file.name.split('.').pop().toLowerCase();
    var icons = { pdf:'📄',doc:'📝',docx:'📝',txt:'📃',xls:'📊',xlsx:'📊',csv:'📊',png:'🖼️',jpg:'🖼️',jpeg:'🖼️' };
    var icon = icons[ext] || '📎';
    var size = file.size < 1024 ? file.size+' B' : file.size < 1048576 ? (file.size/1024).toFixed(1)+' KB' : (file.size/1048576).toFixed(1)+' MB';
    var c = document.getElementById('filePreviewContainer');
    if (!c) return;
    c.innerHTML = '<div class="flex items-center space-x-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-sm"><span class="text-lg">'+icon+'</span><span class="text-slate-700 truncate max-w-[200px]">'+file.name+'</span><span class="text-slate-400 text-xs">'+size+'</span><button onclick="removeFile()" class="ml-auto text-slate-400 hover:text-red-500 cursor-pointer"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></button></div>';
    c.classList.remove('hidden');
    // 隐藏拖拽区域
    var dz = document.getElementById('dropZone');
    if(dz) dz.classList.add('hidden');
}
function removeFile(){
    uploadedFileContent = null;
    uploadedFileName = null;
    var fu = document.getElementById('fileUpload');
    if(fu) fu.value = '';
    var c = document.getElementById('filePreviewContainer');
    if(c){ c.innerHTML = ''; c.classList.add('hidden'); }
}

/* ========== 拖拽上传 ========== */
(function(){
    var dz = document.getElementById('dropZone');
    if(!dz) return;

    // 显示拖拽区域
    window.showDropZone = function(){
        dz.classList.remove('hidden');
    };
    window.hideDropZone = function(){
        dz.classList.add('hidden');
    };

    // 阻止默认拖拽行为
    document.addEventListener('dragover', function(e){
        e.preventDefault();
        e.stopPropagation();
        document.body.classList.add('drag-over');
    });
    document.addEventListener('dragleave', function(e){
        e.preventDefault();
        e.stopPropagation();
        document.body.classList.remove('drag-over');
    });
    document.addEventListener('drop', function(e){
        e.preventDefault();
        e.stopPropagation();
        document.body.classList.remove('drag-over');
        dz.classList.add('hidden');
        var files = e.dataTransfer.files;
        if(files.length > 0){
            var file = files[0];
            if(file.size > 10 * 1024 * 1024){
                alert('文件大小不能超过 10MB');
                return;
            }
            readFileContent(file);
        }
    });
})();

/* ========== 工具管理 ========== */
let selectedToolId = '';
let toolsData = [];

async function loadTools() {
    try {
        const r = await fetch('/api/v1/tools/', {
            headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('token') || '') }
        });
        const d = await r.json();
        toolsData = d.tools || [];
        renderToolSelect();
    } catch (e) {
        console.error('加载工具失败:', e);
    }
}

function renderToolSelect() {
    const select = document.getElementById('toolSelect');
    if (!select) return;
    
    // 保留第一个"未选择工具"选项
    select.innerHTML = '<option value="">未选择工具</option>';
    
    toolsData.forEach(function (t) {
        const option = document.createElement('option');
        option.value = t.id;
        option.textContent = t.name;
        if (t.id === selectedToolId) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    updateToolInfo();
}

function updateToolInfo() {
    const infoBox = document.getElementById('selectedToolInfo');
    const nameEl = document.getElementById('selectedToolName');
    const promptEl = document.getElementById('selectedToolPrompt');
    
    if (!selectedToolId) {
        infoBox.classList.add('hidden');
        return;
    }
    
    const tool = toolsData.find(function (t) { return t.id === selectedToolId; });
    if (tool) {
        nameEl.textContent = tool.name;
        promptEl.textContent = tool.prompt.length > 60 ? tool.prompt.substring(0, 60) + '...' : tool.prompt;
        infoBox.classList.remove('hidden');
    }
}

function onToolChange() {
    const select = document.getElementById('toolSelect');
    selectedToolId = select.value;
    updateToolInfo();
}

function clearToolSelection() {
    selectedToolId = '';
    const select = document.getElementById('toolSelect');
    if (select) select.value = '';
    updateToolInfo();
}

function editSelectedTool() {
    if (!selectedToolId) return;
    const tool = toolsData.find(function (t) { return t.id === selectedToolId; });
    if (tool) {
        document.getElementById('toolEditId').value = tool.id;
        document.getElementById('toolName').value = tool.name;
        document.getElementById('toolPrompt').value = tool.prompt;
        document.getElementById('toolModalTitle').textContent = '编辑工具';
        document.getElementById('toolModal').classList.remove('hidden');
        document.getElementById('toolModal').classList.add('flex');
    }
}

function deleteSelectedTool() {
    if (!selectedToolId) return;
    deleteTool(selectedToolId);
}

function openToolModal() {
    document.getElementById('toolEditId').value = '';
    document.getElementById('toolName').value = '';
    document.getElementById('toolPrompt').value = '';
    document.getElementById('toolModalTitle').textContent = '添加工具';
    document.getElementById('toolModal').classList.remove('hidden');
    document.getElementById('toolModal').classList.add('flex');
}

function editTool(id) {
    const tool = toolsData.find(function (t) { return t.id === id; });
    if (!tool) return;
    document.getElementById('toolEditId').value = id;
    document.getElementById('toolName').value = tool.name;
    document.getElementById('toolPrompt').value = tool.prompt;
    document.getElementById('toolModalTitle').textContent = '编辑工具';
    document.getElementById('toolModal').classList.remove('hidden');
    document.getElementById('toolModal').classList.add('flex');
}

function closeToolModal() {
    document.getElementById('toolModal').classList.add('hidden');
    document.getElementById('toolModal').classList.remove('flex');
}

async function saveTool() {
    const id = document.getElementById('toolEditId').value;
    const name = document.getElementById('toolName').value.trim();
    const prompt = document.getElementById('toolPrompt').value.trim();
    if (!name || !prompt) { alert('请填写工具名称和系统提示词'); return; }

    const headers = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token') || '') };
    try {
        if (id) {
            await fetch('/api/v1/tools/' + id, { method: 'PUT', headers: headers, body: JSON.stringify({ name: name, prompt: prompt }) });
        } else {
            await fetch('/api/v1/tools/', { method: 'POST', headers: headers, body: JSON.stringify({ name: name, prompt: prompt }) });
        }
        closeToolModal();
        await loadTools();
    } catch (e) {
        console.error('保存工具失败:', e);
        alert('保存失败，请重试');
    }
}

async function deleteTool(id) {
    if (!confirm('确定删除该工具？')) return;
    try {
        await fetch('/api/v1/tools/' + id, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('token') || '') }
        });
        if (selectedToolId === id) {
            selectedToolId = '';
            const select = document.getElementById('toolSelect');
            if (select) select.value = '';
        }
        await loadTools();
    } catch (e) {
        console.error('删除工具失败:', e);
    }
}

document.addEventListener('click', function (e) {
    if (e.target.id === 'toolModal') closeToolModal();
});

// 页面加载时获取工具列表
loadTools();
