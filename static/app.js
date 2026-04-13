// static/app.js

const CATEGORIES = ['식비','유류비','교통비','주차비','숙박비','접대비','소모품','운반비','기타'];
const STORAGE_KEY = 'mak_expense_report_v1';

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const statusMsg = document.getElementById('status-message');

const expenseBody = document.getElementById('expense-body');
const fuelBody = document.getElementById('fuel-body');
const tripBody = document.getElementById('trip-body');

// ===== 초기 세팅 =====
document.getElementById('meta-date').valueAsDate = new Date();

// ===== 업로드 이벤트 =====
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

// ===== 버튼 =====
document.getElementById('print-btn').addEventListener('click', () => window.print());
document.getElementById('add-expense-btn').addEventListener('click', () => addExpenseRow({}));
document.getElementById('add-fuel-btn').addEventListener('click', () => addFuelRow({}));
document.getElementById('add-trip-btn').addEventListener('click', () => addTripRow({}));
document.getElementById('save-btn').addEventListener('click', saveData);
document.getElementById('load-btn').addEventListener('click', loadData);
document.getElementById('reset-btn').addEventListener('click', resetData);

// ===== 파일 처리 =====
async function handleFiles(files) {
  if (!files || files.length === 0) return;
  showStatus('AI가 영수증을 분석하고 있습니다...', 'loading');

  const formData = new FormData();
  for (const file of files) formData.append('files', file);

  try {
    const res = await fetch('/process', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) {
      showStatus(data.error || '오류가 발생했습니다.', 'error');
      return;
    }
    hideStatus();
    appendReceipts(data);
    fileInput.value = '';
  } catch (err) {
    showStatus('서버 연결에 실패했습니다.', 'error');
  }
}

// ===== 영수증 → 개인경비 테이블 =====
function appendReceipts(receipts) {
  let okCount = 0, errCount = 0;
  for (const r of receipts) {
    if (r.error) { errCount++; continue; }
    const { month, day } = parseDate(r.date);
    const category = CATEGORIES.includes(r.category) ? r.category : '기타';
    const amount = Math.abs(parseInt(r.total) || 0);
    const memo = [r.store_name, itemsToMemo(r.items)].filter(Boolean).join(' / ');
    addExpenseRow({ month, day, category, amount, memo, voucher: '' });
    okCount++;
  }
  recalc();
  if (errCount > 0) showStatus(`${okCount}건 추가됨. ${errCount}건 실패.`, 'error');
}

function itemsToMemo(items) {
  if (!Array.isArray(items) || items.length === 0) return '';
  return items.slice(0, 3).map(i => i.name).filter(Boolean).join(', ');
}

function parseDate(dateStr) {
  if (!dateStr) return { month: '', day: '' };
  const m = String(dateStr).match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!m) return { month: '', day: '' };
  return { month: String(parseInt(m[2])), day: String(parseInt(m[3])) };
}

// ===== 개인경비 행 =====
function addExpenseRow(data) {
  const tr = document.createElement('tr');
  const amountCells = CATEGORIES.map(cat => {
    const val = (data.category === cat && data.amount) ? data.amount : '';
    return `<td class="num-cell"><input type="number" class="amount cat-${cat}" data-cat="${cat}" value="${esc(val)}"></td>`;
  }).join('');
  tr.innerHTML = `
    <td class="sm"><input type="text" value="${esc(data.month || '')}" maxlength="2"></td>
    <td class="sm"><input type="text" value="${esc(data.day || '')}" maxlength="2"></td>
    ${amountCells}
    <td class="sm"><input type="text" value="${esc(data.voucher || '')}" placeholder="번호"></td>
    <td><input type="text" value="${esc(data.memo || '')}" placeholder="적요"></td>
    <td class="no-print"><button class="del-btn">✕</button></td>
  `;
  tr.querySelectorAll('input').forEach(el => el.addEventListener('input', recalc));
  tr.querySelector('.del-btn').addEventListener('click', () => { tr.remove(); recalc(); });
  expenseBody.appendChild(tr);
}

