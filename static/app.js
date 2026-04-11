// static/app.js

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const statusMsg = document.getElementById('status-message');
const resultSection = document.getElementById('result-section');
const resultBody = document.getElementById('result-body');
const totalAmount = document.getElementById('total-amount');

// ===== 업로드 이벤트 =====

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', () => handleFiles(fileInput.files));

document.getElementById('print-btn').addEventListener('click', () => {
  document.getElementById('print-date').textContent = new Date().toLocaleDateString('ko-KR');
  window.print();
});

document.getElementById('add-row-btn').addEventListener('click', addEmptyRow);

document.getElementById('reset-btn').addEventListener('click', () => {
  resultBody.innerHTML = '';
  resultSection.classList.add('hidden');
  fileInput.value = '';
  updateTotal();
});

// ===== 파일 처리 =====

async function handleFiles(files) {
  if (!files || files.length === 0) return;

  showStatus('처리 중입니다...', 'loading');

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
    renderResults(data);
  } catch (err) {
    showStatus('서버 연결에 실패했습니다. 앱이 실행 중인지 확인해 주세요.', 'error');
  }
}

// ===== 결과 렌더링 =====

function renderResults(receipts) {
  resultSection.classList.remove('hidden');

  for (const receipt of receipts) {
    const items = receipt.items || [];

    if (items.length === 0) {
      addRow(receipt.store_name || '', receipt.date || '', '(항목 없음)', receipt.total || 0);
    } else {
      for (const item of items) {
        addRow(
          receipt.store_name || '',
          receipt.date || '',
          item.name || '',
          item.amount ?? receipt.total ?? 0
        );
      }
    }
  }

  updateTotal();
}

function addRow(storeName, date, itemName, amount) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" value="${esc(storeName)}" placeholder="가게명"></td>
    <td><input type="text" value="${esc(date)}" placeholder="YYYY-MM-DD"></td>
    <td><input type="text" value="${esc(itemName)}" placeholder="항목"></td>
    <td><input type="number" value="${amount}" placeholder="0" class="amount-input"></td>
    <td class="no-print"><button class="delete-btn" onclick="deleteRow(this)">✕</button></td>
  `;
  tr.querySelectorAll('.amount-input').forEach(el => el.addEventListener('input', updateTotal));
  resultBody.appendChild(tr);
}

function addEmptyRow() {
  resultSection.classList.remove('hidden');
  addRow('', '', '', 0);
  updateTotal();
}

function deleteRow(btn) {
  btn.closest('tr').remove();
  updateTotal();
}

function updateTotal() {
  const inputs = resultBody.querySelectorAll('.amount-input');
  const sum = Array.from(inputs).reduce((acc, el) => acc + (parseFloat(el.value) || 0), 0);
  totalAmount.textContent = sum.toLocaleString('ko-KR');
}

// ===== 유틸 =====

function showStatus(msg, type) {
  statusMsg.textContent = msg;
  statusMsg.className = `status ${type}`;
}

function hideStatus() {
  statusMsg.className = 'status hidden';
}

function esc(str) {
  return String(str ?? '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
