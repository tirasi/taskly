'use strict';
/* Taskly frontend: plain JS, no build step.
   Rule used everywhere: user-provided text goes in via textContent (h() below), never innerHTML. */

// ------------------------------------------------------------------ tiny helpers
const $ = (sel, el = document) => el.querySelector(sel);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

// Replace an element's children; accepts nested arrays and skips null/false (unlike replaceChildren).
function fill(el, ...kids) {
  el.replaceChildren(...kids.flat(Infinity)
    .filter((k) => k != null && k !== false)
    .map((k) => (k.nodeType ? k : document.createTextNode(String(k)))));
}

async function api(path, { method = 'GET', body } = {}) {
  const isForm = body instanceof FormData;
  const res = await fetch('/api' + path, {
    method,
    headers: body && !isForm ? { 'Content-Type': 'application/json' } : {},
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (!res.ok) {
    let msg = 'Something went wrong';
    try { const j = await res.json(); if (typeof j.detail === 'string') msg = j.detail; } catch { /* keep default */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

const pad = (n) => String(n).padStart(2, '0');
const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const todayISO = () => isoDate(new Date());
const parseISO = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };

function fmtDate(iso) {
  if (!iso) return '';
  const diff = Math.round((parseISO(iso) - parseISO(todayISO())) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Tomorrow';
  if (diff === -1) return 'Yesterday';
  return parseISO(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
}
function fmtTime(hhmm) {
  if (!hhmm) return '';
  const [hh, mm] = hhmm.split(':').map(Number);
  return `${hh % 12 || 12}:${pad(mm)} ${hh < 12 ? 'AM' : 'PM'}`;
}
const fmtStamp = (iso) => new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

function icon(name, { size = 16, color = 'currentColor', strokeWidth = 2, day = null, class: cls = '' } = {}) {
  let inner = '';
  if (name === 'check') {
    inner = '<polyline points="20 6 9 17 4 12"/>';
  } else if (name === 'inbox') {
    inner = '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>';
  } else if (name === 'today') {
    const d = day != null ? day : new Date().getDate();
    inner = `<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><text x="12" y="18.5" font-size="8.5" font-family="system-ui, sans-serif" font-weight="700" fill="${color}" stroke="none" text-anchor="middle">${d}</text>`;
  } else if (name === 'upcoming') {
    inner = '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="14" x2="8.01" y2="14"/><line x1="12" y1="14" x2="12.01" y2="14"/><line x1="16" y1="14" x2="16.01" y2="14"/><line x1="8" y1="18" x2="8.01" y2="18"/><line x1="12" y1="18" x2="12.01" y2="18"/>';
  } else if (name === 'completed') {
    inner = '<circle cx="12" cy="12" r="10"/><polyline points="16 9 10 15 7 12"/>';
  } else if (name === 'bell') {
    inner = '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>';
  } else if (name === 'mic') {
    inner = '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>';
  } else if (name === 'sun') {
    inner = '<circle cx="12" cy="12" r="4.5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  } else if (name === 'weekend') {
    inner = '<path d="M4 11V8a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v3"/><path d="M2 13a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-4z"/><path d="M4 19v2"/><path d="M20 19v2"/>';
  } else if (name === 'next-week') {
    inner = '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="M9 16l3-3-3-3"/><line x1="15" y1="13" x2="9" y2="13"/>';
  } else if (name === 'nodate') {
    inner = '<circle cx="12" cy="12" r="9"/><line x1="5.6" y1="5.6" x2="18.4" y2="18.4"/>';
  } else if (name === 'clock') {
    inner = '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>';
  } else if (name === 'repeat') {
    inner = '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>';
  } else if (name === 'close') {
    inner = '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>';
  } else if (name === 'chevron-left') {
    inner = '<polyline points="15 18 9 12 15 6"/>';
  } else if (name === 'chevron-right') {
    inner = '<polyline points="9 18 15 12 9 6"/>';
  } else if (name === 'circle-dot') {
    inner = '<circle cx="12" cy="12" r="3.5" fill="currentColor"/>';
  } else if (name === 'comment') {
    inner = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>';
  }
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', color);
  svg.setAttribute('stroke-width', String(strokeWidth));
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  if (cls) svg.setAttribute('class', cls);
  svg.innerHTML = inner;
  return svg;
}

function isOverdue(t) {
  if (!t.due_date || t.done) return false;
  const today = todayISO();
  if (t.due_date < today) return true;
  if (t.due_date === today && t.due_time) {
    const now = new Date();
    const [hh, mm] = t.due_time.split(':').map(Number);
    const due = new Date();
    due.setHours(hh, mm, 0, 0);
    return now > due;
  }
  return false;
}

function fmtHeaderDate(iso, time) {
  if (!iso) return '';
  const d = parseISO(iso);
  const day = d.getDate();
  const month = d.toLocaleDateString(undefined, { month: 'short' });
  return `${day} ${month}${time ? ' ' + time : ''}`;
}


// ------------------------------------------------------------------ state
const S = {
  view: { kind: 'today', id: null },
  tasks: [],
  side: { today: 0, upcoming: 0, projects: [] },
  selected: null,       // task id open in the drawer
  cfg: { debug: false, stt_enabled: false, llm_enabled: false, email_domain: '' },
};

// ------------------------------------------------------------------ toast
let toastTimer;
function toast(msg, { heard, undo, ms = 5000 } = {}) {
  const t = $('#toast');
  fill(t,
    h('div', null, heard ? h('span', { class: 'heard' }, `“${heard}”`) : null, msg),
    undo ? h('button', { onclick: () => { hideToast(); undo(); } }, 'Undo') : null);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, ms);
}
const hideToast = () => { $('#toast').hidden = true; };

// ------------------------------------------------------------------ data loading
async function refresh() {
  const { kind, id } = S.view;
  const q = kind === 'project' ? `?view=project&project_id=${id}` : `?view=${kind}`;
  const [tasks, side] = await Promise.all([api('/tasks' + q), api('/sidebar')]);
  S.tasks = tasks; S.side = side;
  renderSide(); renderList();
}

function setView(kind, id = null) {
  S.view = { kind, id };
  closeDrawer();
  refresh().catch((e) => toast(e.message));
}

// ------------------------------------------------------------------ sidebar
function renderSide() {
  const v = S.view;
  const item = (label, kind, id, count, extra, iconEl) => h('button', {
    class: 'nav' + (v.kind === kind && v.id === id ? ' active' : ''),
    onclick: () => setView(kind, id),
  }, h('span', { class: 'nav-label' }, iconEl, h('span', null, label)), extra || h('small', null, count || ''));

  const inbox = S.side.projects.find((p) => p.id === 1);
  const projects = S.side.projects.filter((p) => p.id !== 1);
  const aiOn = S.cfg.stt_enabled && S.cfg.llm_enabled;

  fill($('#side'),
    h('div', { class: 'brand' }, icon('check', { size: 19, color: 'var(--accent)', strokeWidth: 2.5 }), h('span', null, 'Taskly')),
    item('Inbox', 'inbox', null, inbox ? inbox.count : 0, null, icon('inbox', { size: 17 })),
    item('Today', 'today', null, S.side.today, null, icon('today', { size: 17, day: new Date().getDate() })),
    item('Upcoming', 'upcoming', null, S.side.upcoming, null, icon('upcoming', { size: 17 })),
    item('Completed', 'completed', null, 0, h('span'), icon('completed', { size: 17 })),
    h('div', { class: 'side-head' }, 'Projects',
      h('button', { title: 'Add project', 'aria-label': 'Add project', onclick: addProject }, '+')),
    projects.map((p) => h('button', {
      class: 'nav' + (v.kind === 'project' && v.id === p.id ? ' active' : ''),
      onclick: () => setView('project', p.id),
    }, h('span', { class: 'nav-label' }, `# ${p.name}`),
       h('span', null, h('small', null, p.count || ''),
         h('span', { class: 'del-proj', title: 'Delete project', onclick: (e) => { e.stopPropagation(); deleteProject(p); } }, '✕')))),
    h('div', { class: 'side-foot' },
      ('Notification' in window && Notification.permission === 'default')
        ? h('button', { onclick: enableNotifications }, icon('bell', { size: 14 }), h('span', null, 'Enable reminders')) : null,
      h('div', { class: 'ai-status' },
        icon('mic', { size: 14 }),
        h('span', null, aiOn ? 'Cloud voice AI: on'
          : 'Voice: offline mode (browser speech + rules). Add API keys in .env for cloud AI.'))));
}

async function addProject() {
  const name = (prompt('Project name') || '').trim();
  if (!name) return;
  try { await api('/projects', { method: 'POST', body: { name } }); await refresh(); } catch (e) { toast(e.message); }
}
async function deleteProject(p) {
  if (!confirm(`Delete project “${p.name}”? Its tasks move to the Inbox.`)) return;
  await api(`/projects/${p.id}`, { method: 'DELETE' });
  if (S.view.kind === 'project' && S.view.id === p.id) S.view = { kind: 'inbox', id: null };
  await refresh();
}

// ------------------------------------------------------------------ task list
const TITLES = { today: 'Today', upcoming: 'Upcoming', inbox: 'Inbox', completed: 'Completed' };

function renderList() {
  const { kind, id } = S.view;
  const title = kind === 'project' ? (S.side.projects.find((p) => p.id === id) || {}).name || 'Project' : TITLES[kind];
  $('#viewTitle').textContent = title;
  $('#viewSub').textContent = kind === 'today' ? new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }) : '';
  $('#addForm').hidden = $('#preview').hidden = kind === 'completed';

  const list = $('#list');
  if (!S.tasks.length) {
    fill(list, h('div', { class: 'empty' }, kind === 'completed' ? 'Nothing completed yet.' : 'All clear. Add a task above, or tap 🎙 and say it.'));
    return;
  }
  const today = todayISO();
  const groups = [];   // [{title, cls, tasks}]
  if (kind === 'today') {
    const over = S.tasks.filter(isOverdue);
    const now = S.tasks.filter((t) => !isOverdue(t));
    if (over.length) groups.push({ title: 'Overdue', cls: 'overdue', tasks: over });
    if (now.length) groups.push({ title: 'Today', tasks: now });
  } else if (kind === 'upcoming') {
    for (const t of S.tasks) {
      const g = groups[groups.length - 1];
      if (g && g.key === t.due_date) g.tasks.push(t);
      else groups.push({ key: t.due_date, title: `${fmtDate(t.due_date)} · ${parseISO(t.due_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`, tasks: [t] });
    }
  } else groups.push({ tasks: S.tasks });

  fill(list, groups.map((g) => [
    g.title ? h('div', { class: 'group-title ' + (g.cls || '') }, g.title) : null,
    g.tasks.map(taskRow),
  ]));
}

function taskRow(t) {
  const overdue = isOverdue(t);
  const row = h('div', { class: 'task' + (t.done ? ' done' : '') + (overdue ? ' overdue' : '') + (S.selected === t.id ? ' selected' : ''), 'data-id': t.id, onclick: () => openTask(t.id) },
    h('button', {
      class: `check p${t.priority}`, title: t.done ? 'Reopen' : 'Complete', 'aria-label': t.done ? 'Reopen task' : 'Complete task',
      onclick: (e) => { e.stopPropagation(); toggleDone(t, row); },
    }),
    h('div', { class: 't-main' },
      h('div', { class: 't-title' }, t.title),
      h('div', { class: 't-meta' },
        t.due_date ? h('span', {
          class: 't-date-chip' + (overdue ? ' overdue' : ''),
          title: 'Change date',
          onclick: (e) => {
            e.stopPropagation();
            openDatePicker(t, e.currentTarget);
          }
        },
          icon('today', { size: 13, color: overdue ? 'var(--p1)' : 'currentColor', day: parseISO(t.due_date).getDate() }),
          h('span', null, `${fmtDate(t.due_date)}${t.due_time ? ' ' + fmtTime(t.due_time) : ''}`)) : null,
        t.recurrence_text ? h('span', { class: 'rec' }, icon('repeat', { size: 12 }), h('span', null, t.recurrence_text)) : null,
        S.view.kind !== 'project' && t.project_id !== 1 ? h('span', null, `# ${t.project_name}`) : null,
        t.comment_count ? h('span', { class: 't-meta-item' }, icon('comment', { size: 12 }), h('span', null, t.comment_count)) : null)));
  return row;
}

async function toggleDone(t, row) {
  try {
    if (t.done) {
      await api(`/tasks/${t.id}/reopen`, { method: 'POST' });
    } else {
      row.classList.add('leaving');
      const r = await api(`/tasks/${t.id}/complete`, { method: 'POST' });
      if (r.recurrence) toast(`Done. Next: ${fmtDate(r.due_date)}${r.due_time ? ' ' + fmtTime(r.due_time) : ''}`);
      else toast('Task completed', { undo: async () => { await api(`/tasks/${t.id}/reopen`, { method: 'POST' }); refresh(); } });
    }
    await refresh();
    if (S.selected === t.id) openTask(t.id);
  } catch (e) { toast(e.message); row.classList.remove('leaving'); }
}

// ------------------------------------------------------------------ quick add + live preview
const addInput = $('#addInput');
let previewTimer, previewSeq = 0;

addInput.addEventListener('input', () => {
  clearTimeout(previewTimer);
  const text = addInput.value.trim();
  if (!text) { previewSeq++; fill($('#preview')); return; }
  previewTimer = setTimeout(async () => {
    const seq = ++previewSeq;
    try {
      const p = await api('/parse', { method: 'POST', body: { text } });
      if (seq !== previewSeq) return;       // a newer keystroke already replaced this
      const chipIcon = (kind) => {
        if (kind === 'recurrence') return icon('repeat', { size: 12 });
        if (kind === 'date') return icon('today', { size: 12 });
        if (kind === 'time') return icon('clock', { size: 12 });
        return null;
      };
      const when = p.due_date ? `${fmtDate(p.due_date)}${p.due_time ? ' ' + fmtTime(p.due_time) : ''}` : '';
      fill($('#preview'),
        p.title ? h('span', null, 'Task: ', h('b', null, p.title)) : h('span', null, 'Type what the task is…'),
        p.chips.map((c) => h('span', { class: 'chip ' + c.kind }, chipIcon(c.kind), h('span', null, ' ' + c.text.trim()))),
        when ? h('span', null, p.recurrence_text ? `→ next: ${when}` : `→ ${when}`) : null);
    } catch { /* preview is best-effort */ }
  }, 180);
});

$('#addForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = addInput.value.trim();
  if (!text) return;
  clearTimeout(previewTimer); previewSeq++;       // drop any preview still in flight
  try {
    await api('/tasks', { method: 'POST', body: {
      text, default_today: S.view.kind === 'today', project_id: S.view.kind === 'project' ? S.view.id : null } });
    addInput.value = ''; fill($('#preview'));
    await refresh();
  } catch (err) { toast(err.message); }
});

// ------------------------------------------------------------------ audio recording
class Recorder {
  constructor({ autoStop = false, maxMs = 30000, onTick } = {}) { Object.assign(this, { autoStop, maxMs, onTick }); }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t));
    this.rec = new MediaRecorder(this.stream, mime ? { mimeType: mime } : {});
    this.chunks = []; this.heard = false; this.lastVoice = Date.now();
    this.rec.ondataavailable = (e) => { if (e.data.size) this.chunks.push(e.data); };
    this.done = new Promise((resolve) => {
      this.rec.onstop = () => {
        this.cleanup();
        resolve({ blob: new Blob(this.chunks, { type: this.rec.mimeType || mime || 'audio/webm' }), heard: this.heard });
      };
    });
    if (this.autoStop) {       // simple voice-activity detection so the app "listens" and stops by itself
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      this.analyser = this.ctx.createAnalyser(); this.analyser.fftSize = 1024;
      this.ctx.createMediaStreamSource(this.stream).connect(this.analyser);
      this.buf = new Float32Array(this.analyser.fftSize);
    }
    this.t0 = Date.now();
    this.rec.start();
    this.timer = setInterval(() => this.tick(), 100);
  }

  tick() {
    const ms = Date.now() - this.t0;
    if (this.analyser) {
      this.analyser.getFloatTimeDomainData(this.buf);
      const rms = Math.sqrt(this.buf.reduce((s, x) => s + x * x, 0) / this.buf.length);
      if (rms > 0.02) { this.heard = true; this.lastVoice = Date.now(); }
      if (this.heard && Date.now() - this.lastVoice > 1500) this.stop();      // finished speaking
      else if (!this.heard && ms > 7000) this.stop();                         // nobody spoke
    }
    if (ms > this.maxMs) this.stop();
    if (this.onTick) this.onTick(ms);
  }

  stop() { if (this.rec && this.rec.state !== 'inactive') this.rec.stop(); }
  cleanup() { clearInterval(this.timer); this.stream.getTracks().forEach((t) => t.stop()); if (this.ctx) this.ctx.close(); }
}

