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
  if (typeof loadProjects === 'function') loadProjects();
  if (typeof loadRecents === 'function') loadRecents();
});

