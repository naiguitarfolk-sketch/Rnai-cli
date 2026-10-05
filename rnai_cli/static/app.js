let sid = null;
const $ = id => document.getElementById(id);

function toggleMobileSidebar() {
  const side = $('side');
  const bd = $('sideBackdrop');
  if (side && side.classList.contains('show')) {
    closeMobileSidebar();
  } else {
    if (side) side.classList.add('show');
    if (bd) bd.classList.add('show');
  }
}

function closeMobileSidebar() {
  const side = $('side');
  const bd = $('sideBackdrop');
  if (side) side.classList.remove('show');
  if (bd) bd.classList.remove('show');
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

let currentSelectedIntent = '📊 วิจัยและวิเคราะห์ข้อมูล';
let currentMemorySid = null;

async function loadRecents() {
  const el = $('recents');
  if (!el) return;
  try {
    const r = await fetch('/api/sessions');
    if (!r.ok) return;
    const list = await r.json();
    if (!Array.isArray(list)) return;
    el.innerHTML = list.map(s => {
      const intentChip = s.intent
        ? `<span class="recent-intent-chip" title="${esc(s.intent)}">${esc(s.intent.split(' ')[0] || s.intent.slice(0, 8))}</span>`
        : '';
      return `<div class="recent ${s.id===sid?'active':''}" onclick="openSession('${s.id}')">
          <div style="display:flex; align-items:center; justify-content:space-between; gap:4px;">
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">${esc(s.title)}</span>
            ${intentChip}
          </div>
          <small>${s.count} ข้อความ · ${ago(s.updated)}</small>
          <button class="del" title="ลบ" onclick="delSession(event,'${s.id}')">✕</button>
        </div>`;
    }).join('');
  } catch(e) {}
}

async function openSession(id) {
  sid = id;
  closeMobileSidebar();
  try {
    const r = await fetch('/api/sessions/' + id);
    const d = await r.json();
    $('thread').innerHTML = '';
    if (d.messages && Array.isArray(d.messages)) {
      d.messages.forEach(m => addMsg(m.role, m.content, m.model));
    }
    updateProjectMemoryBanner(d);
    loadRecents();
    scrollBottom();
  } catch(e) {
    console.error('Failed to open session', e);
  }
}

async function delSession(ev, id) {
  ev.stopPropagation();
  await fetch('/api/sessions/' + id, { method:'DELETE' });
  if (sid === id) {
    sid = null;
    const banner = $('projectMemoryBanner');
    if (banner) banner.style.display = 'none';
    quickStartChat();
  } else {
    loadRecents();
  }
}

function updateProjectMemoryBanner(data) {
  const banner = $('projectMemoryBanner');
  if (!banner) return;
  if (data && (data.intent || data.folder_path || (data.title && data.title !== 'สนทนาใหม่'))) {
    banner.style.display = 'flex';
    if ($('pmBannerTitle')) $('pmBannerTitle').textContent = data.title || 'โครงการ';
    if ($('pmBannerIntent')) {
      $('pmBannerIntent').textContent = data.intent || '🎯 ทั่วไป';
      $('pmBannerIntent').style.display = data.intent ? 'inline-block' : 'none';
    }
    if ($('pmBannerFolder')) {
      const fp = data.folder_path ? data.folder_path.replace(/^\/Users\/[^\/]+/, '~') : '-';
      $('pmBannerFolder').textContent = '📁 ' + fp;
      $('pmBannerFolder').title = data.folder_path || '';
    }
  } else {
    banner.style.display = 'none';
  }
}

function newChat() {
  openNewChatIntentModal();
}

function openNewChatIntentModal() {
  const modal = $('newChatIntentModal');
  if (!modal) {
    quickStartChat();
    return;
  }
  closeMobileSidebar();

  // รีเซ็ตค่าในฟอร์ม
  if ($('intentProjTitle')) $('intentProjTitle').value = '';
  if ($('intentContextText')) $('intentContextText').value = '';

  const isStudent = window.location.pathname.includes('student') || document.title.includes('มสธ') || !!$('stuUploadBtn');
  const defaultIntent = isStudent ? '🎓 ติวเตอร์และแผนการเรียนรู้' : '📊 วิจัยและวิเคราะห์ข้อมูล';
  const defaultPrompt = isStudent
    ? 'ช่วยวางแผนการเรียนรู้ประจำสัปดาห์ แนะนำแนวทางการอ่านหนังสือ และสรุปสาระสำคัญ'
    : 'ช่วยอ่าน ศึกษาวิเคราะห์ คำนวณตัวเลขและสถิติจากเอกสาร พร้อมสรุปประเด็นสำคัญ';

  const defaultFolder = isStudent ? '~/RnaiWorkspace/student/' : '~/RnaiWorkspace/projects/';
  if ($('intentFolderPath')) $('intentFolderPath').value = defaultFolder;
  if ($('intentCreateMemory')) $('intentCreateMemory').checked = true;

  // ไฮไลต์การ์ดที่เลือกเริ่มต้น
  const cards = modal.querySelectorAll('.intent-card');
  cards.forEach(c => {
    const text = c.textContent || '';
    if (text.includes(defaultIntent.split(' ')[1] || defaultIntent)) {
      c.classList.add('selected');
    } else {
      c.classList.remove('selected');
    }
  });
  currentSelectedIntent = defaultIntent;
  if ($('intentPromptText')) $('intentPromptText').value = defaultPrompt;

  modal.classList.add('show');
  setTimeout(() => {
    if ($('intentProjTitle')) $('intentProjTitle').focus();
  }, 100);
}

function selectIntentCard(cardEl, intentName, defaultPrompt) {
  const modal = $('newChatIntentModal');
  if (!modal) return;
  modal.querySelectorAll('.intent-card').forEach(c => c.classList.remove('selected'));
  if (cardEl) cardEl.classList.add('selected');
  currentSelectedIntent = intentName;
  if ($('intentPromptText')) $('intentPromptText').value = defaultPrompt;
  updateIntentFolderSuggestion();
}

function updateIntentFolderSuggestion() {
  const titleInput = $('intentProjTitle');
  const folderInput = $('intentFolderPath');
  if (!titleInput || !folderInput) return;
  const title = titleInput.value.trim();
  const isStudent = window.location.pathname.includes('student') || document.title.includes('มสธ') || !!$('stuUploadBtn');
  const baseDir = isStudent ? '~/RnaiWorkspace/student/' : '~/RnaiWorkspace/projects/';

  if (!title) {
    folderInput.value = baseDir;
    return;
  }
  const slug = title.replace(/[\\/*?:"<>|#%&{}\\$!\'=@`+]/g, '').trim().replace(/[\s_]+/g, '-');
  folderInput.value = baseDir + (slug || 'project');
}

function closeIntentModal() {
  const modal = $('newChatIntentModal');
  if (modal) modal.classList.remove('show');
}

function quickStartChat() {
  closeIntentModal();
  sid = null;
  const banner = $('projectMemoryBanner');
  if (banner) banner.style.display = 'none';

  const thread = $('thread');
  if (thread) {
    thread.innerHTML = `
      <div id="empty">
        <svg width="56" height="56" viewBox="0 0 512 512" style="margin-bottom:16px"><rect width="512" height="512" rx="116" fill="#0B3945"/><path d="M196 196v160" stroke="#fff" stroke-width="62" stroke-linecap="round"/><path d="M196 300q0-104 110-104" stroke="#fff" stroke-width="62" stroke-linecap="round" fill="none"/><circle cx="382" cy="196" r="34" fill="#D77757"/></svg>
        <h2 id="emptyTitle">คุยกับ Rnai ได้เลย</h2>
        <p id="emptyDesc">โมเดลของคุณเอง รันบนเครื่อง ประวัติเก็บในเครื่อง</p>
        <div class="chips" id="emptyChips"></div>
      </div>`;
    if (typeof renderChips === 'function') renderChips();
  }
  loadRecents();
  if ($('input')) $('input').focus();
}

async function submitNewChatWithIntent() {
  const btn = $('btnSubmitIntent');
  const title = ($('intentProjTitle') ? $('intentProjTitle').value.trim() : '') || 'การสนทนาใหม่';
  const intent = currentSelectedIntent || '📊 วิจัยและวิเคราะห์ข้อมูล';
  const prompt = $('intentPromptText') ? $('intentPromptText').value.trim() : '';
  const context = $('intentContextText') ? $('intentContextText').value.trim() : '';
  const folder = $('intentFolderPath') ? $('intentFolderPath').value.trim() : '';
  const createMemory = $('intentCreateMemory') ? $('intentCreateMemory').checked : true;
  const modelName = $('model') ? $('model').value : 'rnai';

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ กำลังสร้างโครงการ...';
  }

  try {
    const res = await fetch('/api/sessions/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        intent: intent,
        prompt: prompt,
        context: context,
        folder_path: folder,
        model: modelName,
        create_folder: true,
        create_memory: createMemory
      })
    });
    const data = await res.json();
    if (!data.ok && !data.session_id) {
      alert('ไม่สามารถสร้างเซสชันได้: ' + (data.error || 'unknown error'));
      return;
    }

    sid = data.session_id || data.id;
    closeIntentModal();

    // ล้างหน้าต่างแชทและแสดงการ์ดต้อนรับโครงการ
    $('thread').innerHTML = '';
    updateProjectMemoryBanner(data);

    // แสดง Welcome message ใน Thread
    addMsg('bot',
      `🌟 **เริ่มต้นโปรเจกต์ใหม่: ${data.title}**\n\n` +
      `🎯 **ความจำนง/เป้าหมาย:** ${data.intent}\n` +
      (data.folder_path ? `📁 **โฟลเดอร์เอกสาร:** \`${data.folder_path}\`\n` : '') +
      (data.memory_path ? `🧠 **ไฟล์ความจำ:** \`${data.memory_path}\` *(อัปเดตอัตโนมัติทุกครั้งที่มีการสนทนา)*\n\n` : '') +
      (prompt ? `💬 **คำสั่งเริ่มต้นที่ตั้งไว้:**\n> ${prompt}\n\n` : '') +
      `ระบบบันทึกโปรเจกต์ลงใน Recents แล้ว และพร้อมให้คุณเริ่มสนทนา ลากไฟล์เอกสารมาวิเคราะห์ หรือสั่งการได้ทันที!`
    );

    // วาง prompt ลงใน input เพื่อความสะดวกในการเริ่มสนทนา
    if ($('input') && prompt) {
      $('input').value = prompt;
      if (typeof autosize === 'function') autosize();
      $('input').focus();
    }

    loadRecents();
    scrollBottom();
  } catch(e) {
    alert('เกิดข้อผิดพลาดในการสร้างเซสชัน: ' + e);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🚀 เริ่มต้นการสนทนาและสร้าง Memory.md';
    }
  }
}

async function openMemoryViewer(sessionId) {
  const targetSid = sessionId || sid;
  if (!targetSid) {
    alert('ยังไม่มีการสนทนาที่เลือกอยู่ในขณะนี้');
    return;
  }
  currentMemorySid = targetSid;
  const modal = $('memoryViewerModal');
  if (!modal) return;

  $('memViewMeta').textContent = 'กำลังโหลดเนื้อหา Memory.md...';
  $('memViewBody').textContent = 'กำลังดึงข้อมูล...';
  modal.classList.add('show');

  try {
    const res = await fetch(`/api/sessions/${targetSid}/memory`);
    const data = await res.json();
    if (!data.ok) {
      $('memViewMeta').innerHTML = `⚠️ <span style="color:#d9534f">${esc(data.error || 'ไม่พบไฟล์ Memory.md')}</span>`;
      $('memViewBody').textContent = '(เซสชันนี้ยังไม่มีไฟล์ Memory.md บันทึกไว้ หรือยังไม่ได้สร้างโฟลเดอร์โครงการ)';
      return;
    }
    $('memViewMeta').innerHTML = `📁 ตำแหน่งไฟล์: <code>${esc(data.path)}</code> · อัปเดตล่าสุด: ${ago(data.updated)}`;
    $('memViewBody').textContent = data.content || '(ไฟล์ว่าง)';
  } catch(e) {
    $('memViewMeta').textContent = 'เกิดข้อผิดพลาดในการโหลด: ' + e;
    $('memViewBody').textContent = '';
  }
}

async function refreshMemoryViewer() {
  if (currentMemorySid) openMemoryViewer(currentMemorySid);
}

function copyMemoryContent() {
  const content = $('memViewBody') ? $('memViewBody').textContent : '';
  if (!content) return;
  navigator.clipboard.writeText(content).then(() => {
    alert('คัดลอกเนื้อหา Memory.md เรียบร้อยแล้ว!');
  }).catch(() => {
    alert('ไม่สามารถคัดลอกได้');
  });
}
function fill(text){ $('input').value = text; $('input').focus(); }
function addMsg(role, text, model) {
  const e = $('empty'); if (e) e.remove();
  const turn = document.createElement('div');
  turn.className = 'turn ' + (role === 'user' ? 'user' : 'bot');
  const who = document.createElement('div'); who.className = 'who'; who.textContent = 'Rnai';
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
  turn.appendChild(who); turn.appendChild(bubble);
  if (role !== 'user' && model) {
    const meta = document.createElement('div'); meta.className = 'meta'; meta.textContent = model;
    turn.appendChild(meta);
  }
  $('thread').appendChild(turn); return bubble;
}
/* ── Mode: chat / cowork ── */
let agentMode = false;
const CHIPS = {
  chat: [
    ["💰 วางแผนเก็บเงิน", "วางแผนเก็บเงินเดือนละ 5,000 ให้หน่อย"],
    ["✉️ ร่างอีเมล", "ช่วยร่างอีเมลขอเลื่อนนัดประชุม"],
    ["📊 ถามความรู้", "สรุปหลัก 50/30/20 สั้นๆ"],
  ],
  cowork: [
    ["🔎 ค้นข่าววันนี้", "ค้นข่าว AI ที่น่าสนใจวันนี้ สรุปเป็นภาษาไทย 3 ข้อ บันทึกเป็นไฟล์ ainews.md"],
    ["📄 สรุปไฟล์", "อ่านไฟล์ ~/Downloads/เอกสาร.txt แล้วสรุปประเด็นสำคัญเป็นภาษาไทย"],
    ["💹 เทียบราคา", "ค้นราคาทองคำกับ USD/THB วันนี้ ทำตารางเทียบ บันทึกเป็นไฟล์ market.md"],
  ],
};
function renderChips(){
  const el = $('emptyChips');
  if (!el) return;
  const mode = agentMode ? 'cowork' : 'chat';
  el.innerHTML = CHIPS[mode].map(c =>
    `<button class="chip" onclick="fill(${JSON.stringify(c[1]).replace(/"/g,'&quot;')})">${c[0]}</button>`).join('');
}

function setMode(mode){
  agentMode = (mode === 'cowork');
  $('mode-chat').classList.toggle('on', !agentMode);
  $('mode-cowork').classList.toggle('on', agentMode);
  $('main').classList.toggle('cowork', agentMode);
  $('modedesc').textContent = agentMode
    ? 'ค้นเว็บ · จัดการไฟล์ · เรียก skills — agent ทำงานหลายขั้นและขออนุมัติก่อนแก้ไข'
    : 'คุยกับโมเดลอย่างเดียว — ตอบเร็ว ไม่ใช้เครื่องมือ';
  $('input').placeholder = agentMode
    ? '🛠 สั่งงาน Cowork — เช่น "ค้นข่าววันนี้ สรุปเป็นไฟล์"...'
    : 'พิมพ์ข้อความถึง Rnai...';
  $('emptyTitle').textContent = agentMode ? 'Cowork — ผู้ช่วยลงมือทำ' : 'คุยกับ Rnai ได้เลย';
  $('emptyDesc').textContent = agentMode
    ? 'สั่งงานที่ต้องค้นข้อมูล จัดการไฟล์ หรือทำหลายขั้นตอน แล้วดู agent ทำให้ทีละสเต็ป'
    : 'โมเดลของคุณเอง รันบนเครื่อง ประวัติเก็บในเครื่อง';
  renderChips();
  if (agentMode) loadFolder();
}

/* ── Agent (Real-time Streaming SSE with polling fallback) ── */
async function sendAgent(text) {
  addMsg('user', text);
  const stepsDiv = document.createElement('div'); stepsDiv.className = 'steps';
  stepsDiv.innerHTML = '<span class="tl">🛠 agent เริ่มทำงาน...</span>';
  $('thread').appendChild(stepsDiv); scrollBottom();
  try {
    const r = await fetch('/api/agent', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ session_id: sid, message: text }) });
    if (!r.ok) throw new Error('ไม่พบเซิร์ฟเวอร์ Local Agent');
    const d = await r.json();
    if (d.error) { stepsDiv.remove(); const b = addMsg('bot', d.error); b.classList.add('err');
      $('send').disabled = false; return; }
    sid = d.session_id;

    let apDiv = null, shown = 0;

    // Try Real-time EventSource (SSE)
    if ('EventSource' in window) {
      const sse = new EventSource('/api/agent/stream?id=' + d.job_id);
      sse.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'step') {
            const line = document.createElement('div');
            line.className = data.kind === 'tool' ? 'tl' : 'rs';
            line.textContent = (data.kind === 'tool' ? '🔧 ' : '   ↳ ') + data.text;
            stepsDiv.appendChild(line); scrollBottom();
          } else if (data.type === 'pending') {
            if (!apDiv) {
              apDiv = document.createElement('div'); apDiv.className = 'approvebox';
              apDiv.innerHTML = `<div class="ttl">⚠️ agent ขออนุญาต: ${esc(data.pending.title)}</div>
                <pre>${esc(data.pending.preview||'')}</pre>
                <button class="ap-ok" onclick="approve('${d.job_id}',true,this)">อนุญาต</button>
                <button class="ap-no" onclick="approve('${d.job_id}',false,this)">ปฏิเสธ</button>`;
              $('thread').appendChild(apDiv); scrollBottom();
            }
          } else if (data.type === 'pending_clear') {
            if (apDiv) { apDiv.remove(); apDiv = null; }
          } else if (data.type === 'done') {
            sse.close();
            if (apDiv) apDiv.remove();
            addMsg('bot', data.answer, 'agent');
            $('send').disabled = false;
            loadRecents(); scrollBottom();
          }
        } catch(e) {}
      };
      sse.onerror = () => {
        sse.close();
        // Fallback to polling if SSE encounters an error
        startPollingAgent(d.job_id, stepsDiv);
      };
    } else {
      startPollingAgent(d.job_id, stepsDiv);
    }
  } catch(e) {
    stepsDiv.remove();
    const b = addMsg('bot', '⚠️ โหมด Agent (Cowork) เป็นโหมดที่ต้องรันคำสั่งและจัดการไฟล์ในคอมพิวเตอร์ของคุณ\n\n'
      + '• หากคุณใช้งานผ่าน Netlify: กรุณาสลับเป็นโหมด Chat (ปุ่ม 💬 Chat มุมซ้ายบน) เพื่อคุยผ่าน Cloud AI (Gemini / Groq / HuggingFace)\n'
      + '• หากต้องการใช้ Agent ช่วยเขียนไฟล์/รันคำสั่งในเครื่อง: เปิด Terminal บนคอมพิวเตอร์ของคุณแล้วรันคำสั่ง: "rnai ui --remote"');
    b.classList.add('err');
    $('send').disabled = false;
  }
}

