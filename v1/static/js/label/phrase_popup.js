// 전역 변수 선언
let phrasesData = JSON.parse(document.getElementById('phrases-data').textContent);
let isEditingMode = false;
let isAddingNew = false;
let pendingChanges = { updates: [], deletes: [] };
let currentActiveTab = '';
let lastActiveTabId = localStorage.getItem('lastActiveTab') || null;

// 카테고리 매핑
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

// 초기화 함수
function initializePhrasePopup() {
    // 버튼 초기화
    function initButtons() {
        const addBtn = document.querySelector('.btn-add-new');
        const editBtn = document.querySelector('.btn-edit');

        if (addBtn) {
            addBtn.removeAttribute('onclick');
            addBtn.addEventListener('click', () => {
                if (isAddingNew) {
                    saveNewPhrase();
                } else {
                    if (isEditingMode) {
                        alert('편집 모드에서는 새 문구를 추가할 수 없습니다.');
                        return;
                    }
                    isAddingNew = true;
                    addBtn.textContent = '저장';
                    addBtn.classList.replace('btn-outline-primary', 'btn-primary');
                    createNewPhraseRow();
                }
            });
        }

        if (editBtn) {
            editBtn.removeAttribute('onclick');
            editBtn.addEventListener('click', () => {
                if (isAddingNew) {
                    cancelNewPhrase();
                }
                isEditingMode = !isEditingMode;
                editBtn.textContent = isEditingMode ? '저장' : '수정';
                editBtn.classList.toggle('btn-primary', isEditingMode);
                editBtn.classList.toggle('btn-outline-secondary', !isEditingMode);

                if (isEditingMode) {
                    pendingChanges = { updates: [], deletes: [] };
                } else {
                    saveChanges();
                }
                renderCurrentTab();
            });
        }
    }

    // 탭 초기화
    function initTabs() {
        document.querySelectorAll('.nav-tabs .nav-link').forEach(tab => {
            tab.removeEventListener('shown.bs.tab', handleTabChange);
            tab.addEventListener('shown.bs.tab', handleTabChange);
        });
    }

    function handleTabChange(e) {
        const targetId = e.target.getAttribute('data-bs-target');
        currentActiveTab = targetId.replace('#', '').replace('-tab', '');
        localStorage.setItem('lastActiveTab', targetId);
        lastActiveTabId = targetId;

        if (isEditingMode || isAddingNew) {
            if (confirm('편집 중인 내용이 있습니다. 변경사항을 취소하시겠습니까?')) {
                cancelEditing();
            } else {
                const previousTab = e.relatedTarget;
                if (previousTab) {
                    new bootstrap.Tab(previousTab).show();
                    return;
                }
            }
        }
        renderCurrentTab();
    }

    initButtons();
    initTabs();
    renderCurrentTab();
}

// 현재 탭 렌더링
function renderCurrentTab() {
    if (!currentActiveTab) {
        const activeTab = document.querySelector('.tab-pane.active');
        currentActiveTab = activeTab ? activeTab.id.replace('-tab', '') : Object.keys(phrasesData)[0];
        lastActiveTabId = `#${currentActiveTab}-tab`;
        localStorage.setItem('lastActiveTab', lastActiveTabId);
    }

    renderPhrases(currentActiveTab, phrasesData[currentActiveTab]);

    // 탭 활성화
    const tabTrigger = document.querySelector(`.nav-link[data-bs-target='#${currentActiveTab}-tab']`);
    if (tabTrigger && !tabTrigger.classList.contains('active')) {
        new bootstrap.Tab(tabTrigger).show();
    }
}

