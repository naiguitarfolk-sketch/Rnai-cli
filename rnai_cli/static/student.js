// Rnai Student Edition Client Logic
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('show');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('show');
}

function getStudentId() {
  return localStorage.getItem('rnai_student_id') || '';
}

function valOf(id) {
  const el = document.getElementById(id);
  return el ? (el.value || '').trim() : '';
}

function setValOf(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

async function performStudentLogin() {
  const user = valOf('stuUserInput') || valOf('stuIdInput');
  const pass = valOf('stuPassInput');
  const errDiv = document.getElementById('loginErrMsg');
  if (errDiv) errDiv.style.display = 'none';

  if (!user || !pass) {
    if (errDiv) { errDiv.textContent = 'กรุณากรอกรหัสนักศึกษาและรหัสผ่าน'; errDiv.style.display = 'block'; }
    return;
  }

  try {
    const res = await fetch('/api/student/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass })
    });
    const data = await res.json();
    if (data.ok) {
      localStorage.setItem('rnai_student_id', user);
      closeModal('loginDlg');
      updateLoginBadge();
      loadStudentState();
      if (typeof addMsg === 'function') {
        addMsg('bot', `🔑 เข้าสู่ระบบนักศึกษา (${user}) เรียบร้อยแล้ว`);
      }
    } else {
      if (errDiv) { errDiv.textContent = '⚠️ ' + (data.error || 'เข้าสู่ระบบไม่สำเร็จ'); errDiv.style.display = 'block'; }
    }
  } catch(e) {
    if (errDiv) { errDiv.textContent = '⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ'; errDiv.style.display = 'block'; }
  }
}

function updateLoginBadge() {
  const btn = document.getElementById('studentLoginBtn');
  const btn2 = document.getElementById('studentActionBarLoginBtn');
  const sid = getStudentId();
  const text = sid ? `👤 รหัส: ${sid}` : '🔐 เข้าสู่ระบบ (Login)';
  if (btn) btn.textContent = text;
  if (btn2) btn2.textContent = text;
}

function getHeaders() {
  const h = { 'Content-Type': 'application/json' };
  const sid = getStudentId();
  if (sid) h['X-Student-ID'] = sid;
  return h;
}

async function loadStudentState() {
  updateLoginBadge();
  try {
    const res = await fetch('/api/student/status', { headers: getHeaders() });
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById('studentWeekBadge');
      if (badge && data.week) {
        badge.textContent = `สัปดาห์ที่ ${data.week} · ${data.fading_level || 'L1'}`;
      }
    }
  } catch(e) {}
}

async function sendStudentMsg() {
  if (typeof isRecordingVoice !== 'undefined' && isRecordingVoice) {
    if (typeof stopVoiceInput === 'function') stopVoiceInput();
  }
  const input = document.getElementById('input');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  
  if (typeof addMsg === 'function') {
    addMsg('user', text);
    const wait = addMsg('bot', 'ผู้ช่วยกำลังคิด...');
    wait.classList.add('typing');
    if (typeof scrollBottom === 'function') scrollBottom();

    try {
      const res = await fetch('/api/student/chat', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ message: text, session_id: (typeof sid !== 'undefined' ? sid : '') })
      });
      const data = await res.json();
      wait.parentElement.remove();
      if (data.session_id) {
        sid = data.session_id;
        if (typeof loadRecents === 'function') loadRecents();
      }
      if (data.reply) {
        addMsg('bot', data.reply, (data.model || 'rnai-tutor-v1') + ' · มสธ.');
      } else if (data.error) {
        const err = addMsg('bot', '⚠️ ' + data.error);
        err.classList.add('err');
      }
    } catch(e) {
      wait.parentElement.remove();
      const err = addMsg('bot', '⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์วิจัย');
      err.classList.add('err');
    }
    if (typeof scrollBottom === 'function') scrollBottom();
  }
}

function quickAsk(qText) {
  const input = document.getElementById('input');
  if (input) {
    input.value = qText;
    sendStudentMsg();
  }
}