function startPollingAgent(jobId, stepsDiv) {
  let apDiv = null, shown = 0;
  const poll = setInterval(async () => {
    try {
      const s = await (await fetch('/api/agent/status?id=' + jobId)).json();
      while (shown < s.steps.length) {
        const st = s.steps[shown++];
        const line = document.createElement('div');
        line.className = st.kind === 'tool' ? 'tl' : 'rs';
        line.textContent = (st.kind === 'tool' ? '🔧 ' : '   ↳ ') + st.text;
        stepsDiv.appendChild(line); scrollBottom();
      }
      if (s.pending && !apDiv) {
        apDiv = document.createElement('div'); apDiv.className = 'approvebox';
        apDiv.innerHTML = `<div class="ttl">⚠️ agent ขออนุญาต: ${esc(s.pending.title)}</div>
          <pre>${esc(s.pending.preview||'')}</pre>
          <button class="ap-ok" onclick="approve('${jobId}',true,this)">อนุญาต</button>
          <button class="ap-no" onclick="approve('${jobId}',false,this)">ปฏิเสธ</button>`;
        $('thread').appendChild(apDiv); scrollBottom();
      }
      if (!s.pending && apDiv) { apDiv.remove(); apDiv = null; }
      if (s.status !== 'running') {
        clearInterval(poll); if (apDiv) apDiv.remove();
        addMsg('bot', s.answer, 'agent'); $('send').disabled = false;
        loadRecents(); scrollBottom();
      }
    } catch(e) { clearInterval(poll); }
  }, 1000);
}