const micErr = (e) => (e && e.name === 'NotAllowedError') ? 'Microphone access is blocked. Allow it in the address bar.' : (e.message || 'Could not use the microphone.');

// ------------------------------------------------------------------ voice command (the big mic button)
let cmdRec = null, cmdBusy = false, speechRec = null;

function browserListen() {      // fallback when no cloud STT key is configured (Chrome/Edge/Safari)
  return new Promise((resolve, reject) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return reject(new Error('This browser has no speech recognition. Add STT_API_KEY to use cloud transcription.'));
    speechRec = new SR();
    speechRec.lang = navigator.language || 'en-US';
    speechRec.interimResults = false;
    speechRec.onresult = (e) => resolve(e.results[0][0].transcript);
    speechRec.onerror = (e) => reject(new Error(e.error === 'not-allowed' ? micErr({ name: 'NotAllowedError' }) : `Speech error: ${e.error}`));
    speechRec.onend = () => resolve('');
    speechRec.start();
  });
}

async function runVoiceCommand() {
  const mic = $('#micBtn');
  if (cmdBusy) return;
  if (cmdRec) { cmdRec.stop(); return; }                        // second tap = stop now
  if (speechRec) { speechRec.stop(); return; }
  try {
    mic.classList.add('listening'); addInput.placeholder = 'Listening…';
    let result;
    if (S.cfg.stt_enabled) {
      cmdRec = new Recorder({ autoStop: true });
      await cmdRec.start();
      const { blob, heard } = await cmdRec.done;
      cmdRec = null;
      mic.classList.replace('listening', 'thinking'); cmdBusy = true;
      if (!heard) { toast("I didn't hear anything. Tap the mic and try again."); return; }
      const fd = new FormData(); fd.append('audio', blob, 'speech.webm');
      result = await api('/voice/command', { method: 'POST', body: fd });
    } else {
      const text = await browserListen();
      speechRec = null;
      mic.classList.replace('listening', 'thinking'); cmdBusy = true;
      if (!text) { toast("I didn't hear anything. Tap the mic and try again."); return; }
      result = await api('/voice/interpret', { method: 'POST', body: { text } });
    }
    toast(result.message, { heard: result.transcript, ms: 7000 });
    await refresh();
  } catch (e) {
    toast(micErr(e));
  } finally {
    cmdRec = null; speechRec = null; cmdBusy = false;
    mic.classList.remove('listening', 'thinking'); addInput.placeholder = 'Add a task… e.g. gym every mon 6am #Health';
  }
}
$('#micBtn').addEventListener('click', runVoiceCommand);