// 문구 렌더링
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
                ${isEditingMode ? `<button class="btn btn-sm btn-danger delete-btn">×</button>` : ''}
            </div>
        `;
        list.appendChild(item);
    });

    container.appendChild(list);

    list.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.closest('.phrase-item').dataset.id;
            queueDeletePhrase(id, btn);
        }, { once: true });
    });

    list.querySelectorAll('.phrase-name, .phrase-content, .phrase-note').forEach(input => {
        input.addEventListener('input', () => {
            if (!isEditingMode) return;
            queueEditPhrase(input.closest('.phrase-item'));
        }, { once: true });
    });

    list.querySelectorAll('.toggle-fav').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = btn.closest('.phrase-item');
            const id = item.dataset.id;
            const cat = item.dataset.category;
            const phrase = phrasesData[cat].find(p => p.id == id);
            phrase.note = phrase.note?.includes('★') ? phrase.note.replace('★', '').trim() : `★ ${phrase.note || ''}`.trim();
            saveFavorite(phrase);
        }, { once: true });
    });
}

// 신규 문구 입력 행 생성
function createNewPhraseRow() {
    const category = currentActiveTab || document.querySelector('.tab-pane.active').id.replace('-tab', '');
    const phraseList = document.getElementById(`${category}PhraseList`);
    if (!phraseList) return;

    document.querySelector('.new-input-row')?.remove();

    const newRow = document.createElement('div');
    newRow.className = 'phrase-item new-input-row';
    newRow.innerHTML = `
        <div class="input-container d-flex align-items-center gap-2">
            <div class="suggest-container position-relative">
                <button type="button" class="btn btn-sm btn-outline-primary suggest-btn" style="white-space: nowrap; padding: 4px 8px;">추천</button>
                <div class="suggestions-dropdown" style="display:none;"></div>
            </div>
            <input type="text" class="form-control phrase-name" name="new-name" placeholder="문구명" required>
            <input type="text" class="form-control phrase-content" name="new-content" placeholder="내용" required>
            <input type="text" class="form-control phrase-note" name="new-note" placeholder="비고">
            <button type="button" class="btn btn-sm btn-danger cancel-new">×</button>
        </div>
    `;

    newRow.querySelector('.cancel-new').addEventListener('click', cancelNewPhrase);
    newRow.querySelector('.suggest-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        const suggestionsContainer = newRow.querySelector('.suggestions-dropdown');
        suggestionsContainer.style.display = suggestionsContainer.style.display === 'none' ? 'block' : 'none';
        showSuggestions(category, suggestionsContainer);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.suggest-container')) {
            document.querySelectorAll('.suggestions-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });
        }
    }, { once: true });

    phraseList.insertBefore(newRow, phraseList.firstChild);
    newRow.querySelector('[name="new-name"]').focus();
}

// 신규 문구 저장
async function saveNewPhrase() {
    const inputRow = document.querySelector('.new-input-row');
    if (!inputRow) return;

    const nameInput = inputRow.querySelector('[name="new-name"]');
    const contentInput = inputRow.querySelector('[name="new-content"]');
    const noteInput = inputRow.querySelector('[name="new-note"]');

    const name = nameInput.value.trim();
    const content = contentInput.value.trim();
    const note = noteInput.value.trim();

    // 카테고리 유효성 검사 추가
    if (!currentActiveTab || currentActiveTab.trim() === '') {
        alert('카테고리(탭)가 올바르지 않습니다. 다시 시도해 주세요.');
        return;
    }
    if (!name || !content) {
        alert('문구명과 내용은 필수 입력항목입니다.');
        return;
    }

    const existingPhrase = phrasesData[currentActiveTab]?.find(
        p => p.name.toLowerCase() === name.toLowerCase() && p.content.toLowerCase() === content.toLowerCase()
    );
    if (existingPhrase) {
        alert('이미 동일한 문구명과 내용이 존재합니다.');
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
                my_phrase_name: name,
                category_name: currentActiveTab,
                comment_content: content,
                note: note
            })
        });

        const result = await response.json();
        if (result.success) {
            const addButton = document.querySelector('.btn-add-new');
            if (addButton) {
                addButton.textContent = '신규';
                addButton.classList.replace('btn-primary', 'btn-outline-primary');
            }
            isAddingNew = false;
            inputRow.remove();
            localStorage.setItem('lastActiveTab', `#${currentActiveTab}-tab`);
            await reloadPopupData();
        } else {
            alert('저장 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Save error:', error);
        alert('저장 중 오류가 발생했습니다: ' + error.message);
    }
}

// 신규 문구 취소
function cancelNewPhrase() {
    const addButton = document.querySelector('.btn-add-new');
    if (addButton) {
        addButton.textContent = '신규';
        addButton.classList.replace('btn-primary', 'btn-outline-primary');
    }

    const inputRow = document.querySelector('.new-input-row');
    if (inputRow) inputRow.remove();

    isAddingNew = false;
}

// 편집 취소
async function cancelEditing() {
    const addButton = document.querySelector('.btn-add-new');
    if (addButton) {
        addButton.textContent = '신규';
        addButton.classList.replace('btn-primary', 'btn-outline-primary');
    }

    const editButton = document.querySelector('.btn-edit');
    if (editButton) {
        editButton.textContent = '수정';
        editButton.classList.replace('btn-primary', 'btn-outline-secondary');
    }

    document.querySelectorAll('.new-input-row').forEach(row => row.remove());
    localStorage.setItem('lastActiveTab', `#${currentActiveTab}-tab`);
    await reloadPopupData();
}

// 수정 사항 저장
async function saveChanges() {
    const editButton = document.querySelector('.btn-edit');
    if (editButton) {
        editButton.textContent = '수정';
        editButton.classList.replace('btn-primary', 'btn-outline-secondary');
    }

    if (pendingChanges.updates.length === 0 && pendingChanges.deletes.length === 0) {
        await reloadPopupData();
        return;
    }

    for (const change of [...pendingChanges.updates, ...pendingChanges.deletes]) {
        try {
            const response = await fetch('/label/phrases/manage/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify(change)
            });

            const result = await response.json();
            if (!result.success) {
                alert(`변경 사항 저장 실패: ${result.error || '알 수 없는 오류'}`);
                return;
            }
        } catch (error) {
            console.error('Save changes error:', error);
            alert('변경 사항 저장 중 오류: ' + error.message);
            return;
        }
    }

    localStorage.setItem('lastActiveTab', `#${currentActiveTab}-tab`);
    await reloadPopupData();
}