/* ── Projects ── */
async function loadProjects(){
  const d = await (await fetch('/api/projects')).json();
  $('projects').innerHTML = d.projects.map(p => `
    <div class="proj ${p.active?'active':''}" onclick="switchProject('${esc(p.path)}')" title="${esc(p.path)}">
      <span class="ic">${p.active?'📂':'📁'}</span>
      <span class="nm">${esc(p.name||'workspace')}</span>
      ${p.active?'<span class="dot2"></span>':''}
      <button class="x" title="เอาออกจากรายการ" onclick="removeProject(event,'${esc(p.path)}')">✕</button>
    </div>`).join('');
}
async function switchProject(path){
  await fetch('/api/projects', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ path }) });
  loadProjects();
  if (agentMode) loadFolder();
  toast('เปิดโปรเจกต์: ' + path.split('/').pop());
}
function openNewProject(){
  const name = prompt('ชื่อโปรเจกต์ใหม่ (จะสร้างโฟลเดอร์ใน ~/RnaiProjects/)\nหรือใส่ path เต็มก็ได้:');
  if (!name) return;
  const path = name.includes('/') ? name : '~/RnaiProjects/' + name;
  fetch('/api/projects', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ path, create: true }) })
    .then(r=>r.json()).then(d=>{
      if (d.ok) { loadProjects(); if (agentMode) loadFolder();
        if (!agentMode) setMode('cowork'); toast('สร้างโปรเจกต์แล้ว: ' + path.split('/').pop()); }
      else alert(d.error || 'สร้างไม่สำเร็จ');
    });
}
async function removeProject(ev, path){
  ev.stopPropagation();
  await fetch('/api/projects/remove', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ path }) });
  loadProjects();
}
function toast(msg){
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id='toast'; document.body.appendChild(t);
    t.style.cssText='position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#171717;color:#fff;padding:9px 18px;border-radius:99px;font-size:13px;z-index:100;opacity:0;transition:.2s'; }
  t.textContent = msg; t.style.opacity='1';
  clearTimeout(t._h); t._h = setTimeout(()=>t.style.opacity='0', 1800);
}

/* ── Attach file/folder ── */
let apSrc = 'ws';   // 'ws' = โฟลเดอร์ทำงาน | 'any' = ทั้งเครื่อง
let apSub = '';     // subfolder (โหมด ws)
let apAbs = '';     // absolute dir ปัจจุบัน (โหมด any)
let apAbsRoot = false;
async function toggleAttach(ev){
  ev.stopPropagation();
  const pop = $('attachpop');
  if (pop.classList.contains('show')) { pop.classList.remove('show'); return; }
  apSub = ''; apAbs = ''; await renderAttach(); pop.classList.add('show');
}
function apSetSrc(src){
  apSrc = src; apSub = ''; apAbs = '';
  $('aptab-ws').classList.toggle('on', src==='ws');
  $('aptab-any').classList.toggle('on', src==='any');
  $('apInput').placeholder = src==='ws' ? 'วาง path (relative จาก workspace)' : 'วาง path เต็ม เช่น /Users/you/file.pdf';
  renderAttach();
}
async function renderAttach(){
  let d, up = false, upLabel = '.. ย้อนกลับ';
  if (apSrc === 'ws') {
    d = await (await fetch('/api/workspace' + (apSub?'?sub='+encodeURIComponent(apSub):''))).json();
    $('apdir').textContent = homeShort(d.dir) + (apSub?'/'+apSub:'');
    up = !!apSub;
  } else {
    d = await (await fetch('/api/browse' + (apAbs?'?path='+encodeURIComponent(apAbs):''))).json();
    apAbs = d.dir; apAbsRoot = d.atRoot;
    $('apdir').textContent = homeShort(d.dir);
    up = !d.atRoot;
  }
  let html = '';
  if (up) html += `<div class="apitem" onclick="apUp()"><span>↩︎</span><span class="nm">${upLabel}</span></div>`;
  if (!d.entries.length && !up) html += '<div class="apempty">โฟลเดอร์ว่าง</div>';
  html += d.entries.map(e => e.dir
    ? `<div class="apitem" onclick="apOpen('${esc(e.name)}')"><span>📁</span><span class="nm">${esc(e.name)}</span><span class="go">เปิด ›</span></div>`
    : `<div class="apitem" onclick="apPick('${esc(e.name)}')"><span>📄</span><span class="nm">${esc(e.name)}</span><span class="go">แนบ</span></div>`
  ).join('');
  html += `<div class="apitem" onclick="apPickFolder()" style="border-top:1px solid var(--line);margin-top:6px;color:var(--brand-ink)">
             <span>📎</span><span class="nm">แนบทั้งโฟลเดอร์นี้</span></div>`;
  $('aplist').innerHTML = html;
}
function apOpen(name){
  if (apSrc === 'ws') apSub = apSub ? apSub+'/'+name : name;
  else apAbs = apAbs.replace(/\/$/, '') + '/' + name;
  renderAttach();
}
function apUp(){
  if (apSrc === 'ws') apSub = apSub.includes('/') ? apSub.slice(0, apSub.lastIndexOf('/')) : '';
  else apAbs = apAbs.slice(0, apAbs.lastIndexOf('/')) || '/';
  renderAttach();
}
function apInsert(ref){
  const cur = $('input').value;
  $('input').value = (cur ? cur.replace(/\s*$/, '') + ' ' : '') + '`' + ref + '` ';
  $('input').focus(); autosize();
  $('attachpop').classList.remove('show');
}
function apPick(name){
  const ref = apSrc === 'ws' ? (apSub?apSub+'/':'')+name : apAbs.replace(/\/$/, '')+'/'+name;
  apInsert(ref);
}
function apPickFolder(){
  const ref = apSrc === 'ws' ? (apSub||'.')+'/' : apAbs.replace(/\/$/, '')+'/';
  apInsert(ref);
}
document.addEventListener('DOMContentLoaded', ()=>{});
$('apInput') && $('apInput').addEventListener('keydown', e=>{
  if (e.key === 'Enter') { e.preventDefault(); const v = e.target.value.trim(); if (v) apInsert(v); e.target.value=''; }
});
document.addEventListener('click', e => {
  const pop = $('attachpop');
  if (pop && pop.classList.contains('show') && !pop.contains(e.target) && e.target.id !== 'attach')
    pop.classList.remove('show');
});

/* ── Workspace folder ── */
function homeShort(p){ return p.replace(/^\/Users\/[^/]+/, '~').replace(/^\/home\/[^/]+/, '~'); }
async function loadFolder(){
  const d = await (await fetch('/api/workspace')).json();
  $('folderPath').textContent = homeShort(d.dir);
  return d;
}
async function openFolder(){
  const d = await loadFolder();
  $('fdInput').value = d.dir;
  $('fdFiles').innerHTML = d.entries.length
    ? d.entries.map(e => `<div class="it">${e.dir?'📁':'📄'} ${esc(e.name)}${e.dir?'/':''}</div>`).join('')
    : '<div class="it" style="color:var(--faint)">(โฟลเดอร์ว่าง)</div>';
  $('fdmsg').textContent = '';
  $('folderdlg').classList.add('show');
}
async function saveFolder(){
  const dir = $('fdInput').value.trim();
  const r = await fetch('/api/workspace', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ dir, create: $('fdCreate').checked }) });
  const d = await r.json();
  if (d.ok) { $('folderPath').textContent = homeShort(d.dir); $('folderdlg').classList.remove('show'); }
  else { $('fdmsg').innerHTML = '<span class="err">'+esc(d.error)+'</span>'; }
}