// ------------------------------------------------------------------ task drawer
function closeDrawer() {
  S.selected = null;
  $('#drawer').hidden = true;
  document.querySelectorAll('.task.selected').forEach((r) => r.classList.remove('selected'));
}

async function openTask(id) {
  S.selected = id;
  document.querySelectorAll('.task').forEach((r) => r.classList.toggle('selected', r.dataset.id === String(id)));
  try {
    const [t, comments, projects] = await Promise.all([api(`/tasks/${id}`), api(`/tasks/${id}/comments`), api('/projects')]);
    renderDrawer(t, comments, projects);
  } catch (e) { toast(e.message); closeDrawer(); }
}

function scheduleText(t) {
  if (t.recurrence_text) return t.recurrence_text;
  if (!t.due_date) return '';
  return `${fmtDate(t.due_date)}${t.due_time ? ' ' + fmtTime(t.due_time) : ''}`;
}

// ------------------------------------------------------------------ Todoist-style date picker popover
let activeDP = null;

function closeDatePicker() {
  if (activeDP) {
    activeDP.el.remove();
    activeDP = null;
  }
}

function openDatePicker(task, anchorEl) {
  closeDatePicker();

  let curDate = task.due_date;
  let curTime = task.due_time || '';
  let curRec = task.recurrence_text || '';

  const baseD = curDate ? parseISO(curDate) : new Date();
  let calYear = baseD.getFullYear();
  let calMonth = baseD.getMonth();
  let showingTime = false;
  let showingRepeat = false;

  const popover = h('div', { class: 'dp-popover', onclick: (e) => e.stopPropagation() });
  document.body.appendChild(popover);

  const positionPopover = () => {
    const rect = anchorEl.getBoundingClientRect();
    const popWidth = 292;
    let left = rect.left;
    if (left + popWidth > window.innerWidth - 12) {
      left = window.innerWidth - popWidth - 12;
    }
    if (left < 12) left = 12;

    let top = rect.bottom + 6;
    const estHeight = 440;
    if (top + estHeight > window.innerHeight - 12) {
      const topAbove = rect.top - estHeight - 6;
      if (topAbove > 12) top = topAbove;
      else top = Math.max(12, window.innerHeight - estHeight - 12);
    }
    popover.style.left = `${left + window.scrollX}px`;
    popover.style.top = `${top + window.scrollY}px`;
  };

  positionPopover();
  activeDP = { el: popover, anchor: anchorEl };

  const patchAndRefresh = async (body, { close = false } = {}) => {
    try {
      const updated = await api(`/tasks/${task.id}`, { method: 'PATCH', body });
      Object.assign(task, updated);
      await refresh();
      if (S.selected === task.id) openTask(task.id);
      if (close) {
        closeDatePicker();
      } else {
        curDate = task.due_date;
        curTime = task.due_time || '';
        curRec = task.recurrence_text || '';
        render();
        positionPopover();
      }
    } catch (e) {
      toast(e.message);
    }
  };

  const render = () => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);

    // This weekend (Saturday)
    const thisWeekend = new Date(today);
    const dayOfWeek = today.getDay(); // 0 = Sun ... 6 = Sat
    const daysUntilSat = (6 - dayOfWeek + 7) % 7 || 7;
    thisWeekend.setDate(today.getDate() + daysUntilSat);

    // Next week (Monday)
    const nextWeek = new Date(today);
    const daysUntilMon = (1 - dayOfWeek + 7) % 7 || 7;
    nextWeek.setDate(today.getDate() + daysUntilMon);

    const datesWithTasks = new Set(S.tasks.filter((t) => t.due_date && !t.done).map((t) => t.due_date));

    // Top input value display
    const topVal = curDate ? fmtHeaderDate(curDate, curTime) : (curRec || '');

    const topInput = h('input', {
      class: 'dp-text-input',
      type: 'text',
      value: topVal,
      placeholder: 'Type a date, time or repeat…',
      'aria-label': 'Date and time',
      onkeydown: async (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const txt = topInput.value.trim();
          if (!txt) {
            await patchAndRefresh({ schedule: '' }, { close: true });
          } else {
            await patchAndRefresh({ schedule: txt }, { close: true });
          }
        }
      }
    });

    const closeBtn = h('button', {
      class: 'dp-close-btn',
      type: 'button',
      'aria-label': 'Close picker',
      onclick: closeDatePicker
    }, icon('close', { size: 14 }));

    // Quick option row helper
    const quickBtn = (iconEl, label, rightText, onClick) => h('button', {
      type: 'button',
      class: 'dp-quick-btn',
      onclick: onClick
    },
      h('span', { class: 'dp-quick-left' }, iconEl, h('span', null, label)),
      rightText ? h('span', { class: 'dp-quick-right' }, rightText) : null);

    // Mini Calendar calculation
    const calDate = new Date(calYear, calMonth, 1);
    const monthTitle = calDate.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
    const firstDayIdx = (calDate.getDay() + 6) % 7;
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

    const calNavPrev = h('button', {
      type: 'button',
      title: 'Previous month',
      onclick: () => {
        calMonth--;
        if (calMonth < 0) { calMonth = 11; calYear--; }
        render();
      }
    }, icon('chevron-left', { size: 13 }));

    const calNavToday = h('button', {
      type: 'button',
      title: 'Today',
      onclick: () => {
        calYear = now.getFullYear();
        calMonth = now.getMonth();
        render();
      }
    }, icon('circle-dot', { size: 10 }));

    const calNavNext = h('button', {
      type: 'button',
      title: 'Next month',
      onclick: () => {
        calMonth++;
        if (calMonth > 11) { calMonth = 0; calYear++; }
        render();
      }
    }, icon('chevron-right', { size: 13 }));

    const dayCells = [];
    for (let i = 0; i < firstDayIdx; i++) {
      dayCells.push(h('div', { class: 'dp-day-cell dp-empty' }));
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const dayISO = isoDate(new Date(calYear, calMonth, d));
      const isToday = dayISO === todayISO();
      const isSel = dayISO === curDate;
      const hasDot = isSel || datesWithTasks.has(dayISO);

      dayCells.push(h('button', {
        type: 'button',
        class: 'dp-day-cell' + (isToday ? ' dp-today' : '') + (isSel ? ' dp-selected' : ''),
        onclick: () => {
          curDate = dayISO;
          patchAndRefresh({ due_date: dayISO, due_time: curTime || null }, { close: false });
        }
      },
        h('span', null, String(d)),
        hasDot ? h('span', { class: 'dp-dot' }) : null));
    }

    // Next month preview
    const nextMonthDate = new Date(calYear, calMonth + 1, 1);
    const nextMonthName = nextMonthDate.toLocaleDateString(undefined, { month: 'short' });
    const nextFirstIdx = (nextMonthDate.getDay() + 6) % 7;
    const nextDayCells = [];
    for (let i = 0; i < nextFirstIdx; i++) {
      nextDayCells.push(h('div', { class: 'dp-day-cell dp-empty' }));
    }
    for (let d = 1; d <= 8; d++) {
      const dayISO = isoDate(new Date(nextMonthDate.getFullYear(), nextMonthDate.getMonth(), d));
      const isSel = dayISO === curDate;
      const hasDot = isSel || datesWithTasks.has(dayISO);
      nextDayCells.push(h('button', {
        type: 'button',
        class: 'dp-day-cell' + (isSel ? ' dp-selected' : ''),
        onclick: () => {
          curDate = dayISO;
          patchAndRefresh({ due_date: dayISO, due_time: curTime || null }, { close: false });
        }
      },
        h('span', null, String(d)),
        hasDot ? h('span', { class: 'dp-dot' }) : null));
    }

    // Time action button
    const timeBtn = h('button', {
      type: 'button',
      class: 'dp-action-btn',
      onclick: () => { showingTime = !showingTime; showingRepeat = false; render(); positionPopover(); }
    },
      icon('clock', { size: 15 }),
      h('span', { class: 'dp-btn-label' }, curTime ? curTime : 'Time'),
      curTime ? h('span', {
        class: 'dp-clear-part',
        title: 'Clear time',
        onclick: (e) => {
          e.stopPropagation();
          curTime = '';
          patchAndRefresh({ due_time: '' }, { close: false });
        }
      }, icon('close', { size: 13 })) : null);

    // Time Sub Panel
    const timePanel = showingTime ? h('div', { class: 'dp-sub-panel' },
      h('div', { class: 'dp-chips-grid' },
        [
          { label: 'Morning', val: '09:00' },
          { label: 'Afternoon', val: '13:00' },
          { label: 'Evening', val: '18:00' },
          { label: 'Night', val: '21:00' },
        ].map((p) => h('button', {
          type: 'button',
          class: 'dp-chip-btn',
          onclick: () => {
            curTime = p.val;
            showingTime = false;
            patchAndRefresh({ due_time: p.val, due_date: curDate || todayISO() }, { close: false });
          }
        }, `${p.label} ${p.val}`))),
      h('div', { class: 'dp-custom-time-row' },
        h('input', {
          type: 'time',
          value: curTime || '09:00',
          id: 'dpCustomTimeInput'
        }),
        h('button', {
          type: 'button',
          class: 'small-btn primary',
          onclick: () => {
            const v = $('#dpCustomTimeInput', popover).value;
            if (v) {
              curTime = v;
              showingTime = false;
              patchAndRefresh({ due_time: v, due_date: curDate || todayISO() }, { close: false });
            }
          }
        }, 'Set'))) : null;

    // Repeat action button
    const repeatBtn = h('button', {
      type: 'button',
      class: 'dp-action-btn',
      onclick: () => { showingRepeat = !showingRepeat; showingTime = false; render(); positionPopover(); }
    },
      icon('repeat', { size: 15 }),
      h('span', { class: 'dp-btn-label' }, curRec ? curRec : 'Repeat'),
      curRec ? h('span', {
        class: 'dp-clear-part',
        title: 'Clear repeat',
        onclick: (e) => {
          e.stopPropagation();
          curRec = '';
          patchAndRefresh({ recurrence: '' }, { close: false });
        }
      }, icon('close', { size: 13 })) : null);

    // Repeat Sub Panel
    const repeatPanel = showingRepeat ? h('div', { class: 'dp-sub-panel' },
      h('div', { class: 'dp-chips-grid' },
        [
          { label: 'Daily', sched: 'every day' },
          { label: 'Weekdays', sched: 'every weekday' },
          { label: 'Weekly', sched: 'every week' },
          { label: 'Monthly', sched: 'every month' },
          { label: 'Yearly', sched: 'every year' },
          { label: "Don't repeat", sched: '' },
        ].map((r) => h('button', {
          type: 'button',
          class: 'dp-chip-btn',
          onclick: () => {
            showingRepeat = false;
            if (!r.sched) {
              patchAndRefresh({ recurrence: '' }, { close: false });
            } else {
              patchAndRefresh({ schedule: r.sched + (curTime ? ' ' + curTime : '') }, { close: false });
            }
          }
        }, r.label)))) : null;

    fill(popover,
      h('div', { class: 'dp-head' }, topInput, closeBtn),
      h('div', { class: 'dp-quick-list' },
        quickBtn(icon('today', { size: 18, color: '#2f9e44', day: now.getDate() }),
          'Today',
          today.toLocaleDateString(undefined, { weekday: 'short' }),
          () => patchAndRefresh({ due_date: todayISO(), due_time: curTime || null }, { close: true })),
        quickBtn(icon('sun', { size: 18, color: '#eb8909' }),
          'Tomorrow',
          tomorrow.toLocaleDateString(undefined, { weekday: 'short' }),
          () => patchAndRefresh({ due_date: isoDate(tomorrow), due_time: curTime || null }, { close: true })),
        quickBtn(icon('weekend', { size: 18, color: '#246fe0' }),
          'This weekend',
          thisWeekend.toLocaleDateString(undefined, { weekday: 'short' }),
          () => patchAndRefresh({ due_date: isoDate(thisWeekend), due_time: curTime || null }, { close: true })),
        quickBtn(icon('next-week', { size: 18, color: '#8b5cf6' }),
          'Next week',
          nextWeek.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' }),
          () => patchAndRefresh({ due_date: isoDate(nextWeek), due_time: curTime || null }, { close: true })),
        quickBtn(icon('nodate', { size: 18, color: '#7a7a7a' }),
          'No Date',
          null,
          () => patchAndRefresh({ due_date: '', due_time: '', recurrence: '' }, { close: true }))),
      h('hr', { class: 'dp-divider' }),
      h('div', { class: 'dp-cal' },
        h('div', { class: 'dp-cal-head' },
          h('span', { class: 'dp-cal-title' }, monthTitle),
          h('div', { class: 'dp-cal-nav' }, calNavPrev, calNavToday, calNavNext)),
        h('div', { class: 'dp-cal-weekdays' },
          ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((wd) => h('span', null, wd))),
        h('div', { class: 'dp-cal-grid' }, dayCells),
        h('div', { class: 'dp-next-month-label' }, nextMonthName),
        h('div', { class: 'dp-cal-grid' }, nextDayCells)),
      h('div', { class: 'dp-bottom-controls' },
        timeBtn,
        timePanel,
        repeatBtn,
        repeatPanel));
  };

  render();
}