async function saveGoal() {
  const text = valOf('gText');
  const criterion = valOf('gCriterion');
  const component = valOf('gComponent');
  if (!text) return alert('กรุณากรอกเป้าหมายการเรียน');

  try {
    const res = await fetch('/api/student/goal', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ goal_text: text, measurable_criterion: criterion, component: component })
    });
    const data = await res.json();
    if (data.ok) {
      closeModal('goalDlg');
      setValOf('gText', '');
      setValOf('gCriterion', '');
      setValOf('gComponent', '');
      if (typeof addMsg === 'function') {
        addMsg('bot', '🎯 บันทึกเป้าหมายการเรียนเรียบร้อยแล้ว: ' + text);
      }
    }
  } catch(e) {
    alert('เกิดข้อผิดพลาดในการบันทึกเป้าหมาย');
  }
}

async function saveProgress() {
  const activity = valOf('pAct');
  const type = valOf('pType') || 'reading';
  const val = valOf('pValue');
  if (!activity) return alert('กรุณากรอกกิจกรรมการเรียน');

  try {
    const res = await fetch('/api/student/progress', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ activity: activity, evidence_type: type, value: val })
    });
    const data = await res.json();
    if (data.ok) {
      closeModal('progressDlg');
      setValOf('pAct', '');
      setValOf('pValue', '');
      if (typeof addMsg === 'function') {
        addMsg('bot', '📊 บันทึกความก้าวหน้าการเรียนเรียบร้อยแล้ว');
      }
    }
  } catch(e) {
    alert('เกิดข้อผิดพลาดในการบันทึกความก้าวหน้า');
  }
}

async function saveReflection() {
  const worked = valOf('rWorked');
  const change = valOf('rChange');
  if (!worked && !change) return alert('กรุณากรอกข้อมูลการสะท้อนความคิด');

  try {
    const res = await fetch('/api/student/reflection', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ what_worked: worked, what_to_change: change })
    });
    const data = await res.json();
    if (data.ok) {
      closeModal('reflectDlg');
      setValOf('rWorked', '');
      setValOf('rChange', '');
      if (typeof addMsg === 'function') {
        addMsg('bot', '📝 บันทึกการสะท้อนการเรียนรู้เรียบร้อยแล้ว');
      }
    }
  } catch(e) {
    alert('เกิดข้อผิดพลาดในการบันทึกการสะท้อนความคิด');
  }
}

async function searchCorpus() {
  const query = valOf('sQuery');
  const resultsDiv = document.getElementById('sResults');
  if (!query) return;
  if (resultsDiv) resultsDiv.textContent = 'กำลังค้นหาคลังเอกสาร...';

  try {
    const res = await fetch('/api/student/search?q=' + encodeURIComponent(query));
    const data = await res.json();
    if (resultsDiv) {
      if (data.results && data.results.length > 0) {
        resultsDiv.innerHTML = data.results.map(r =>
          `<div style="padding:6px; border-bottom:1px solid var(--line);">
             <b>${r.title}</b> <small>(${r.type || 'เอกสาร'})</small><br>
             <span style="color:var(--sub); font-size:11.5px;">ID: ${r.resource_id}</span>
           </div>`
        ).join('');
      } else {
        resultsDiv.textContent = 'ไม่พบบทความหรือคู่มือที่ตรงในคลัง';
      }
    }
  } catch(e) {
    if (resultsDiv) resultsDiv.textContent = 'เกิดข้อผิดพลาดในการค้นหา';
  }
}

window.addEventListener('load', () => {
  loadStudentState();
  loadStudentDocs();
  if (typeof loadProjects === 'function') loadProjects();
  if (typeof loadRecents === 'function') loadRecents();
});

/* ── Student Document Hub & Upload Box ── */
let STU_DOCS = [];
let stuActivePreviewPath = null;

function stuDocIcon(ext) {
  ext = (ext || '').toLowerCase().replace(/^\./, '');
  if (ext === 'pdf') return { cls: 'pdf', icon: '📕' };
  if (['doc', 'docx'].includes(ext)) return { cls: 'docx', icon: '📘' };
  if (['xls', 'xlsx'].includes(ext)) return { cls: 'xlsx', icon: '📗' };
  if (['csv', 'tsv'].includes(ext)) return { cls: 'csv', icon: '📊' };
  if (['json', 'js', 'py', 'html', 'css', 'sql'].includes(ext)) return { cls: 'code', icon: '💻' };
  return { cls: 'txt', icon: '📄' };
}

function openStudentDocModal() {
  openModal('stuDocModal');
  loadStudentDocs();
}