/* ── Rnai.io account (login / เครดิต) ── */
async function loadAccount(){
  let d;
  try {
    const r = await fetch('/api/rnai/account');
    if (r.ok) d = await r.json();
  } catch(e) {}

  if (!d) {
    const email = localStorage.getItem('RNAI_IO_EMAIL');
    const key = localStorage.getItem('RNAI_IO_API_KEY');
    if (email && key) {
      let credits = null;
      try {
        const crRes = await fetch('https://rnai-io.vercel.app/api/billing/me', {
          headers: { 'Authorization': `Bearer ${key}` }
        });
        if (crRes.ok) {
          const crData = await crRes.json();
          const free = crData.freeCreditsRemaining || 0;
          const paid = crData.paidCreditsBalance || 0;
          credits = { freeCreditsRemaining: free, paidCreditsBalance: paid, total: free + paid };
        }
      } catch(e) {}
      d = { loggedIn: true, email: email, keyMasked: key.slice(0,6) + '...' + key.slice(-4), credits: credits };
    } else {
      d = { loggedIn: false };
    }
  }

  const btn = $('acctBtn'); const sideBtn = $('sideAcctBtn');
  if (d.loggedIn) {
    const total = d.credits ? d.credits.total : null;
    const txt = total === null ? '🔌 ' + d.email : '💳 เครดิต: ' + total.toLocaleString();
    if (btn) { btn.textContent = txt; btn.classList.add('linked'); btn.title = 'เข้าสู่ระบบแล้ว: ' + d.email; }
    if (sideBtn) sideBtn.textContent = '👤 ' + d.email;
  } else {
    if (btn) { btn.textContent = '🔌 เข้าสู่ระบบ Rnai.io'; btn.classList.remove('linked'); }
    if (sideBtn) sideBtn.textContent = '🔌 เข้าสู่ระบบ Rnai.io';
  }
  return d;
}
async function openAccount(){
  const d = await loadAccount();
  const loginCard = $('acLoginCard'), acctCard = $('acAccountCard');
  if (d.loggedIn) {
    loginCard.style.display = 'none'; acctCard.style.display = '';
    $('acEmailLabel').textContent = 'เข้าสู่ระบบด้วย: ' + d.email;
    if (d.credits) {
      $('acCreditsBox').innerHTML = 'เครดิตคงเหลือ: <b>' + d.credits.total.toLocaleString() + '</b>'
        + ' (ฟรี ' + (d.credits.freeCreditsRemaining||0).toLocaleString()
        + ' · เติมเงิน ' + (d.credits.paidCreditsBalance||0).toLocaleString() + ')';
    } else {
      $('acCreditsBox').innerHTML = 'เชื่อมต่อบัญชีเรียบร้อยแล้ว: <b>' + esc(d.email) + '</b><br><small style="color:var(--sub);font-size:12px;margin-top:4px;display:block">✓ สถานะระบบพร้อมใช้งาน (สามารถสลับใช้ Gemini / Groq / HuggingFace ได้ฟรี)</small>';
    }
  } else {
    loginCard.style.display = ''; acctCard.style.display = 'none';
    $('acEmail').value = ''; $('acPassword').value = ''; $('acmsg').textContent = '';
  }
  $('accountdlg').classList.add('show');
}
async function doLogin(){
  const email = $('acEmail').value.trim(), password = $('acPassword').value;
  if (!email || !password) { $('acmsg').innerHTML = '<span class="err">กรอกอีเมลและรหัสผ่านให้ครบ</span>'; return; }
  const btn = $('acLoginBtn'); btn.disabled = true; btn.textContent = 'กำลังเข้าสู่ระบบ...';
  try {
    let d;
    try {
      const r = await fetch('/api/rnai/login', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ email, password }) });
      if (r.ok) d = await r.json();
    } catch(e) {}

    // Fallback: Direct Firebase Sign In for Netlify WebApp
    if (!d || !d.ok) {
      const fbKey = atob("QUl6YVN5Q2x2b21tWlJiUDctczBab1U4LWJiNHpLUE1nWko4RlQ0");
      const fbRes = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${fbKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, returnSecureToken: true })
      });
      const fbData = await fbRes.json();
      if (fbData.error) {
        const code = fbData.error.message || 'LOGIN_FAILED';
        const msgs = {
          EMAIL_NOT_FOUND: 'ไม่พบอีเมลนี้ในระบบ Rnai.io',
          INVALID_PASSWORD: 'รหัสผ่านไม่ถูกต้อง',
          INVALID_LOGIN_CREDENTIALS: 'อีเมลหรือรหัสผ่านไม่ถูกต้อง',
          USER_DISABLED: 'บัญชีนี้ถูกระงับการใช้งาน',
          TOO_MANY_ATTEMPTS_TRY_LATER: 'ลองผิดหลายครั้งเกินไป โปรดลองใหม่ภายหลัง'
        };
        throw new Error(msgs[code] || 'เข้าสู่ระบบไม่สำเร็จ: ' + code);
      }

      let apiKey = fbData.idToken;
      try {
        const pkRes = await fetch('https://rnai-io.vercel.app/api/keys', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${fbData.idToken}` },
          body: JSON.stringify({ name: 'Web App Key' })
        });
        const pkData = await pkRes.json();
        if (pkData.key) apiKey = pkData.key;
      } catch(e) {}

      localStorage.setItem('RNAI_IO_API_KEY', apiKey);
      localStorage.setItem('RNAI_IO_EMAIL', fbData.email);
      d = { ok: true, email: fbData.email };
    }

    if (d && d.ok) {
      toast('เข้าสู่ระบบสำเร็จ: ' + d.email);
      $('accountdlg').classList.remove('show');
      loadAccount();
    } else {
      $('acmsg').innerHTML = '<span class="err">' + esc((d && d.error) || 'เข้าสู่ระบบไม่สำเร็จ') + '</span>';
    }
  } catch (e) {
    $('acmsg').innerHTML = '<span class="err">' + esc(String(e.message || e)) + '</span>';
  } finally { btn.disabled = false; btn.textContent = 'เข้าสู่ระบบ'; }
}
async function doLogout(){
  try { await fetch('/api/rnai/logout', { method:'POST' }); } catch(e) {}
  localStorage.removeItem('RNAI_IO_API_KEY');
  localStorage.removeItem('RNAI_IO_EMAIL');
  toast('ออกจากระบบแล้ว');
  $('accountdlg').classList.remove('show');
  loadAccount();
}

async function approve(jobId, ok, btn){
  btn.parentElement.querySelectorAll('button').forEach(b=>b.disabled=true);
  await fetch('/api/agent/approve', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ id: jobId, approve: ok }) });
}

/* ── Tasks view ── */
async function loadTaskList(){
  const tasks = await (await fetch('/api/tasks')).json();
  const tc = $('taskCount'); if (tc) tc.textContent = tasks.length + ' งาน';
  const icon = { ok:'🟢', error:'🔴', running:'🟡' };
  $('tasklist').innerHTML = tasks.length ? tasks.map(t => `
    <div class="taskrow">
      <div class="info">
        <div class="tp">${esc(t.prompt)}</div>
        <div class="tm">${esc(schedTxt(t.schedule))} · รันแล้ว ${t.runs||0} ครั้ง · ${icon[t.last_status]||'⚪'} ${t.last_status||'รอ'}</div>
      </div>
      ${t.last_session ? `<button onclick="openTaskResult('${t.last_session}')">ดูผลล่าสุด</button>` : ''}
      <button onclick="runTaskNow('${t.id}',this)">▶ รันเลย</button>
      <button class="danger" onclick="delTask('${t.id}')">ลบ</button>
    </div>`).join('')
    : '<div style="color:var(--faint);font-size:14px">ยังไม่มีงานในคิว — ไปเลือกจากแท็บ Templates ได้เลยครับ</div>';
}
function schedTxt(s){ if (s.type==='daily') return 'ทุกวัน '+s.time;
  if (s.type==='every') return 'ทุก '+s.minutes+' นาที';
  if (s.type==='once') return 'ครั้งเดียวตามเวลา'; return 'รันครั้งเดียว'; }
function openTaskResult(sessionId){ showChat(); openSession(sessionId); }
async function runTaskNow(id, btn){ btn.textContent = 'กำลังรัน...'; btn.disabled = true;
  await fetch('/api/tasks/run', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ id }) });
  setTimeout(()=>{ btn.textContent='▶ รันเลย'; btn.disabled=false; loadTaskList(); }, 4000); }
async function delTask(id){ await fetch('/api/tasks/'+id, { method:'DELETE' }); loadTaskList(); }

async function chatDirectCloud(model, text) {
  const t0 = performance.now();
  const geminiKey = localStorage.getItem('GEMINI_API_KEY');
  const groqKey = localStorage.getItem('GROQ_API_KEY');
  const openrouterKey = localStorage.getItem('OPENROUTER_API_KEY');
  const hfKey = localStorage.getItem('HF_API_KEY');

  if (model.startsWith('ollama')) {
    throw new Error('โมเดล Ollama เป็นโมเดลสำหรับรันบนคอมพิวเตอร์ของคุณ\n\n• หากเปิดผ่าน Netlify: กรุณาสลับโมเดลเป็น Hugging Face / Gemini / Groq ในมุมขวาบน\n• หากต้องการใช้ Ollama: เปิด Terminal ในเครื่องคอมพิวเตอร์แล้วรันคำสั่ง "rnai ui --remote"');
  }

  // 1. GEMINI
  if (model === 'gemini') {
    if (!geminiKey) {
      throw new Error('⚠️ ต้องการ GEMINI_API_KEY ในหน้า Settings\n\nกรุณากดรับ Key ฟรีที่ <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:var(--brand-ink);font-weight:600">aistudio.google.com/app/apikey 🔗</a> แล้วนำมาวางใน Settings');
    }
    const modelsToTry = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-1.5-pro'];
    let reply = '', lastError = '';
    for (const m of modelsToTry) {
      try {
        const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${m}:generateContent?key=${geminiKey}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contents: [{ parts: [{ text }] }] })
        });
        const data = await res.json();
        if (data.candidates?.[0]?.content?.parts?.[0]?.text) {
          reply = data.candidates[0].content.parts[0].text;
          break;
        } else if (data.error && data.error.message) {
          lastError = data.error.message;
        }
      } catch(e) { lastError = String(e); }
    }
    if (reply) return { reply, model: 'Gemini Flash', elapsed: (performance.now() - t0)/1000 };
    throw new Error('⚠️ GEMINI_API_KEY ไม่ถูกต้องหรือหมดอายุ (' + (lastError || 'HTTP Error') + ')\n\nกรุณากดรับ Key ฟรีใหม่ที่ <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:var(--brand-ink);font-weight:600">aistudio.google.com/app/apikey 🔗</a>');
  }

  // 2. GROQ
  if (model === 'groq') {
    if (!groqKey) {
      throw new Error('⚠️ ต้องการ GROQ_API_KEY ในหน้า Settings\n\nกรุณากดรับ Key ฟรีที่ <a href="https://console.groq.com/keys" target="_blank" style="color:var(--brand-ink);font-weight:600">console.groq.com/keys 🔗</a> แล้วนำมาวางใน Settings');
    }
    const groqModels = ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'llama3-70b-8192', 'llama3-8b-8192', 'mixtral-8x7b-32768'];

    let reply = '', lastError = '';
    for (const gm of groqModels) {
      try {
        const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${groqKey}` },
          body: JSON.stringify({ model: gm, messages: [{ role: 'user', content: text }] })
        });
        const data = await res.json();
        if (data.choices?.[0]?.message?.content) {
          reply = data.choices[0].message.content;
          break;
        } else if (data.error && data.error.message) {
          lastError = data.error.message;
        }
      } catch(e) { lastError = String(e); }
    }
    if (reply) return { reply, model: 'Groq (Llama-3.3)', elapsed: (performance.now() - t0)/1000 };
    throw new Error('⚠️ GROQ_API_KEY ไม่ถูกต้องหรือหมดอายุ (' + (lastError || 'HTTP Error') + ')\n\nกรุณากดรับ Key ฟรีใหม่ที่ <a href="https://console.groq.com/keys" target="_blank" style="color:var(--brand-ink);font-weight:600">console.groq.com/keys 🔗</a>');
  }

  // 3. HUGGING FACE
  if (model.includes('hf') || model.includes('huggingface')) {
    if (!hfKey) {
      throw new Error('⚠️ ต้องการ HF_API_KEY ในหน้า Settings สำหรับเรียกใช้โมเดล Hugging Face\n\nกรุณากดรับ Token ฟรีที่ <a href="https://huggingface.co/settings/tokens" target="_blank" style="color:var(--brand-ink);font-weight:600">huggingface.co/settings/tokens 🔗</a> แล้วนำมาวางใน Settings');
    }
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${hfKey}` };
    const hfEndpoints = [
      { url: 'https://router.huggingface.co/together/v1/chat/completions', model: 'meta-llama/Llama-3.3-70B-Instruct-Turbo' },
      { url: 'https://router.huggingface.co/together/v1/chat/completions', model: 'Qwen/Qwen2.5-72B-Instruct' },
      { url: 'https://router.huggingface.co/nebius/v1/chat/completions', model: 'meta-llama/Meta-Llama-3.1-70B-Instruct' },
      { url: 'https://router.huggingface.co/novita/v1/chat/completions', model: 'meta-llama/llama-3.1-70b-instruct' }
    ];
    let reply = '', lastError = '';

    for (const ep of hfEndpoints) {
      try {
        const res = await fetch(ep.url, {
          method: 'POST', headers,
          body: JSON.stringify({ model: ep.model, messages: [{ role: 'user', content: text }] })
        });
        const data = await res.json();
        if (data.choices?.[0]?.message?.content) {
          reply = data.choices[0].message.content;
          break;
        } else if (data.error) {
          lastError = typeof data.error === 'string' ? data.error : (data.error.message || JSON.stringify(data.error));
        }
      } catch(e) { lastError = String(e); }
    }

    if (reply) return { reply, model: 'HuggingFace Cloud', elapsed: (performance.now() - t0)/1000 };
    throw new Error('⚠️ ไม่สามารถเรียก Hugging Face ได้ (' + (lastError || 'Token ไม่ถูกต้องหรือโมเดลสลีป') + ')\n\nกรุณาตรวจสอบ HF_API_KEY หรือรับ Token ฟรีใหม่ที่ <a href="https://huggingface.co/settings/tokens" target="_blank" style="color:var(--brand-ink);font-weight:600">huggingface.co/settings/tokens 🔗</a>');
  }

  // 4. OPENROUTER
  if (model === 'openrouter') {
    if (!openrouterKey) {
      throw new Error('⚠️ ต้องการ OPENROUTER_API_KEY ในหน้า Settings\n\nกรุณากดรับ Key ฟรีที่ <a href="https://openrouter.ai/keys" target="_blank" style="color:var(--brand-ink);font-weight:600">openrouter.ai/keys 🔗</a> แล้วนำมาวางใน Settings');
    }
    const orModels = [
      'openrouter/auto',
      'deepseek/deepseek-r1:free',
      'qwen/qwen-2.5-7b-instruct:free',
      'google/gemma-2-9b-it:free'
    ];
    let reply = '', lastError = '';
    for (const om of orModels) {
      try {
        const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${openrouterKey}`,
            'HTTP-Referer': 'https://rnai-cli.netlify.app',
            'X-Title': 'Rnai CLI'
          },
          body: JSON.stringify({ model: om, messages: [{ role: 'user', content: text }] })
        });
        const data = await res.json();
        if (data.choices?.[0]?.message?.content) {
          reply = data.choices[0].message.content;
          break;
        } else if (data.error && data.error.message) {
          lastError = data.error.message;
        }
      } catch(e) { lastError = String(e); }
    }
    if (reply) return { reply, model: 'OpenRouter Free', elapsed: (performance.now() - t0)/1000 };
    throw new Error('⚠️ OPENROUTER_API_KEY ไม่ถูกต้องหรือหมดอายุ (' + (lastError || 'HTTP Error') + ')\n\nกรุณารับ Key ฟรีที่ <a href="https://openrouter.ai/keys" target="_blank" style="color:var(--brand-ink);font-weight:600">openrouter.ai/keys 🔗</a>');
  }

  // 5. RNAI.IO CLOUD API
  if (model === 'rnai') {
    const rnaiKey = localStorage.getItem('RNAI_IO_API_KEY');
    if (!rnaiKey) {
      throw new Error('⚠️ ต้องการเข้าสู่ระบบ Rnai.io หรือใส่ RNAI_IO_API_KEY ใน Settings\n\nกรุณากดปุ่ม 🔑 Login เพื่อเข้าสู่ระบบ Rnai.io หรือนำคีย์ rnai_sk_... ที่ได้มาวางในช่อง RNAI_IO_API_KEY ในหน้า Settings');
    }
    try {
      const res = await fetch('https://rnai-io.vercel.app/api/rnai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${rnaiKey}` },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      if (data && data.text) {
        return { reply: data.text, model: 'rnai-llm v4.1 (Rnai.io Cloud)', elapsed: (performance.now() - t0)/1000 };
      } else if (data && data.error) {
        throw new Error(data.error);
      }
    } catch(e) {
      if (e.message && !e.message.includes('fetch')) throw e;
    }
    throw new Error('⚠️ ไม่สามารถเรียก Rnai.io Cloud ได้ในขณะนี้\n\nกรุณาตรวจสอบคีย์ RNAI_IO_API_KEY หรือลองกดปุ่ม 🔑 Login เพื่อเข้าสู่ระบบใหม่อีกครั้ง');
  }

  // Auto select any working key if model is set to default
  if (groqKey) return chatDirectCloud('groq', text);
  if (geminiKey) return chatDirectCloud('gemini', text);
  if (openrouterKey) return chatDirectCloud('openrouter', text);
  if (hfKey) return chatDirectCloud('hf', text);

  throw new Error('ไม่พบ API Key ในหน้า Settings\n\n• กรุณากดปุ่ม 🔑 Login หรือ Settings ด้านบน เพื่อวาง API Key ของ Gemini / Groq / HuggingFace');
}

