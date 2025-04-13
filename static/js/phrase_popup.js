// 전역 변수 선언
let phrasesData = JSON.parse(document.getElementById('phrases-data').textContent);
let isEditingMode = false;
let isAddingNew = false;
let pendingChanges = { updates: [], deletes: [] };
let selectedPhrases = {}; // 탭별 선택된 문구 저장
let lastActiveTabId = localStorage.getItem('lastActiveTabId') || null; // 탭 고정

function renderAllPhrases() {
  for (const category in phrasesData) {
    renderPhrases(category, phrasesData[category]);
  }

  if (lastActiveTabId) {
    const tabTrigger = document.querySelector(`.nav-link[data-bs-target='${lastActiveTabId}']`);
    if (tabTrigger) new bootstrap.Tab(tabTrigger).show();
  }
}

// DOM 로드 완료 시 초기화
window.addEventListener('DOMContentLoaded', () => {
  // ✅ 탭 이동 시 신규/수정 모드 초기화
  document.querySelectorAll('.nav-tabs .nav-link').forEach(btn => {
    btn.addEventListener('show.bs.tab', function () {
      if (isAddingNew) {
        cancelNewPhrase(); // 신규 모드 종료
      }
      if (isEditingMode) {
        isEditingMode = false;
        const editBtn = document.querySelector('.btn[onclick="startEdit()"]');
        if (editBtn) {
          editBtn.textContent = '수정';
          editBtn.classList.replace('btn-primary', 'btn-outline-secondary');
        }
        renderAllPhrases(); // 수정모드 종료 후 재렌더링
      }
      lastActiveTabId = this.getAttribute('data-bs-target');
      localStorage.setItem('lastActiveTabId', lastActiveTabId);
    });
  });

  renderAllPhrases();
});

function renderPhrases(category, phraseList) {
  const container = document.getElementById(`${category}PhraseList`);
  if (!container) return;

  container.innerHTML = '';

  const list = document.createElement('div');
  list.className = 'd-flex flex-column gap-2';
  list.setAttribute('data-category', category);

  if (phraseList.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'text-muted';
    empty.style.fontSize = '0.8rem';
    empty.textContent = '저장된 문구가 없습니다.';
    list.appendChild(empty);
  }

  phraseList.sort((a, b) => {
    const afav = a.note && a.note.includes('★') ? -1 : 0;
    const bfav = b.note && b.note.includes('★') ? -1 : 0;
    return afav - bfav || (a.order || 0) - (b.order || 0);
  });

  phraseList.forEach((p, index) => {
    const item = document.createElement('div');
    item.className = 'phrase-item';
    item.dataset.id = p.id;
    item.dataset.category = category;
    item.dataset.index = index;

    item.innerHTML = `
    <div class="input-container d-flex align-items-center gap-2">
      <input type="text" class="form-control phrase-name" name="edit-name" value="${p.name}" ${isEditingMode ? '' : 'disabled'}>
      <input type="text" class="form-control phrase-content" name="edit-content" value="${p.content}" ${isEditingMode ? '' : 'disabled'}>
      <input type="text" class="form-control phrase-note" name="edit-note" value="${p.note || ''}" ${isEditingMode ? '' : 'disabled'}>
      <button class="btn btn-sm btn-outline-warning toggle-fav">${p.note?.includes('★') ? '★' : '☆'}</button>
      ${isEditingMode ? `
        <button class="btn btn-sm btn-danger delete-btn">×</button>
      ` : ''}
    </div>
    `;

    list.appendChild(item);
  });

  container.appendChild(list);

  list.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.closest('.phrase-item').dataset.id;
      queueDeletePhrase(id, btn);
    });
  });

  list.querySelectorAll('.phrase-name, .phrase-content, .phrase-note').forEach(input => {
    input.addEventListener('input', () => {
      if (!isEditingMode) return;
      queueEditPhrase(input.closest('.phrase-item'));
    });
  });

  list.querySelectorAll('.toggle-fav').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.phrase-item');
      const id = item.dataset.id;
      const cat = item.dataset.category;
      const phrase = phrasesData[cat].find(p => p.id == id);
      phrase.note = phrase.note?.includes('★') ? phrase.note.replace('★', '').trim() : `★ ${phrase.note || ''}`.trim();
      saveFavorite(phrase);
    });
  });
}


function saveFavorite(phrase) {
  if (isEditingMode) {
    const dummyItem = document.createElement('div');
    dummyItem.dataset.id = phrase.id;
    dummyItem.dataset.category = phrase.category;
    dummyItem.dataset.order = phrase.order || 0; //  이 줄 추가
    dummyItem.innerHTML = `
      <input name="edit-name" value="${phrase.name}">
      <input name="edit-content" value="${phrase.content}">
      <input name="edit-note" value="${phrase.note}">
    `;
    queueEditPhrase(dummyItem);
    renderAllPhrases();
  } else {
    fetch('/label/phrases/manage/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: JSON.stringify({
        action: 'update',
        id: phrase.id,
        name: phrase.name,
        content: phrase.content,
        note: phrase.note,
        category: phrase.category
      })
    }).then(res => res.json()).then(data => {
      if (data.success) reloadPopupData();
    });
  }
}