document.addEventListener('click', (e) => {
  if (activeDP) {
    if (!activeDP.el.contains(e.target) && !activeDP.anchor.contains(e.target)) {
      closeDatePicker();
    }
  }
});

function renderDrawer(t, comments, projects) {
  const d = $('#drawer');
  const commentsBox = h('div', { class: 'comments' }, comments.map(commentView));
  const note = h('textarea', { placeholder: 'Add a comment…', 'aria-label': 'Comment' });

  const sendComment = async () => {
    const body = note.value.trim();
    if (!body) return;
    try {
      const c = await api(`/tasks/${t.id}/comments`, { method: 'POST', body: { body } });
      note.value = ''; commentsBox.append(commentView(c)); refresh();
    } catch (e) { toast(e.message); }
  };

  // --- voice note recorder (tap to start, tap to stop)
  let noteRec = null;
  const recBtn = h('button', { class: 'small-btn rec-btn', type: 'button' }, icon('mic', { size: 13 }), ' Record voice note');
  recBtn.addEventListener('click', async () => {
    if (noteRec) { noteRec.stop(); return; }
    try {
      noteRec = new Recorder({ maxMs: 120000, onTick: (ms) => { recBtn.textContent = `Stop · ${Math.floor(ms / 1000)}s`; } });
      await noteRec.start();
      recBtn.classList.add('recording');
      const { blob } = await noteRec.done;
      noteRec = null;
      recBtn.classList.remove('recording'); recBtn.textContent = 'Saving…'; recBtn.disabled = true;
      const fd = new FormData(); fd.append('audio', blob, 'note.webm');
      const c = await api(`/tasks/${t.id}/voice-note`, { method: 'POST', body: fd });
      commentsBox.append(commentView(c)); refresh();
    } catch (e) { toast(micErr(e)); noteRec = null; recBtn.classList.remove('recording'); }
    recBtn.disabled = false; recBtn.textContent = 'Record voice note';
  });

  const patch = async (body) => {
    try { await api(`/tasks/${t.id}`, { method: 'PATCH', body }); await refresh(); } catch (e) { toast(e.message); openTask(t.id); }
  };

  const isTaskOverdue = isOverdue(t);
  const schedText = scheduleText(t) || 'No date';
  const scheduleBtn = h('button', {
    type: 'button',
    class: 'd-schedule-btn' + (isTaskOverdue ? ' overdue' : '') + (!t.due_date ? ' empty' : ''),
    'aria-label': 'Edit schedule',
    onclick: (e) => {
      e.stopPropagation();
      openDatePicker(t, scheduleBtn);
    }
  },
    h('span', { class: 'd-sched-left' },
      icon(t.due_date ? 'today' : 'nodate', { size: 16, color: isTaskOverdue ? 'var(--p1)' : 'var(--mute)', day: t.due_date ? parseISO(t.due_date).getDate() : null }),
      h('span', null, schedText)),
    isTaskOverdue ? h('span', { class: 'badge-overdue' }, 'Overdue') : null);

  const titleInput = h('input', { type: 'text', class: 'd-title', value: t.title, maxlength: 500, 'aria-label': 'Task title' });
  titleInput.addEventListener('change', () => titleInput.value.trim() && patch({ title: titleInput.value }));

  const prio = h('select', { 'aria-label': 'Priority', onchange: () => patch({ priority: Number(prio.value) }) },
    [1, 2, 3, 4].map((p) => h('option', { value: p, selected: p === t.priority }, `P${p}${p === 1 ? ' · urgent' : p === 4 ? ' · normal' : ''}`)));
  const proj = h('select', { 'aria-label': 'Project', onchange: () => patch({ project_id: Number(proj.value) }) },
    projects.map((p) => h('option', { value: p.id, selected: p.id === t.project_id }, p.id === 1 ? 'Inbox' : `# ${p.name}`)));

  const copyBtn = h('button', { class: 'small-btn', type: 'button', onclick: async () => {
    try { await navigator.clipboard.writeText(t.email); toast('Address copied'); } catch { toast(t.email); }
  } }, 'Copy');

  const sim = S.cfg.debug ? simulateBox(t, commentsBox) : null;

  fill(d,
    h('div', { class: 'drawer-head' }, h('span', { class: 'hint' }, t.done ? 'Completed' : 'Task'), h('button', { class: 'close', 'aria-label': 'Close', onclick: closeDrawer }, '✕')),
    h('div', { class: 'drawer-body' },
      titleInput,
      h('label', null, 'Schedule'), scheduleBtn,
      h('div', { class: 'row' },
        h('div', null, h('label', null, 'Priority'), prio),
        h('div', null, h('label', null, 'Project'), proj)),
      h('label', null, 'Email address for this task'),
      h('div', { class: 'email-box' }, h('code', null, t.email), copyBtn),
      h('div', { class: 'hint' }, 'Anything emailed here is added as a comment on this task.'),
      h('label', null, `Comments`), commentsBox,
      h('div', { class: 'composer' }, note,
        h('div', { class: 'row' }, h('button', { class: 'primary', style: 'padding:8px', type: 'button', onclick: sendComment }, 'Comment'), recBtn)),
      sim),
    h('div', { class: 'drawer-foot' },
      h('button', { class: 'small-btn', onclick: () => toggleDone(t, document.createElement('div')) }, t.done ? 'Reopen' : (t.recurrence ? 'Complete this occurrence' : 'Complete')),
      h('button', { class: 'small-btn danger', onclick: async () => {
        if (!confirm('Delete this task and its comments?')) return;
        await api(`/tasks/${t.id}`, { method: 'DELETE' }); closeDrawer(); refresh();
      } }, 'Delete')));
  d.hidden = false;
}