async function loadStudentDocs() {
  try {
    const res = await fetch('/api/documents');
    if (!res.ok) return;
    STU_DOCS = await res.json();
    
    const badge = document.getElementById('stuDocBadge');
    if (badge) badge.textContent = `${STU_DOCS.length}`;
    
    const countSpan = document.getElementById('stuDocListCount');
    if (countSpan) countSpan.textContent = `${STU_DOCS.length}`;

    renderStudentDocList(STU_DOCS);
  } catch(e) {
    console.error('loadStudentDocs error:', e);
  }
}

function renderStudentDocList(items) {
  const container = document.getElementById('stuDocList');
  if (!container) return;

  if (!items.length) {
    container.innerHTML = `
      <div style="text-align:center; padding:24px 10px; color:var(--sub); font-size:13px; background:var(--soft); border-radius:10px;">
        ยังไม่มีเอกสารในกล่อง ลากไฟล์มาวางด้านบน หรือกดคลิกเพื่ออัปโหลดไฟล์ประกอบการเรียนรู้
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(d => {
    const ic = stuDocIcon(d.ext);
    return `
      <div style="border:1px solid var(--line); border-radius:12px; background:var(--card); padding:12px; display:flex; flex-direction:column; gap:8px;">
        <div style="display:flex; align-items:center; gap:10px;">
          <div style="width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:16px;" class="doc-type-icon ${ic.cls}">
            ${ic.icon}
          </div>
          <div style="flex:1; min-width:0;">
            <div style="font-size:13.5px; font-weight:600; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
              ${d.name}
            </div>
            <div style="font-size:11.5px; color:var(--sub);">
              ${d.size_formatted} • ${d.mtime_formatted}
            </div>
          </div>
        </div>

        <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:2px;">
          <button class="st-btn" onclick="quickAskStudentDoc('${d.relative_path}', 'summary')" title="ให้อ่านและสรุปประเด็นหลักของบทเรียน" style="padding:4px 10px; font-size:11.5px; background:var(--accent-tint); color:var(--brand-ink); border-color:var(--brand-ink);">
            📖 สรุปบทเรียน
          </button>
          <button class="st-btn" onclick="quickAskStudentDoc('${d.relative_path}', 'calc')" title="วิเคราะห์และคำนวณตัวเลข/สถิติ" style="padding:4px 10px; font-size:11.5px;">
            🧮 คำนวณ & วิเคราะห์
          </button>
          <button class="st-btn" onclick="quickAskStudentDoc('${d.relative_path}', 'quiz')" title="สร้างข้อสอบทบทวนความเข้าใจ" style="padding:4px 10px; font-size:11.5px;">
            🎯 สร้างแบบฝึกหัด
          </button>
          <button class="st-btn" onclick="previewStudentDoc('${d.relative_path}')" title="ดูตัวอย่างเนื้อหา" style="padding:4px 8px; font-size:11.5px;">
            👁️ ดูตัวอย่าง
          </button>
          <button class="st-btn" onclick="deleteStudentDoc('${d.relative_path}', '${d.name}')" title="ลบไฟล์" style="padding:4px 8px; font-size:11.5px; color:#dc2626;">
            🗑️
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function triggerStudentUpload() {
  const inp = document.getElementById('stuFileInput');
  if (inp) {
    inp.value = '';
    inp.click();
  }
}

async function handleStudentFileSelect(ev) {
  const files = ev.target.files;
  if (!files || !files.length) return;
  await uploadStudentFilesList(files);
}

async function handleStudentDocDrop(ev) {
  ev.preventDefault();
  const dz = document.getElementById('stuDropzone');
  if (dz) dz.classList.remove('dragover');
  if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
    await uploadStudentFilesList(ev.dataTransfer.files);
  }
}

async function uploadStudentFilesList(files) {
  const pBox = document.getElementById('stuUploadProgress');
  const pFill = document.getElementById('stuProgressBarFill');
  const pTxt = document.getElementById('stuProgressStatus');

  if (pBox) pBox.style.display = 'block';

  let done = 0;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (pTxt) pTxt.textContent = `กำลังอัปโหลด ${file.name} (${i + 1}/${files.length})...`;
    if (pFill) pFill.style.width = `${Math.round(((i) / files.length) * 100)}%`;

    try {
      await uploadStudentFileDirect(file);
      done++;
    } catch(err) {
      alert(`อัปโหลด ${file.name} ไม่สำเร็จ: ${err.message}`);
    }
  }

  if (pFill) pFill.style.width = '100%';
  if (pTxt) pTxt.textContent = `อัปโหลดเสร็จสิ้น ${done} ไฟล์!`;
  setTimeout(() => { if (pBox) pBox.style.display = 'none'; }, 1500);

  await loadStudentDocs();
}