// 신규 문구 추가
function addNewPhrase() {
  console.log('addNewPhrase called, isEditingMode:', isEditingMode, 'isAddingNew:', isAddingNew);
  if (isEditingMode) {
    console.log('Cannot add: Edit mode active');
    return;
  }
  if (isAddingNew) {
    saveNewPhrase();
    return;
  }

  const activeTab = document.querySelector('.tab-pane.active');
  if (!activeTab) {
    console.error('Active tab not found');
    return;
  }
  const category = activeTab.id.replace('-tab', '');
  const container = document.getElementById(`${category}PhraseList`);
  const addButton = document.querySelector('.btn[onclick="addNewPhrase()"]');

  const inputRow = document.createElement('div');
  inputRow.className = 'phrase-item new-input-row';
  inputRow.innerHTML = `
    <div class="input-container">
      <button type="button" class="btn btn-sm btn-outline-info" onclick="showSuggestions('${category}')">추천</button>
      <input type="text" class="form-control phrase-name" placeholder="문구명" name="new-name">
      <input type="text" class="form-control phrase-content" placeholder="문구 내용" name="new-content">
      <input type="text" class="form-control phrase-note" placeholder="참고사항" name="new-note">
    </div>
    <div class="button-container">
      <button type="button" class="btn btn-sm btn-outline-danger" onclick="cancelNewPhrase()">×</button>
    </div>
  `;
  container.insertBefore(inputRow, container.firstChild);
  if (addButton) {
    addButton.textContent = '저장';
    addButton.classList.replace('btn-outline-primary', 'btn-primary');
    console.log('Add button updated to "저장"');
  }
  isAddingNew = true;
}

// 신규 문구 저장
function saveNewPhrase() {
  console.log('saveNewPhrase called');
  const activeTab = document.querySelector('.tab-pane.active');
  if (!activeTab) {
    console.error('Active tab not found');
    return;
  }
  const category = activeTab.id.replace('-tab', '');
  const inputRow = document.querySelector('.new-input-row');
  if (!inputRow) {
    console.error('New input row not found');
    return;
  }

  const newPhrase = {
    action: 'add',
    name: inputRow.querySelector('[name="new-name"]').value || '',
    content: inputRow.querySelector('[name="new-content"]').value || '',
    note: inputRow.querySelector('[name="new-note"]').value || '',
    category: category
  };
  console.log('Saving new phrase:', newPhrase);

  fetch('/label/phrases/manage/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
    },
    body: JSON.stringify(newPhrase)
  })
    .then(response => {
      console.log('Save response status:', response.status);
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      return response.json();
    })
    .then(data => {
      console.log('Save response:', data);
      if (data.success) {
        reloadPopupData();
      } else {
        alert('문구 추가 실패: ' + (data.error || '알 수 없는 오류'));
      }
    })
    .catch(error => {
      console.error('Save error:', error);
      alert('문구 추가 중 오류: ' + error.message);
    });
}

// 신규 문구 취소
function cancelNewPhrase() {
  console.log('cancelNewPhrase called');
  const addButton = document.querySelector('.btn[onclick="addNewPhrase()"]');
  const inputRow = document.querySelector('.new-input-row');
  if (inputRow) inputRow.remove();
  if (addButton) {
    addButton.textContent = '신규';
    addButton.classList.replace('btn-primary', 'btn-outline-primary');
    console.log('Add button reset to "신규"');
  }
  isAddingNew = false;
}

function startEdit() {
  console.log('startEdit called, isAddingNew:', isAddingNew);
  if (isAddingNew) {
    console.log('Cannot edit: Add mode active');
    return;
  }

  isEditingMode = !isEditingMode;
  console.log('Edit mode:', isEditingMode);
  const editButton = document.querySelector('.btn[onclick="startEdit()"]');

  if (isEditingMode) {
    editButton.textContent = '저장';
    editButton.classList.replace('btn-outline-secondary', 'btn-primary');
    pendingChanges = { updates: [], deletes: [] };
    console.log('Edit button updated to "저장"');
  } else {
    saveChanges();
    editButton.textContent = '수정';
    editButton.classList.replace('btn-primary', 'btn-outline-secondary');
    console.log('Edit button reset to "수정"');
  }

  renderAllPhrases();
}