// ===== 차량 유류비 행 =====
function addFuelRow(data) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="sm"><input type="text" value="${esc(data.month || '')}"></td>
    <td class="sm"><input type="text" value="${esc(data.day || '')}"></td>
    <td><input type="text" value="${esc(data.from || '')}"></td>
    <td><input type="text" value="${esc(data.to || '')}"></td>
    <td class="sm"><input type="number" value="${esc(data.km || '')}"></td>
    <td class="num-cell"><input type="number" class="fuel-amount" value="${esc(data.amount || '')}"></td>
    <td><input type="text" value="${esc(data.memo || '')}"></td>
    <td class="no-print"><button class="del-btn">✕</button></td>
  `;
  tr.querySelectorAll('input').forEach(el => el.addEventListener('input', recalc));
  tr.querySelector('.del-btn').addEventListener('click', () => { tr.remove(); recalc(); });
  fuelBody.appendChild(tr);
}

// ===== 출장일비 행 =====
function addTripRow(data) {
  const tr = document.createElement('tr');
  const idx = tripBody.children.length + 1;
  tr.innerHTML = `
    <td class="sm">${idx}</td>
    <td class="sm"><input type="number" value="${esc(data.days || '')}" placeholder="출장일수"></td>
    <td class="num-cell"><input type="number" class="trip-amount" value="${esc(data.amount || '')}"></td>
    <td><input type="text" value="${esc(data.period || '')}" placeholder="기간"></td>
    <td><input type="text" value="${esc(data.place || '')}" placeholder="출장지"></td>
    <td><input type="text" value="${esc(data.memo || '')}"></td>
    <td class="no-print"><button class="del-btn">✕</button></td>
  `;
  tr.querySelectorAll('input').forEach(el => el.addEventListener('input', recalc));
  tr.querySelector('.del-btn').addEventListener('click', () => {
    tr.remove();
    renumberTrip();
    recalc();
  });
  tripBody.appendChild(tr);
}

function renumberTrip() {
  Array.from(tripBody.children).forEach((tr, i) => {
    tr.firstElementChild.textContent = i + 1;
  });
}

// ===== 합계 계산 =====
function recalc() {
  // 개인경비 카테고리별
  let expenseSum = 0;
  CATEGORIES.forEach(cat => {
    const inputs = expenseBody.querySelectorAll(`input.cat-${cat}`);
    const s = Array.from(inputs).reduce((a, el) => a + (parseFloat(el.value) || 0), 0);
    document.querySelector(`[data-sum="${cat}"]`).textContent = s.toLocaleString('ko-KR');
    expenseSum += s;
  });
  document.getElementById('expense-sum').textContent = expenseSum.toLocaleString('ko-KR');

  // 유류비
  const fuelSum = Array.from(fuelBody.querySelectorAll('.fuel-amount'))
    .reduce((a, el) => a + (parseFloat(el.value) || 0), 0);
  document.getElementById('fuel-sum').textContent = fuelSum.toLocaleString('ko-KR');

  // 출장일비
  const tripSum = Array.from(tripBody.querySelectorAll('.trip-amount'))
    .reduce((a, el) => a + (parseFloat(el.value) || 0), 0);
  document.getElementById('trip-sum').textContent = tripSum.toLocaleString('ko-KR');

  // 국내 합계 = 개인경비 + 유류비 + 출장일비
  document.getElementById('grand-total').textContent =
    (expenseSum + fuelSum + tripSum).toLocaleString('ko-KR');
}

// ===== 저장 / 불러오기 / 초기화 =====
function collectData() {
  return {
    meta: {
      name: document.getElementById('meta-name').value,
      dept: document.getElementById('meta-dept').value,
      period: document.getElementById('meta-period').value,
      date: document.getElementById('meta-date').value,
    },
    expenses: Array.from(expenseBody.children).map(tr => {
      const inputs = tr.querySelectorAll('input');
      const row = { month: inputs[0].value, day: inputs[1].value };
      CATEGORIES.forEach((cat, i) => { row[cat] = inputs[2 + i].value; });
      row.voucher = inputs[11].value;
      row.memo = inputs[12].value;
      return row;
    }),
    fuels: Array.from(fuelBody.children).map(tr => {
      const i = tr.querySelectorAll('input');
      return { month: i[0].value, day: i[1].value, from: i[2].value, to: i[3].value, km: i[4].value, amount: i[5].value, memo: i[6].value };
    }),
    trips: Array.from(tripBody.children).map(tr => {
      const i = tr.querySelectorAll('input');
      return { days: i[0].value, amount: i[1].value, period: i[2].value, place: i[3].value, memo: i[4].value };
    }),
  };
}

function saveData() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(collectData()));
  showStatus('임시저장 완료 (이 브라우저에만 저장됨)', 'success');
  setTimeout(hideStatus, 2000);
}

function loadData() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) { showStatus('저장된 데이터가 없습니다.', 'error'); return; }
  const data = JSON.parse(raw);
  clearAll();
  document.getElementById('meta-name').value = data.meta?.name || '';
  document.getElementById('meta-dept').value = data.meta?.dept || '';
  document.getElementById('meta-period').value = data.meta?.period || '1차 (1일 ~ 15일)';
  document.getElementById('meta-date').value = data.meta?.date || '';
  (data.expenses || []).forEach(r => {
    // 가장 큰 값의 카테고리만 복원하면 여러 카테고리 한 행 불가 → 직접 셀 채움
    const tr = document.createElement('tr');
    const amountCells = CATEGORIES.map(cat =>
      `<td class="num-cell"><input type="number" class="amount cat-${cat}" data-cat="${cat}" value="${esc(r[cat] || '')}"></td>`
    ).join('');
    tr.innerHTML = `
      <td class="sm"><input type="text" value="${esc(r.month || '')}" maxlength="2"></td>
      <td class="sm"><input type="text" value="${esc(r.day || '')}" maxlength="2"></td>
      ${amountCells}
      <td class="sm"><input type="text" value="${esc(r.voucher || '')}" placeholder="번호"></td>
      <td><input type="text" value="${esc(r.memo || '')}" placeholder="적요"></td>
      <td class="no-print"><button class="del-btn">✕</button></td>
    `;
    tr.querySelectorAll('input').forEach(el => el.addEventListener('input', recalc));
    tr.querySelector('.del-btn').addEventListener('click', () => { tr.remove(); recalc(); });
    expenseBody.appendChild(tr);
  });
  (data.fuels || []).forEach(r => addFuelRow(r));
  (data.trips || []).forEach(r => addTripRow(r));
  recalc();
  showStatus('불러오기 완료', 'success');
  setTimeout(hideStatus, 2000);
}

function clearAll() {
  expenseBody.innerHTML = '';
  fuelBody.innerHTML = '';
  tripBody.innerHTML = '';
  recalc();
}

function resetData() {
  if (!confirm('모든 입력을 초기화하시겠습니까?')) return;
  clearAll();
  document.getElementById('meta-name').value = '';
  document.getElementById('meta-dept').value = '';
  document.getElementById('meta-date').valueAsDate = new Date();
}

// ===== 상태 메시지 =====
function showStatus(msg, type) {
  statusMsg.textContent = msg;
  statusMsg.className = `status ${type}`;
}
function hideStatus() { statusMsg.className = 'status hidden'; }

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 초기 렌더
recalc();