// 수정 대기열 추가
function queueEditPhrase(item) {
    const phraseId = item.dataset.id;
    const category = item.dataset.category;
    if (!category || category.trim() === '') return; // 방어 코드 추가
    const original = phrasesData[category].find(p => p.id == phraseId);
    const updatedPhrase = {
        action: 'update',
        id: phraseId,
        my_phrase_name: item.querySelector('[name="edit-name"]').value,
        comment_content: item.querySelector('[name="edit-content"]').value,
        note: item.querySelector('[name="edit-note"]').value,
        category_name: category,
        order: Number(item.dataset.index) || original?.order || 0
    };

    const existingIndex = pendingChanges.updates.findIndex(p => p.id === phraseId);
    if (existingIndex >= 0) {
        pendingChanges.updates[existingIndex] = updatedPhrase;
    } else {
        pendingChanges.updates.push(updatedPhrase);
    }
}

// 삭제 대기열 추가
function queueDeletePhrase(phraseId, button) {
    // category_name을 반드시 포함
    const item = button.closest('.phrase-item');
    const category = item?.dataset.category || currentActiveTab;
    pendingChanges.deletes.push({
        action: 'delete',
        id: phraseId,
        category_name: category
    });
    button.closest('.phrase-item').remove();
}

// 즐겨찾기 저장
function saveFavorite(phrase) {
    if (isEditingMode) {
        const dummyItem = document.createElement('div');
        dummyItem.dataset.id = phrase.id;
        dummyItem.dataset.category = phrase.category;
        dummyItem.dataset.index = phrasesData[phrase.category].findIndex(p => p.id == phrase.id);
        dummyItem.innerHTML = `
            <input name="edit-name" value="${phrase.name}">
            <input name="edit-content" value="${phrase.content}">
            <input name="edit-note" value="${phrase.note}">
        `;
        queueEditPhrase(dummyItem);
        renderCurrentTab();
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
                my_phrase_name: phrase.name,
                comment_content: phrase.content,
                note: phrase.note,
                category_name: phrase.category
            })
        }).then(res => res.json()).then(data => {
            if (data.success) reloadPopupData();
        });
    }
}

// 팝업 데이터 새로고침
async function reloadPopupData() {
    try {
        const response = await fetch('/label/phrases/', { cache: 'no-store' });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newContent = doc.querySelector('.container-fluid.phrase-popup');
        if (!newContent) throw new Error('Phrase popup container not found');

        document.querySelector('.container-fluid.phrase-popup').outerHTML = newContent.outerHTML;
        phrasesData = JSON.parse(doc.getElementById('phrases-data').textContent);

        isEditingMode = false;
        isAddingNew = false;
        pendingChanges = { updates: [], deletes: [] };

        initializePhrasePopup();
    } catch (error) {
        console.error('Reload error:', error);
        alert('팝업 새로고침 오류: ' + error.message);
    }
}

// 추천 문구 표시
function showSuggestions(category, container) {
    fetch(`/label/phrases/suggestions/?category=${category}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const suggestBtn = container.closest('.suggest-container').querySelector('.suggest-btn');
                const btnRect = suggestBtn.getBoundingClientRect();

                container.style.display = 'block';
                container.style.position = 'absolute';
                container.style.top = `${btnRect.height}px`;
                container.style.left = '0';
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

                const listRect = container.getBoundingClientRect();
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;

                if (listRect.right > viewportWidth) {
                    container.style.left = 'auto';
                    container.style.right = '0';
                }
                if (listRect.bottom > viewportHeight) {
                    container.style.top = 'auto';
                    container.style.bottom = `${btnRect.height}px`;
                }
            } else {
                alert('추천 문구 로딩 실패: ' + (data.error || '알 수 없는 오류'));
            }
        })
        .catch(error => {
            console.error('Suggestions error:', error);
            alert('추천 문구 로딩 중 오류: ' + error.message);
        });
}

// 추천 문구 적용
function applySuggestion(name, content, note, element) {
    const row = document.querySelector('.new-input-row');
    if (row) {
        row.querySelector('[name="new-name"]').value = name;
        row.querySelector('[name="new-content"]').value = content;
        row.querySelector('[name="new-note"]').value = note;
        row.querySelector('.suggestions-dropdown').style.display = 'none';
        row.querySelector('[name="new-name"]').focus();
    }
}

// DOMContentLoaded 이벤트
document.addEventListener('DOMContentLoaded', () => {
    document.removeEventListener('DOMContentLoaded', initializePhrasePopup);
    initializePhrasePopup();
});