// 수정 대기열 추가
function queueEditPhrase(item) {
  const phraseId = item.dataset.id;
  const category = item.dataset.category || document.querySelector('.tab-pane.active').id.replace('-tab', '');
  const original = phrasesData[category].find(p => p.id == phraseId);
  const updatedPhrase = {
    action: 'update',
    id: phraseId,
    name: item.querySelector('[name="edit-name"]')?.value || original?.name || '',
    content: item.querySelector('[name="edit-content"]')?.value || original?.content || '',
    note: item.querySelector('[name="edit-note"]')?.value || original?.note || '',
    category,
    order: Number(item.dataset.order) || original?.order || 0 // 추가된 부분
  };
  
  updatedPhrase.order = original?.order || 0;

  console.log('Queuing edit:', updatedPhrase);

  const existingIndex = pendingChanges.updates.findIndex(p => p.id === phraseId);
  if (existingIndex >= 0) {
    pendingChanges.updates[existingIndex] = updatedPhrase;
  } else {
    pendingChanges.updates.push(updatedPhrase);
  }
}

// 삭제 대기열 추가
function queueDeletePhrase(phraseId, button) {
  console.log('Queuing delete for ID:', phraseId);
  pendingChanges.deletes.push({ action: 'delete', id: phraseId });
  button.closest('.phrase-item').remove();
}

// 변경 사항 저장
function saveChanges() {
  console.log('saveChanges called');
  if (pendingChanges.updates.length === 0 && pendingChanges.deletes.length === 0) {
    console.log('No changes to save');
    isEditingMode = false;
    renderAllPhrases();
    return;
  }

  const changes = [...pendingChanges.updates, ...pendingChanges.deletes];
  console.log('Saving changes:', changes);

  fetch('/label/phrases/manage/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
    },
    body: JSON.stringify(changes)
  })
    .then(response => {
      console.log('Save changes response status:', response.status);
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      return response.json();
    })
    .then(data => {
      console.log('Save changes response:', data);
      if (data.success) {
        reloadPopupData();
      } else {
        alert('변경 사항 저장 실패: ' + (data.error || '알 수 없는 오류'));
      }
    })
    .catch(error => {
      console.error('Save changes error:', error);
      alert('변경 사항 저장 중 오류: ' + error.message);
    });
}

// 팝업 데이터 새로고침
function reloadPopupData() {
  console.log('Reloading popup data');
  fetch('/label/phrases/', { cache: 'no-store' })
    .then(response => {
      console.log('Reload response status:', response.status);
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      return response.text();
    })
    .then(html => {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const newContent = doc.querySelector('.container-fluid.phrase-popup');
      if (!newContent) {
        console.error('Phrase popup container not found in response');
        return;
      }
      document.querySelector('.container-fluid.phrase-popup').outerHTML = newContent.outerHTML;
      phrasesData = JSON.parse(doc.getElementById('phrases-data').textContent);
      console.log('Updated phrases data:', phrasesData);
      isEditingMode = false;
      isAddingNew = false;
      pendingChanges = { updates: [], deletes: [] };
      // 선택 상태 유지
      const tempSelected = { ...selectedPhrases };
      selectedPhrases = {};
      renderAllPhrases();
      Object.keys(tempSelected).forEach(category => {
        if (category === 'cautions' || category === 'additional_info') {
          selectedPhrases[category] = [...tempSelected[category]];
        } else {
          selectedPhrases[category] = tempSelected[category];
        }
      });
    })
    .catch(error => {
      console.error('Reload error:', error);
      alert('팝업 새로고침 오류: ' + error.message);
    });
}

// 추천 문구 표시
function showSuggestions(category) {
  console.log('showSuggestions called for category:', category);
  fetch(`/label/phrases/suggestions/?category=${category}`)
    .then(response => {
      console.log('Suggestions response status:', response.status);
      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
      return response.json();
    })
    .then(data => {
      if (data.success) {
        const suggestions = data.suggestions;
        const modal = document.createElement('div');
        modal.className = 'suggestion-modal';
        modal.innerHTML = `
          <ul>
            ${suggestions.map(s => `<li onclick="applySuggestion('${s.name}', '${s.content}', '${s.note || ''}')">${s.name}</li>`).join('')}
          </ul>
          <button type="button" class="btn btn-sm btn-secondary" onclick="this.parentElement.remove()">닫기</button>
        `;
        document.body.appendChild(modal);
      } else {
        alert('추천 문구 불러오기 실패: ' + (data.error || '알 수 없는 오류'));
      }
    })
    .catch(error => {
      console.error('Suggestions error:', error);
      alert('추천 문구 불러오기 오류: ' + error.message);
    });
}

// 추천 문구 적용
function applySuggestion(name, content, note) {
  console.log('applySuggestion called:', { name, content, note });
  const row = document.querySelector('.new-input-row');
  if (row) {
    row.querySelector('[name="new-name"]').value = name;
    row.querySelector('[name="new-content"]').value = content;
    row.querySelector('[name="new-note"]').value = note;
    document.querySelector('.suggestion-modal').remove();
  }
}