/* ── Microphone / Speech-to-Text (Voice input) ── */
let speechRecognizer = null;
let isRecordingVoice = false;
let voiceBaseText = '';

function toggleVoiceInput() {
  if (isRecordingVoice) {
    stopVoiceInput();
  } else {
    startVoiceInput();
  }
}

function startVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert('เบราว์เซอร์ของคุณยังไม่รองรับ Web Speech API\nแนะนำให้ใช้งานผ่าน Google Chrome, Microsoft Edge หรือ Apple Safari เพื่อใช้งานฟังก์ชันแปลงเสียงเป็นข้อความ');
    return;
  }

  const micBtn = $('micBtn');
  const listeningBar = $('micListeningBar');
  const inputEl = $('input');

  try {
    if (speechRecognizer) {
      try { speechRecognizer.stop(); } catch(e) {}
    }

    speechRecognizer = new SpeechRecognition();
    speechRecognizer.lang = 'th-TH'; // ภาษาไทยเป็นหลัก
    speechRecognizer.continuous = true;
    speechRecognizer.interimResults = true;
    speechRecognizer.maxAlternatives = 1;

    voiceBaseText = inputEl ? inputEl.value : '';
    if (voiceBaseText && !voiceBaseText.endsWith(' ') && !voiceBaseText.endsWith('\n')) {
      voiceBaseText += ' ';
    }

    speechRecognizer.onstart = function() {
      isRecordingVoice = true;
      if (micBtn) {
        micBtn.classList.add('recording');
        micBtn.title = 'กำลังฟังเสียง... (กดเพื่อหยุดการบันทึก)';
      }
      if (listeningBar) listeningBar.classList.add('active');
    };

    speechRecognizer.onresult = function(event) {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (inputEl) {
        const spoken = (finalTranscript || interimTranscript).trim();
        if (spoken) {
          inputEl.value = voiceBaseText + spoken;
          if (typeof autosize === 'function') autosize();
          inputEl.scrollTop = inputEl.scrollHeight;
        }
      }
    };

    speechRecognizer.onerror = function(event) {
      console.warn('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        alert('กรุณาอนุญาตการเข้าถึงไมโครโฟน (Microphone Permission) ในการตั้งค่าเบราว์เซอร์ เพื่อใช้งานการพิมพ์ด้วยเสียง');
      }
      stopVoiceInput();
    };

    speechRecognizer.onend = function() {
      if (isRecordingVoice) {
        stopVoiceInput();
      }
    };

    speechRecognizer.start();
  } catch (err) {
    console.error('Failed to start speech recognition:', err);
    stopVoiceInput();
  }
}

function stopVoiceInput() {
  isRecordingVoice = false;
  const micBtn = $('micBtn');
  const listeningBar = $('micListeningBar');
  const inputEl = $('input');

  if (micBtn) {
    micBtn.classList.remove('recording');
    micBtn.title = 'เปิดไมโครโฟนพูดเพื่อแปลงเป็นข้อความ (Voice-to-Text)';
  }
  if (listeningBar) listeningBar.classList.remove('active');

  if (speechRecognizer) {
    try {
      speechRecognizer.stop();
    } catch(e) {}
    speechRecognizer = null;
  }

  if (inputEl) {
    if (typeof autosize === 'function') autosize();
    inputEl.focus();
  }
}