function uploadStudentFileDirect(file) {
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

function quickAskStudentDoc(relPath, mode) {
  closeModal('stuDocModal');
  let prompt = '';
  if (mode === 'summary') {
    prompt = `ช่วยอ่าน ศึกษาวิเคราะห์ และสรุปสาระสำคัญของเอกสาร \`${relPath}\` เพื่อใช้ประกอบการเรียนรู้ด้วยตนเอง โดยแบ่งเป็นประเด็นสำคัญและแนวคิดหลักที่ต้องทำความเข้าใจ`;
  } else if (mode === 'calc') {
    prompt = `ช่วยอ่านเอกสาร \`${relPath}\` และทำการคำนวณ วิเคราะห์ข้อมูลตัวเลข สถิติ หรือตารางข้อมูล พร้อมอธิบายขั้นตอนและสรุปผลการคำนวณอย่างชัดเจน`;
  } else if (mode === 'quiz') {
    prompt = `ช่วยอ่านเอกสาร \`${relPath}\` และวิเคราะห์เนื้อหาเพื่อสร้างแบบฝึกหัด/แบบทดสอบประเมินตนเอง 3 ข้อ (พร้อมเฉลยและเหตุผล) เพื่อทบทวนความเข้าใจ`;
  } else {
    prompt = `ช่วยอ่านและศึกษาวิเคราะห์เอกสาร \`${relPath}\``;
  }

  const input = document.getElementById('input');
  if (input) {
    input.value = prompt;
    sendStudentMsg();
  }
}

async function previewStudentDoc(relPath) {
  stuActivePreviewPath = relPath;
  openModal('stuPreviewModal');
  const tEl = document.getElementById('stuPrevTitle');
  const mEl = document.getElementById('stuPrevMeta');
  const bEl = document.getElementById('stuPrevBody');

  if (tEl) tEl.textContent = `📄 กำลังโหลด ${relPath.split('/').pop()}...`;
  if (mEl) mEl.textContent = 'กำลังสกัดข้อความจากเอกสาร...';
  if (bEl) bEl.textContent = 'กำลังโหลด...';

  try {
    const res = await fetch('/api/documents/preview?path=' + encodeURIComponent(relPath));
    const data = await res.json();
    if (!data.ok) {
      if (bEl) bEl.textContent = 'ข้อผิดพลาด: ' + (data.error || 'ไม่สามารถอ่านเอกสารได้');
      return;
    }

    if (tEl) tEl.textContent = `📄 ${data.file_name}`;
    const stats = data.stats || {};
    let metaTxt = `ขนาด: ${data.file_size_formatted || '-'} | ชนิด: ${data.file_ext || '-'}`;
    if (stats.pages) metaTxt += ` | จำนวน: ${stats.pages} หน้า`;
    if (stats.rows) metaTxt += ` | จำนวน: ${stats.rows} แถว, ${stats.columns || 0} คอลัมน์`;
    if (stats.chars) metaTxt += ` | ความยาว: ${stats.chars.toLocaleString()} ตัวอักษร`;

    if (mEl) mEl.textContent = metaTxt;
    if (bEl) bEl.textContent = data.text || '(ไม่มีข้อความ)';
  } catch(e) {
    if (bEl) bEl.textContent = 'เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + e.message;
  }
}

function sendDocToStudentChatFromPreview() {
  if (!stuActivePreviewPath) return;
  closeModal('stuPreviewModal');
  quickAskStudentDoc(stuActivePreviewPath, 'summary');
}

async function deleteStudentDoc(relPath, name) {
  if (!confirm(`ต้องการลบเอกสาร "${name || relPath}" ใช่หรือไม่?`)) return;
  try {
    const res = await fetch('/api/documents/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: relPath })
    });
    const d = await res.json();
    if (d.ok) {
      await loadStudentDocs();
    } else {
      alert('ลบเอกสารไม่สำเร็จ: ' + (d.error || 'error'));
    }
  } catch(e) {
    alert('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + e.message);
  }
}