function commentView(c) {
  const kindIcons = { email: icon('bell', { size: 13 }), voice: icon('mic', { size: 13 }), text: icon('comment', { size: 13 }) };
  const label = { email: c.from || 'Email', voice: 'Voice note', text: 'Comment' }[c.kind];
  return h('div', { class: 'comment' },
    h('div', { class: 'c-head' },
      h('span', { class: 't-meta-item' }, kindIcons[c.kind] || null, h('span', null, label)),
      h('span', null, fmtStamp(c.created_at))),
    c.subject ? h('div', { class: 'c-subj' }, c.subject) : null,
    c.body ? h('div', { class: 'c-body' }, c.body) : (c.kind === 'voice' ? h('div', { class: 'c-body muted' }, 'No transcript (speech-to-text not configured)') : null),
    c.audio_url ? h('audio', { controls: true, preload: 'none', src: c.audio_url }) : null);
}

function simulateBox(t, commentsBox) {
  const subj = h('input', { type: 'text', placeholder: 'Subject' });
  const body = h('textarea', { placeholder: 'Email body…' });
  return h('details', null, h('summary', null, 'Dev: simulate an incoming email'),
    subj, body,
    h('button', { class: 'small-btn', style: 'margin-top:6px', type: 'button', onclick: async () => {
      if (!body.value.trim()) return;
      try {
        const r = await api('/dev/simulate-email', { method: 'POST', body: { task_id: t.id, subject: subj.value, body: body.value } });
        if (r.comment) { commentsBox.append(commentView(r.comment)); body.value = subj.value = ''; refresh(); }
      } catch (e) { toast(e.message); }
    } }, 'Send'));
}