// ทางลัดคีย์บอร์ด: Alt + M เพื่อเปิด/ปิดไมโครโฟน
window.addEventListener('keydown', (e) => {
  if (e.altKey && (e.key === 'm' || e.key === 'M' || e.key === 'ท')) {
    e.preventDefault();
    toggleVoiceInput();
  }
});

async function send() {
  if (isRecordingVoice) {
    stopVoiceInput();
  }
  if (typeof sendStudentMsg === 'function') {
    sendStudentMsg();
    return;
  }
  const text = $('input').value.trim(); if (!text) return;
  $('input').value = ''; autosize(); $('send').disabled = true;
  if (agentMode) { sendAgent(text); return; }
  addMsg('user', text);
  const wait = addMsg('bot', 'กำลังคิด'); wait.classList.add('typing');
  scrollBottom();
  const targetModel = $('model') ? $('model').value : 'rnai';
  try {
    let d;
    try {
      const r = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ session_id: sid, model: targetModel, message: text }) });
      if (r.ok) d = await r.json();
    } catch(e) {}
    if (!d) {
      d = await chatDirectCloud(targetModel, text);
    }
    wait.parentElement.remove();
    if (d.error) { const b = addMsg('bot', d.error); b.classList.add('err'); }
    else { sid = d.session_id || sid; addMsg('bot', d.reply, d.model + ' · ' + (d.elapsed ? d.elapsed.toFixed(1) + 's' : 'cloud')); }
  } catch (e) {
    wait.parentElement.remove();
    let msg = String(e.message || e);
    if (msg.includes('Failed to fetch') || msg.includes('TypeError')) {
      msg = '⚠️ ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ในขณะนี้\n\n'
          + '• หากใช้งานผ่าน Netlify (เว็บเบราว์เซอร์): กรุณาเลือกโมเดล Gemini / Groq / HuggingFace ในช่องมุมขวาบน และใส่ API Key ในหน้า Settings\n'
          + '• หากต้องการใช้ Ollama / Local Agent: เปิด Terminal ในคอมพิวเตอร์ แล้วรันคำสั่ง "rnai ui --remote"';
    }
    const b = addMsg('bot', msg); b.classList.add('err');
  }
  $('send').disabled = false; loadRecents(); scrollBottom();
}
function scrollBottom(){ const c = $('chat'); c.scrollTop = c.scrollHeight; }
function esc(s){ return (s||'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function ago(ts){ const m = (Date.now()/1000 - ts)/60;
  if (m < 1) return 'เมื่อครู่'; if (m < 60) return Math.floor(m)+' นาทีที่แล้ว';
  if (m < 1440) return Math.floor(m/60)+' ชม.ที่แล้ว'; return Math.floor(m/1440)+' วันที่แล้ว'; }
const input = $('input');
function autosize(){ input.style.height='auto'; input.style.height = Math.min(input.scrollHeight, 160)+'px'; }
if (input) {
  input.addEventListener('input', autosize);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (typeof sendStudentMsg === 'function') sendStudentMsg();
      else send();
    }
  });
}

if ($('emptyChips')) renderChips();
if ($('projects') || $('projList')) loadProjects();
if ($('acctTier')) loadAccount();


/* ── Theme ── */
function applyTheme(t){
  document.documentElement.setAttribute('data-theme', t);
  const b = $('themebtn'); if (b) b.textContent = t === 'dark' ? '☀️' : '🌙';
  try { localStorage.setItem('rnai-theme', t); } catch(e){}
}
function toggleTheme(){
  const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  applyTheme(cur === 'dark' ? 'light' : 'dark');
}
(function(){
  let saved = 'light';
  try { saved = localStorage.getItem('rnai-theme')
        || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light'); } catch(e){}
  applyTheme(saved);
})();

/* ── Views: chat / templates / settings / download ── */
function hideAll(){
  $('main').style.display='none';
  if ($('side')) $('side').removeAttribute('style');
  closeMobileSidebar();
  $('settings').classList.remove('show');
  $('download').classList.remove('show');
  $('ws').classList.remove('show');
  const dv = $('docview');
  if (dv) dv.classList.remove('show');
}
function showWorkspace(){ hideAll(); $('ws').classList.add('show'); loadTemplates(); loadTaskList(); loadDocuments(); }
function showDocBox(){ hideAll(); const dv = $('docview'); if (dv) dv.classList.add('show'); loadDocuments(); }
function showSettings(){ hideAll(); $('settings').classList.add('show'); loadConfig(); loadNetworkInfo(); }
function showDownload(){ hideAll(); $('download').classList.add('show'); }
function showChat(){ hideAll(); $('main').style.display='flex'; }

/* ── Templates ── */
const TYPE_ICON = { task:'⏰', chat:'💬', agent:'🤖' };
let TPLS = [];
async function loadTemplates(){
  const r = await fetch('/api/templates'); TPLS = await r.json();
  const tc = $('tplCount'); if (tc) tc.textContent = TPLS.length + ' รายการ';
  const cats = [...new Set(TPLS.map(t=>t.cat))];
  $('tpllist').innerHTML = cats.map(c =>
    `<div class="tplcat">${c}</div><div class="cards">` +
    TPLS.filter(t=>t.cat===c).map(t =>
      `<div class="card" onclick="pickTpl('${t.id}')">
         <div class="t">${TYPE_ICON[t.type]} ${esc(t.title)}</div>
         <div class="p">${esc(t.prompt)}</div>
         <div class="badge">${t.sched_txt||''}</div>
       </div>`).join('') + '</div>').join('');
}
function tplVars(prompt){ return [...prompt.matchAll(/\{([^}]+)\}/g)].map(m=>m[1]); }
function pickTpl(id){
  const t = TPLS.find(x=>x.id===id); if (!t) return;
  const vars = tplVars(t.prompt);
  let rows = vars.map((v,i) =>
    `<div class="frow"><label>${esc(v)}</label><input id="tv-${i}" placeholder="กรอก${esc(v)}"></div>`).join('');
  if (t.type==='task' && t.schedule && t.schedule.daily !== undefined)
    rows += `<div class="frow"><label>รันทุกวันเวลา (HH:MM)</label><input id="tv-sched" value="${t.schedule.daily}"></div>`;
  if (t.type==='task' && t.schedule && t.schedule.every !== undefined)
    rows += `<div class="frow"><label>รันทุกกี่นาที</label><input id="tv-sched" value="${t.schedule.every}"></div>`;
  if (t.type==='task' && t.schedule && t.schedule.at !== undefined)
    rows += `<div class="frow"><label>รันเมื่อ (YYYY-MM-DD HH:MM)</label><input id="tv-sched" placeholder="2026-07-21 09:30"></div>`;
  const f = $('tplform');
  f.innerHTML = `<h3>${TYPE_ICON[t.type]} ${esc(t.title)}</h3><div class="fp">${esc(t.prompt)}</div>${rows}
    <div class="actions">
      <button class="go" onclick="useTpl('${t.id}')">${t.type==='task'?'เพิ่มเข้าคิว Worker':t.type==='chat'?'ไปคุยต่อในแชท':'คัดลอกคำสั่ง Terminal'}</button>
      <button class="cancel" onclick="$('tplform').classList.remove('show')">ยกเลิก</button>
      <span id="tplmsg"></span>
    </div>`;
  f.classList.add('show'); f.scrollIntoView({behavior:'smooth'});
}
async function useTpl(id){
  const t = TPLS.find(x=>x.id===id);
  let prompt = t.prompt;
  tplVars(t.prompt).forEach((v,i) => { prompt = prompt.split('{'+v+'}').join($('tv-'+i).value.trim() || v); });
  if (t.type === 'chat') { showChat(); newChatSoft(); $('input').value = prompt; $('input').focus(); autosize(); return; }
  if (t.type === 'agent') {
    navigator.clipboard.writeText('rnai agent "' + prompt.replace(/"/g,'\\"') + '"');
    $('tplmsg').innerHTML = '<span class="saved">✓ คัดลอกแล้ว — วางใน Terminal ได้เลย</span>'; return;
  }
  const body = { prompt };
  const sv = $('tv-sched') ? $('tv-sched').value.trim() : '';
  if (t.schedule.daily !== undefined) body.daily = sv;
  else if (t.schedule.every !== undefined) body.every = parseInt(sv);
  else body.at = sv;
  const r = await fetch('/api/task', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body) });
  const d = await r.json();
  $('tplmsg').innerHTML = d.ok
    ? `<span class="saved">✓ เพิ่มงาน ${d.id} แล้ว (${d.sched}) — Worker จะรันตามเวลา</span>`
    : `<span class="err">${d.error||'ผิดพลาด'}</span>`;
}
function newChatSoft(){ sid = null; $('title') && ($('title').textContent='สนทนาใหม่');
  $('thread').innerHTML=''; loadRecents(); }

