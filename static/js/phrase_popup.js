// 전역 변수 선언
let phrasesData = JSON.parse(document.getElementById('phrases-data').textContent);
let isEditingMode = false;
let isAddingNew = false;
let pendingChanges = { updates: [], deletes: [] };
let selectedPhrases = {}; // 탭별 선택된 문구 저장
let lastActiveTabId = localStorage.getItem('lastActiveTabId') || null; // 탭 고정
let currentActiveTab = ''; // 전역 변수로 현재 활성화된 탭 저장

// 카테고리 매핑 추가
const categoryMapping = {
    'label_name': '라벨명',
    'food_type': '식품유형',
    'product_name': '제품명',
    'ingredient_info': '성분명 및 함량',
    'content_weight': '내용량',
    'weight_calorie': '내용량(열량)',
    'report_no': '품목보고번호',
    'storage': '보관방법',
    'package': '용기.포장재질',
    'manufacturer': '제조원 소재지',
    'distributor': '유통전문판매원',
    'repacker': '소분원',
    'importer': '수입원',
    'expiry': '소비기한',
    'cautions': '주의사항',
    'additional': '기타표시사항'
};

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

// DOM 로드 시 초기화 코드 수정
document.addEventListener('DOMContentLoaded', function() {
    // 탭 변경 이벤트 리스너
    document.querySelectorAll('.nav-link').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const targetId = e.target.getAttribute('data-bs-target');
            localStorage.setItem('lastActiveTab', targetId);
            currentActiveTab = targetId.replace('#', '').replace('-tab', '');

            // 신규 또는 수정 모드일 때 취소 처리
            if (isAddingNew) {
                cancelNewPhrase();
            }
            if (isEditingMode) {
                // 수정 모드 취소
                isEditingMode = false;
                const editButton = document.querySelector('.btn[onclick="startEdit()"]');
                if (editButton) {
                    editButton.textContent = '수정';
                    editButton.classList.replace('btn-primary', 'btn-outline-secondary');
                }
                // 변경사항 취소 및 목록 새로고침
                pendingChanges = { updates: [], deletes: [] };
                renderAllPhrases();
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
    // 마지막 활성 탭 복원
    const lastActiveTab = localStorage.getItem('lastActiveTab');
    if (lastActiveTab) {
        const tabEl = document.querySelector(`button[data-bs-target="${lastActiveTab}"]`);
        if (tabEl) {
            new bootstrap.Tab(tabEl).show();
        }
    }

    // 탭 변경 이벤트 리스너
    document.querySelectorAll('.nav-link').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const targetId = e.target.getAttribute('data-bs-target');
            localStorage.setItem('lastActiveTab', targetId);
            currentActiveTab = targetId.replace('#', '').replace('-tab', '');

            // 편집 중이거나 새로 추가 중인 경우 확인
            if (isEditingMode || isAddingNew) {
                if (confirm('편집 중인 내용이 있습니다. 변경사항을 취소하시겠습니까?')) {
                    cancelEditing();
                } else {
                    // 이전 탭으로 복귀
                    const previousTab = e.relatedTarget;
                    if (previousTab) {
                        new bootstrap.Tab(previousTab).show();
                    }
                }
            }
        });
    });

    // 신규 버튼 이벤트 리스너
    document.querySelector('.btn-add-new').addEventListener('click', addNewPhrase);
});