// ------------------------------------------------------------------ reminders (browser notifications while the tab is open)
async function enableNotifications() {
  const p = await Notification.requestPermission();
  toast(p === 'granted' ? 'Reminders on while Taskly is open.' : 'Notifications were not allowed.');
  renderSide();
}

async function checkReminders() {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  try {
    const tasks = await api('/tasks?view=today');
    const now = new Date();
    for (const t of tasks) {
      if (!t.due_time || t.due_date !== todayISO()) continue;
      const [hh, mm] = t.due_time.split(':').map(Number);
      const due = new Date(); due.setHours(hh, mm, 0, 0);
      const late = now - due;
      const key = `notified:${t.id}:${t.due_date}:${t.due_time}`;
      if (late >= 0 && late < 10 * 60000) {
        let seen = false;
        try { seen = localStorage.getItem(key); localStorage.setItem(key, '1'); } catch { /* private mode */ }
        if (!seen) new Notification(t.title, { body: t.recurrence_text || `Due ${fmtTime(t.due_time)}` });
      }
    }
  } catch { /* offline: try next tick */ }
}

// ------------------------------------------------------------------ keyboard + boot
document.addEventListener('keydown', (e) => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if (e.key === 'Escape') {
    if (activeDP) { closeDatePicker(); return; }
    closeDrawer();
  }
  if (e.key === 'q' && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); addInput.focus(); }
});
window.addEventListener('focus', () => refresh().catch(() => {}));

(async function boot() {
  try { S.cfg = await api('/config'); } catch { /* keep defaults */ }
  await refresh().catch((e) => toast(e.message));
  setInterval(checkReminders, 30000);
  setInterval(() => refresh().catch(() => {}), 120000);
})();