const DL = {
  mac:   { cmd:'curl -fsSL https://raw.githubusercontent.com/Rnai-io/Rnai-CLI/main/install.sh | sh', cap:'วางคำสั่งนี้ใน Terminal' },
  linux: { cmd:'curl -fsSL https://raw.githubusercontent.com/Rnai-io/Rnai-CLI/main/install.sh | sh', cap:'วางคำสั่งนี้ใน Terminal' },
  win:   { cmd:'pip install git+https://github.com/Rnai-io/Rnai-CLI.git', cap:'วางคำสั่งนี้ใน PowerShell (ต้องมี Python + Git)' },
};
function setOS(os){
  for (const k of ['mac','linux','win']) $('os-'+k).classList.toggle('on', k===os);
  $('dlcmd').textContent = DL[os].cmd; $('dlcap').textContent = DL[os].cap;
}
function copyCmd(btn){
  navigator.clipboard.writeText($('dlcmd').textContent).then(()=>{
    btn.textContent='Copied ✓'; setTimeout(()=>btn.textContent='Copy', 1500); });
}
async function loadConfig(){
  let d;
  try {
    const r = await fetch('/api/config');
    if (r.ok) d = await r.json();
  } catch(e){}
  if (!d) {
    d = { sections: [
      { title: 'Cloud Models API Keys (สำหรับ WebApp บน Netlify)', items: [
        { label: 'GROQ_API_KEY', key: 'GROQ_API_KEY', desc: 'gsk_... สำหรับ Groq — <a href="https://console.groq.com/keys" target="_blank" style="color:var(--brand-ink);font-weight:600">รับ Key ฟรีที่ console.groq.com 🔗</a>', secret: true, set: !!localStorage.getItem('GROQ_API_KEY'), value: localStorage.getItem('GROQ_API_KEY')||'' },
        { label: 'GEMINI_API_KEY', key: 'GEMINI_API_KEY', desc: 'สำหรับ Gemini — <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:var(--brand-ink);font-weight:600">รับ Key ฟรีที่ aistudio.google.com 🔗</a>', secret: true, set: !!localStorage.getItem('GEMINI_API_KEY'), value: localStorage.getItem('GEMINI_API_KEY')||'' },
        { label: 'HF_API_KEY', key: 'HF_API_KEY', desc: 'สำหรับ rnai-llm v4.1 GGUF — <a href="https://huggingface.co/settings/tokens" target="_blank" style="color:var(--brand-ink);font-weight:600">รับ Token ฟรีที่ huggingface.co 🔗</a>', secret: true, set: !!localStorage.getItem('HF_API_KEY'), value: localStorage.getItem('HF_API_KEY')||'' },
        { label: 'OPENROUTER_API_KEY', key: 'OPENROUTER_API_KEY', desc: 'สำหรับ OpenRouter — <a href="https://openrouter.ai/keys" target="_blank" style="color:var(--brand-ink);font-weight:600">รับ Key ที่ openrouter.ai 🔗</a>', secret: true, set: !!localStorage.getItem('OPENROUTER_API_KEY'), value: localStorage.getItem('OPENROUTER_API_KEY')||'' },
        { label: 'RNAI_IO_API_KEY', key: 'RNAI_IO_API_KEY', desc: 'จากโปรไฟล์ Rnai.io — <a href="https://rnai-io.vercel.app/dashboard/profile" target="_blank" style="color:var(--brand-ink);font-weight:600">ดู Key ที่ Rnai.io 🔗</a>', secret: true, set: !!localStorage.getItem('RNAI_IO_API_KEY'), value: localStorage.getItem('RNAI_IO_API_KEY')||'' }
      ]}
    ]};
  }
  let html = `<div class="sethead">🔑 บัญชี Rnai.io (Account & Login)</div>
    <div class="setrow">
      <div class="info">
        <div class="name">เข้าสู่ระบบเพื่อใช้งาน Rnai.io Cloud Models & Skills</div>
        <div class="desc">เข้าใช้งานด้วยอีเมลและรหัสผ่านของคุณจาก Rnai.io เพื่อดูเครดิตและสร้าง API key ให้อัตโนมัติ</div>
      </div>
      <button class="save" onclick="openAccount()">🔑 เข้าสู่ระบบ Rnai.io</button>
    </div>`;
  for (const sec of d.sections) {
    html += `<div class="sethead">${sec.title}</div>`;
    for (const it of sec.items) {
      const secret = it.secret;
      html += `<div class="setrow">
        <div class="info">
          <div class="name"><span class="st ${it.set?'on':''}"></span>${it.label}</div>
          <div class="desc">${it.desc}</div>
        </div>
        <input id="in-${it.key}" type="${secret?'password':'text'}"
               placeholder="${it.set ? (secret ? (it.masked || '••••••••') : it.value) : (it.placeholder||'ยังไม่ได้ตั้งค่า')}">
        <button class="save" onclick="saveKey('${it.key}')">บันทึก</button>
        <span id="ok-${it.key}"></span>
      </div>`;
    }
  }
  $('setlist').innerHTML = html;
  loadNetworkInfo();
}

async function loadNetworkInfo(){
  try {
    const r = await fetch('/api/network');
    if (r.ok) {
      const d = await r.json();
      const nDiv = document.getElementById('netinfo');
      if (nDiv) nDiv.textContent = d.lan_url;
    }
  } catch(e){}
}

async function saveKey(key){
  const v = $('in-'+key).value.trim();
  if (!v) return;
  try { localStorage.setItem(key, v); } catch(e){}
  if (key === 'GEMINI_API_KEY') $('model').value = 'gemini';
  else if (key === 'GROQ_API_KEY') $('model').value = 'groq';
  else if (key === 'OPENROUTER_API_KEY') $('model').value = 'openrouter';
  else if (key === 'HF_API_KEY') $('model').value = 'hf/naiguitarfolk/rnai-llm-v4.1-gguf';

  try {
    const r = await fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ key, value: v }) });
    const d = await r.json();
    if (d.ok) { $('ok-'+key).className='saved'; $('ok-'+key).textContent='✓ บันทึกแล้ว';
      setTimeout(loadConfig, 900); return; }
  } catch(e) {}
  $('ok-'+key).className='saved'; $('ok-'+key).textContent='✓ บันทึกในเบราว์เซอร์แล้ว (สลับโมเดลให้อัตโนมัติ)';
  setTimeout(loadConfig, 900);
}

loadRecents();
loadDocumentsBadge();
if (location.hash === '#login') { openAccount(); }

/* ── Document Hub & Upload Box ── */
let DOCS = [];
let activePromptFile = null;
let activePreviewDoc = null;

function docIcon(ext) {
  ext = (ext || '').toLowerCase().replace(/^\./, '');
  if (ext === 'pdf') return { cls: 'pdf', icon: '📕' };
  if (['doc', 'docx'].includes(ext)) return { cls: 'docx', icon: '📘' };
  if (['xls', 'xlsx'].includes(ext)) return { cls: 'xlsx', icon: '📗' };
  if (['csv', 'tsv'].includes(ext)) return { cls: 'csv', icon: '📊' };
  if (['json', 'js', 'py', 'html', 'css', 'sql'].includes(ext)) return { cls: 'code', icon: '💻' };
  return { cls: 'txt', icon: '📄' };
}

async function loadDocumentsBadge() {
  try {
    const r = await fetch('/api/documents');
    if (!r.ok) return;
    const list = await r.json();
    DOCS = list;
    const badge = $('docCountBadge');
    if (badge) badge.textContent = `เอกสาร (${list.length})`;
  } catch(e) {}
}

async function loadDocuments() {
  try {
    const ws = await (await fetch('/api/workspace')).json();
    if ($('docFolderShort') && ws.dir) {
      $('docFolderShort').textContent = homeShort(ws.dir) + '/documents';
    }
  } catch(e) {}

  try {
    const r = await fetch('/api/documents');
    if (!r.ok) return;
    DOCS = await r.json();
    renderDocGrid(DOCS);
    renderWsDocMini(DOCS);
    const badge = $('docCountBadge');
    if (badge) badge.textContent = `เอกสาร (${DOCS.length})`;
    const stats = $('docStatsText');
    if (stats) stats.textContent = `${DOCS.length} รายการ`;
  } catch(e) {
    console.error('loadDocuments error:', e);
  }
}