function renderPhrases(category, phraseList) {
  const container = document.getElementById(`${category}PhraseList`);
  if (!container) return;

  container.innerHTML = '';

  const list = document.createElement('div');
  list.className = 'd-flex flex-column gap-2';
  list.setAttribute('data-category', category);

  // 사용자 문구가 없으면 추천 문구 표시
  if (phraseList.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'text-muted';
    empty.style.fontSize = '0.8rem';
      empty.textContent = '저장된 문구가 없습니다. "신규" 버튼으로 문구를 추가하거나 추천 문구를 사용하세요.';
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

// addNewPhrase 함수 수정
function addNewPhrase() {
    const addButton = document.querySelector('[onclick="addNewPhrase()"]');
    
  if (isAddingNew) {
    saveNewPhrase();
    return;
  }

    if (isEditingMode) {
        alert('편집 모드에서는 새 문구를 추가할 수 없습니다.');
    return;
  }

    isAddingNew = true;
    const category = currentActiveTab || document.querySelector('.tab-pane.active').id.replace('-tab', '');
    const phraseList = document.getElementById(`${category}PhraseList`);
    
    if (addButton) {
        addButton.textContent = '저장';
        addButton.classList.remove('btn-outline-primary');
        addButton.classList.add('btn-primary');
    }

    const newRow = document.createElement('div');
    newRow.className = 'phrase-item new-input-row';
    newRow.innerHTML = `
      <div class="input-container d-flex align-items-center gap-2">
          <div class="d-flex align-items-center gap-2 flex-grow-1">
              <div class="suggest-container" style="position: relative; min-width: 100px;">
                  <button type="button" class="btn btn-sm btn-outline-secondary suggest-btn">추천</button>
                  <div class="suggestions-dropdown" style="display: none;"></div>
    </div>
              <input type="text" class="form-control phrase-name" name="new-name" placeholder="문구명" required>
              <input type="text" class="form-control phrase-content" name="new-content" placeholder="내용" required>
              <input type="text" class="form-control phrase-note" name="new-note" placeholder="비고">
          </div>
          <button type="button" class="btn btn-sm btn-danger cancel-new">×</button>
    </div>
  `;

    // 이벤트 리스너 추가
    newRow.querySelector('.suggest-btn').addEventListener('click', (e) => {
        const suggestionsContainer = newRow.querySelector('.suggestions-dropdown');
        suggestionsContainer.style.display = 
            suggestionsContainer.style.display === 'none' ? 'block' : 'none';
        showSuggestions(category, suggestionsContainer);
        e.stopPropagation();
    });

    // 문서 클릭 시 추천 목록 닫기
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.suggest-container')) {
            const suggestionsDropdowns = document.querySelectorAll('.suggestions-dropdown');
            suggestionsDropdowns.forEach(dropdown => dropdown.style.display = 'none');
        }
    });

    phraseList.insertBefore(newRow, phraseList.firstChild);
    newRow.querySelector('[name="new-name"]').focus();
  }

// saveNewPhrase 함수 수정
async function saveNewPhrase() {
  const inputRow = document.querySelector('.new-input-row');
  if (!inputRow) return;

  const nameInput = inputRow.querySelector('[name="new-name"]');
  const contentInput = inputRow.querySelector('[name="new-content"]');
  const noteInput = inputRow.querySelector('[name="new-note"]');
  
  if (!nameInput.value.trim() || !contentInput.value.trim()) {
      alert('문구명과 내용은 필수 입력항목입니다.');
    return;
  }

  try {
      const response = await fetch('/label/phrases/manage/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
    },
          body: JSON.stringify({
              action: 'create',
              my_phrase_name: nameInput.value.trim(),
              category_name: currentActiveTab,
              comment_content: contentInput.value.trim(),
              note: noteInput.value.trim()
          })
      });

      const result = await response.json();
      if (result.success) {
          // 저장 성공 시 UI 초기화
          const addButton = document.querySelector('[onclick="addNewPhrase()"]');
          if (addButton) {
              addButton.textContent = '신규';
              addButton.classList.remove('btn-primary');
              addButton.classList.add('btn-outline-primary');
          }
          isAddingNew = false;
          
          // 입력 행 제거 및 데이터 새로고침
          inputRow.remove();
          await reloadPopupData();
          
          // 현재 활성 탭 유지
          if (currentActiveTab) {
              const tabEl = document.querySelector(`button[data-bs-target="#${currentActiveTab}-tab"]`);
              if (tabEl) {
                  new bootstrap.Tab(tabEl).show();
              }
          }
      } else {
          alert('저장 실패: ' + (result.error || '알 수 없는 오류'));
      }
  } catch (error) {
      console.error('Save error:', error);
      alert('저장 중 오류가 발생했습니다.');
  }
}

// 신규 문구 취소
function cancelNewPhrase() {
    const addButton = document.querySelector('[onclick="addNewPhrase()"]');
  if (addButton) {
    addButton.textContent = '신규';
        addButton.classList.remove('btn-primary');
        addButton.classList.add('btn-outline-primary');
    }
    
    const inputRow = document.querySelector('.new-input-row');
    if (inputRow) {
        inputRow.remove();
  }
    
  isAddingNew = false;
}

// startEdit 함수 수정
function startEdit() {
  if (isAddingNew) {
        cancelNewPhrase();
  }

  isEditingMode = !isEditingMode;
  const editButton = document.querySelector('.btn[onclick="startEdit()"]');

  if (isEditingMode) {
    editButton.textContent = '저장';
    editButton.classList.replace('btn-outline-secondary', 'btn-primary');
    pendingChanges = { updates: [], deletes: [] };
  } else {
    saveChanges();
    editButton.textContent = '수정';
    editButton.classList.replace('btn-primary', 'btn-outline-secondary');
  }

  renderAllPhrases();
}

function saveChanges() {
  console.log('saveChanges called');
  if (pendingChanges.updates.length === 0 && pendingChanges.deletes.length === 0) {
      console.log('No changes to save');
      isEditingMode = false;
      renderAllPhrases();
      return;
  }

  const changes = [...pendingChanges.updates, ...pendingChanges.deletes];
  fetch('/label/phrases/manage/', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: JSON.stringify(changes)
  })
      .then(response => {
          if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
          return response.json();
      })
      .then(data => {
          if (data.success) {
              pendingChanges = { updates: [], deletes: [] };
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

// showSuggestions 함수 수정
function showSuggestions(category, container) {
  fetch(`/label/phrases/suggestions/?category=${category}`)
        .then(response => response.json())
    .then(data => {
      if (data.success) {
                const suggestBtn = container.closest('.suggest-container').querySelector('.suggest-btn');
                const btnRect = suggestBtn.getBoundingClientRect();
                
                // 추천 목록의 위치를 버튼에 맞춰 조정
                container.style.display = 'block';
                container.style.position = 'absolute';
                container.style.top = '0';  // 버튼과 같은 높이
                container.style.left = '100%';  // 버튼 바로 옆
                container.style.marginLeft = '5px';  // 약간의 여백
                container.style.zIndex = '1000';
                
                container.innerHTML = `
                    <div class="suggestions-list" style="
                        background: white; 
                        border: 1px solid #dee2e6; 
                        border-radius: 4px; 
                        padding: 0.5rem; 
                        max-height: 300px; 
                        overflow-y: auto; 
                        min-width: 300px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.15);
                    ">
                        ${data.suggestions.map(s => `
                            <div class="suggestion-item p-2 hover-highlight" style="cursor: pointer;" 
                                 onclick="applySuggestion('${s.name}', '${s.content}', '${s.note || ''}', this)">
                                <div class="fw-bold">${s.name}</div>
                                <div class="small text-muted">${s.content}</div>
                            </div>
                        `).join('')}
                    </div>
                `;

                // 추천 목록이 화면을 벗어나지 않도록 조정
                const listRect = container.getBoundingClientRect();
                const viewportWidth = window.innerWidth;
                if (listRect.right > viewportWidth) {
                    container.style.left = 'auto';
                    container.style.right = '100%';
                    container.style.marginLeft = '0';
                    container.style.marginRight = '5px';
                }
            }
        });
}

// applySuggestion 함수 수정 (중복 함수 제거 및 통합)
function applySuggestion(name, content, note, element) {
  console.log('applySuggestion called:', { name, content, note });
  const row = document.querySelector('.new-input-row');
  if (row) {
      row.querySelector('[name="new-name"]').value = name;
      row.querySelector('[name="new-content"]').value = content;
      row.querySelector('[name="new-note"]').value = note;
      
      // 추천 목록 닫기
      const suggestionsContainer = row.querySelector('.suggestions-dropdown');
      if (suggestionsContainer) {
          suggestionsContainer.style.display = 'none';
      }
      
      // 입력 필드로 포커스 이동
      row.querySelector('[name="new-name"]').focus();
  }
}

// 추천 문구 적용
function applySuggestion(name, content, note) {
  console.log('applySuggestion called:', { name, content, note });
  const row = document.querySelector('.new-input-row');
  if (row) {
    row.querySelector('[name="new-name"]').value = name;
    row.querySelector('[name="new-content"]').value = content;
    row.querySelector('[name="new-note"]').value = note;
      row.querySelector('[name="new-name"]').focus();
    document.querySelector('.suggestion-modal').remove();
  } else {
      console.error('New input row not found');
  }
}

// 편집 취소
function cancelEditing() {
    isEditingMode = false;
    isAddingNew = false;
    const editingRows = document.querySelectorAll('.editing, .new-input-row');
    editingRows.forEach(row => row.remove());
}