function renderDocGrid(items) {
  const grid = $('docGrid');
  const empty = $('docEmptyMsg');
  if (!grid) return;

  if (!items.length) {
    grid.innerHTML = '';
    if (empty) empty.style.display = 'block';
    return;
  }
  if (empty) empty.style.display = 'none';

  grid.innerHTML = items.map(d => {
    const ic = docIcon(d.ext);
    return `
      <div class="doc-card" id="doc-${esc(d.relative_path)}">
        <div class="doc-card-header">
          <div class="doc-type-icon ${ic.cls}">${ic.icon}</div>
          <div class="doc-info">
            <div class="doc-name" title="${esc(d.name)}">${esc(d.name)}</div>
            <div class="doc-meta">
              <span>${esc(d.size_formatted)}</span>
              <span>•</span>
              <span>${esc(d.mtime_formatted)}</span>
            </div>
          </div>
        </div>

        <div class="doc-excerpt">
          ${d.preview_text ? esc(d.preview_text) : 'คลิกเพื่อดูตัวอย่างเนื้อหาหรือส่งให้โมเดลอ่านและวิเคราะห์'}
        </div>

        <div class="doc-card-actions">
          <div class="doc-action-row">
            <button class="doc-btn primary" onclick="quickDocAction('${esc(d.relative_path)}', 'analyze')" title="สั่งให้โมเดลเอเจนอ่าน ศึกษาวิเคราะห์ และคำนวณข้อมูล">
              📊 วิเคราะห์ & คำนวณ
            </button>
            <button class="doc-btn" onclick="openDocPromptModal('${esc(d.relative_path)}', '${esc(d.name)}')" title="ปรับแต่งคำสั่งวิเคราะห์และรายงานตามสั่ง">
              ⚙️ รายงานตามสั่ง
            </button>
          </div>
          <div class="doc-action-row">
            <button class="doc-btn" onclick="previewDoc('${esc(d.relative_path)}')" title="ดูตัวอย่างข้อความที่สกัดได้จากเอกสาร">
              👁️ ดูตัวอย่าง
            </button>
            <button class="doc-btn danger icon-only" onclick="deleteDoc('${esc(d.relative_path)}', '${esc(d.name)}')" title="ลบไฟล์นี้">
              🗑️
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderWsDocMini(items) {
  const mini = $('wsDocMiniList');
  if (!mini) return;
  if (!items.length) {
    mini.innerHTML = '<div style="font-size:12.5px;color:var(--faint);padding:6px 0;">(ยังไม่มีเอกสารในกล่อง กดเปิดกล่องเอกสารเพื่ออัปโหลด)</div>';
    return;
  }
  mini.innerHTML = items.slice(0, 4).map(d => {
    const ic = docIcon(d.ext);
    return `
      <div class="wsdoc-item" onclick="quickDocAction('${esc(d.relative_path)}', 'analyze')">
        <span class="w-ic">${ic.icon}</span>
        <span class="w-name">${esc(d.name)}</span>
        <span class="w-sz">${esc(d.size_formatted)}</span>
      </div>
    `;
  }).join('');
}

function filterDocList(kw) {
  kw = (kw || '').trim().toLowerCase();
  if (!kw) {
    renderDocGrid(DOCS);
    return;
  }
  const filtered = DOCS.filter(d => (d.name || '').toLowerCase().includes(kw) || (d.ext || '').toLowerCase().includes(kw));
  renderDocGrid(filtered);
}

function triggerDocUpload() {
  const inp = $('docFileInput');
  if (inp) {
    inp.value = '';
    inp.click();
  }
}

async function handleDocFileSelect(ev) {
  const files = ev.target.files;
  if (!files || !files.length) return;
  await uploadFilesList(files);
}

async function uploadFilesList(files) {
  const pBox = $('docUploadProgress');
  const pFill = $('docProgressBarFill');
  const pTxt = $('docProgressStatus');

  if (pBox) pBox.style.display = 'block';

  let done = 0;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (pTxt) pTxt.textContent = `กำลังอัปโหลด ${file.name} (${i + 1}/${files.length})...`;
    if (pFill) pFill.style.width = `${Math.round(((i) / files.length) * 100)}%`;

    try {
      await uploadFileDirect(file);
      done++;
    } catch(err) {
      toast(`อัปโหลด ${file.name} ไม่สำเร็จ: ${err.message}`);
    }
  }

  if (pFill) pFill.style.width = '100%';
  if (pTxt) pTxt.textContent = `อัปโหลดเสร็จสิ้น ${done} ไฟล์!`;
  setTimeout(() => { if (pBox) pBox.style.display = 'none'; }, 1500);

  toast(`✓ อัปโหลดสำเร็จ ${done} ไฟล์`);
  await loadDocuments();
}

function uploadFileDirect(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async function() {
      try {
        const base64 = reader.result;
        const res = await fetch('/api/documents/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            content: base64,
            is_base64: true,
            subfolder: 'documents'
          })
        });
        const d = await res.json();
        if (d.ok) resolve(d);
        else reject(new Error(d.error || 'upload failed'));
      } catch(e) {
        reject(e);
      }
    };
    reader.onerror = () => reject(new Error('read file error'));
    reader.readAsDataURL(file);
  });
}

/* Drag & Drop */
let dragCounter = 0;
window.addEventListener('dragenter', e => {
  if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
    dragCounter++;
    const ol = $('dragDropOverlay');
    if (ol) ol.classList.add('active');
  }
});
window.addEventListener('dragleave', e => {
  dragCounter--;
  if (dragCounter <= 0) {
    dragCounter = 0;
    const ol = $('dragDropOverlay');
    if (ol) ol.classList.remove('active');
  }
});
window.addEventListener('dragover', e => { e.preventDefault(); });
window.addEventListener('drop', async e => {
  e.preventDefault();
  dragCounter = 0;
  const ol = $('dragDropOverlay');
  if (ol) ol.classList.remove('active');
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    await uploadFilesList(e.dataTransfer.files);
  }
});

function handleDocDragOver(ev) {
  ev.preventDefault();
  const dz = $('docDropzone');
  if (dz) dz.classList.add('dragover');
}
function handleDocDragLeave(ev) {
  const dz = $('docDropzone');
  if (dz) dz.classList.remove('dragover');
}
async function handleDocDrop(ev) {
  ev.preventDefault();
  const dz = $('docDropzone');
  if (dz) dz.classList.remove('dragover');
  if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
    await uploadFilesList(ev.dataTransfer.files);
  }
}

/* One-click Action & Presets */
function quickDocAction(relPath, actionType) {
  setMode('cowork');
  showChat();

  let prompt = '';
  if (actionType === 'analyze') {
    prompt = `กรุณาอ่าน ศึกษาวิเคราะห์ และคำนวณข้อมูลตัวเลข/สถิติทั้งหมดในเอกสาร \`${relPath}\` โดยละเอียด พร้อมสรุปรายงานผลวิเคราะห์เชิงลึกและการคำนวณที่ถูกต้อง`;
  } else if (actionType === 'summary') {
    prompt = `กรุณาอ่านและสรุปสาระสำคัญ ประเด็นหลัก และข้อคิดเห็นสำคัญจากเอกสาร \`${relPath}\` เป็นภาษาไทยที่กระชับและเข้าใจง่าย`;
  } else if (actionType === 'report') {
    prompt = `กรุณาจัดทำรายงานวิเคราะห์ฉบับสมบูรณ์จากเอกสาร \`${relPath}\` โดยแบ่งออกเป็น 4 ส่วนหลัก:
1. สรุปภาพรวมและวัตถุประสงค์
2. สาระสำคัญและผลการวิเคราะห์เชิงลึก
3. การคำนวณตัวเลขและสถิติสำคัญ (ระบุสูตร/ที่มาตัวเลขชัดเจน)
4. บทสรุปและข้อเสนอแนะเชิงปฏิบัติ`;
  } else {
    prompt = `กรุณาอ่านและศึกษาวิเคราะห์เอกสาร \`${relPath}\` อย่างละเอียด`;
  }

  $('input').value = prompt;
  autosize();
  send();
}

function openDocPromptModal(relPath, filename) {
  activePromptFile = relPath;
  const targetCode = $('docPromptTargetFile');
  if (targetCode) targetCode.innerHTML = `เอกสารเป้าหมาย: <code>${esc(filename || relPath)}</code>`;
  selectDocPreset('analyze');
  $('docPromptModal').classList.add('show');
}

function selectDocPreset(preset, btnEl) {
  if (btnEl) {
    document.querySelectorAll('.preset-chips .pchip').forEach(b => b.classList.remove('on'));
    btnEl.classList.add('on');
  }

  const pfile = activePromptFile || 'เอกสาร';
  const txt = $('docPromptCustomText');
  if (!txt) return;

  if (preset === 'analyze') {
    txt.value = `กรุณาอ่าน ศึกษาวิเคราะห์ และคำนวณข้อมูลสถิติ/ตัวเลขทั้งหมดในเอกสาร \`${pfile}\` พร้อมสรุปรายงานผลการคำนวณอย่างถูกต้องแม่นยำ`;
  } else if (preset === 'summary') {
    txt.value = `กรุณาอ่านและสรุปสาระสำคัญ ใจความหลัก และข้อคิดเห็นที่สำคัญจากเอกสาร \`${pfile}\``;
  } else if (preset === 'report') {
    txt.value = `กรุณาจัดทำรายงานวิเคราะห์ฉบับสมบูรณ์จากเอกสาร \`${pfile}\` โดยแบ่งเป็นหัวข้อ:
1) ภาพรวมและวัตถุประสงค์
2) ผลการวิเคราะห์เชิงลึก
3) ข้อมูลสถิติและการคำนวณที่สำคัญ
4) บทสรุปและข้อเสนอแนะ`;
  } else if (preset === 'verify') {
    txt.value = `กรุณาอ่านเอกสาร \`${pfile}\` เพื่อตรวจสอบความถูกต้องของตัวเลข สถิติ และข้อเท็จจริง ค้นหาจุดผิดพลาดหรือข้อสังเกตที่น่าสงสัย`;
  }
}

function executeDocAgentTask() {
  const prompt = ($('docPromptCustomText').value || '').trim();
  if (!prompt) return;
  $('docPromptModal').classList.remove('show');

  setMode('cowork');
  showChat();
  $('input').value = prompt;
  autosize();
  send();
}

/* Preview Document */
async function previewDoc(relPath) {
  activePreviewDoc = relPath;
  $('prevDocTitle').textContent = `📄 กำลังเปิด ${relPath.split('/').pop()}...`;
  $('prevDocMeta').textContent = 'กำลังประมวลผลและสกัดเนื้อหาเอกสาร...';
  $('prevDocBody').textContent = 'กำลังโหลด...';
  $('docPreviewModal').classList.add('show');

  try {
    const r = await fetch('/api/documents/preview?path=' + encodeURIComponent(relPath));
    const d = await r.json();
    if (!d.ok) {
      $('prevDocBody').textContent = 'ข้อผิดพลาด: ' + (d.error || 'ไม่สามารถอ่านเอกสารได้');
      return;
    }

    $('prevDocTitle').textContent = `📄 ${d.file_name}`;
    const stats = d.stats || {};
    let metaTxt = `ขนาด: ${d.file_size_formatted || '-'} | ชนิด: ${d.file_ext || '-'}`;
    if (stats.pages) metaTxt += ` | จำนวน: ${stats.pages} หน้า`;
    if (stats.rows) metaTxt += ` | จำนวน: ${stats.rows} แถว, ${stats.columns || 0} คอลัมน์`;
    if (stats.chars) metaTxt += ` | ความยาว: ${stats.chars.toLocaleString()} ตัวอักษร`;

    $('prevDocMeta').textContent = metaTxt;
    $('prevDocBody').textContent = d.text || '(ไม่มีข้อความที่สกัดได้)';
  } catch(e) {
    $('prevDocBody').textContent = 'ข้อผิดพลาดในการเชื่อมต่อ: ' + e.message;
  }
}

function sendDocToAgentFromPreview() {
  if (!activePreviewDoc) return;
  $('docPreviewModal').classList.remove('show');
  quickDocAction(activePreviewDoc, 'analyze');
}

/* Delete Document */
async function deleteDoc(relPath, name) {
  if (!confirm(`คุณต้องการลบเอกสาร "${name || relPath}" ใช่หรือไม่?`)) return;
  try {
    const r = await fetch('/api/documents/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: relPath })
    });
    const d = await r.json();
    if (d.ok) {
      toast(`✓ ลบไฟล์ ${name || relPath} เรียบร้อยแล้ว`);
      await loadDocuments();
    } else {
      toast('ลบไฟล์ไม่สำเร็จ: ' + (d.error || 'error'));
    }
  } catch(e) {
    toast('ลบไฟล์ไม่สำเร็จ: ' + e.message);
  }
}

