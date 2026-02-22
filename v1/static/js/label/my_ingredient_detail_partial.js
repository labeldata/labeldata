(function() {
'use strict';

// --- 알레르기/GMO 버튼 선택 로직 ---
let selectedAllergens = [];
let selectedGmos = [];

function updateAllergyDisplay() {
    const display = document.getElementById('allergySelectedDisplay');
    const input = document.getElementById('allergy_info');
    if (!display || !input) return;
    
    if (selectedAllergens.length === 0) {
        display.textContent = '선택된 항목 없음';
        display.style.color = '#6b7280';
        input.value = '';
    } else {
        display.textContent = selectedAllergens.join(', ');
        display.style.color = '#1f2937';
        display.style.fontWeight = '600';
        input.value = selectedAllergens.join(', ');
    }
}

function updateGmoDisplay() {
    const display = document.getElementById('gmoSelectedDisplay');
    const input = document.getElementById('gmo_info');
    if (!display || !input) return;
    
    if (selectedGmos.length === 0) {
        display.textContent = '선택된 항목 없음';
        display.style.color = '#6b7280';
        input.value = '';
    } else {
        display.textContent = selectedGmos.join(', ');
        display.style.color = '#1f2937';
        display.style.fontWeight = '600';
        input.value = selectedGmos.join(', ');
    }
}

function initAllergyGmoButtonEvents() {
    // 초기값 세팅
    const allergyInput = document.getElementById('allergy_info');
    const gmoInput = document.getElementById('gmo_info');
    if (!allergyInput || !gmoInput) return;
    
    selectedAllergens = allergyInput.value ? allergyInput.value.split(',').map(s => s.trim()).filter(Boolean) : [];
    selectedGmos = gmoInput.value ? gmoInput.value.split(',').map(s => s.trim()).filter(Boolean) : [];

    // 버튼 상태 초기화
    document.querySelectorAll('.allergy-btn').forEach(btn => {
        const allergen = btn.dataset.allergen;
        if (selectedAllergens.includes(allergen)) {
            btn.classList.remove('btn-outline-primary');
            btn.classList.add('btn-primary');
        } else {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        }
    });
    document.querySelectorAll('.gmo-btn').forEach(btn => {
        const gmo = btn.dataset.gmo;
        if (selectedGmos.includes(gmo)) {
            btn.classList.remove('btn-outline-primary');
            btn.classList.add('btn-primary');
        } else {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        }
    });
    updateAllergyDisplay();
    updateGmoDisplay();
    
    // === 전체선택/해제 버튼 이벤트 바인딩 ===
    const allergyToggleBtn = document.getElementById('allergyToggleBtn');
    const allergyBtnList = document.getElementById('allergyBtnList');
    
    if (allergyToggleBtn && allergyBtnList) {
        allergyToggleBtn.onclick = function() {
            const allAllergens = Array.from(allergyBtnList.querySelectorAll('.allergy-btn')).map(btn => btn.dataset.allergen);
            const allSelected = allAllergens.every(allergen => selectedAllergens.includes(allergen));
            
            if (allSelected) {
                // 전체해제
                selectedAllergens = [];
                allergyBtnList.querySelectorAll('.allergy-btn').forEach(btn => {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                });
                this.textContent = '전체선택';
            } else {
                // 전체선택
                selectedAllergens = [...allAllergens];
                allergyBtnList.querySelectorAll('.allergy-btn').forEach(btn => {
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-primary');
                });
                this.textContent = '전체해제';
            }
            updateAllergyDisplay();
        };
    }
    
    // GMO 전체선택/해제 토글
    const gmoToggleBtn = document.getElementById('gmoToggleBtn');
    const gmoBtnList = document.getElementById('gmoBtnList');
    
    if (gmoToggleBtn && gmoBtnList) {
        gmoToggleBtn.onclick = function() {
            const allGmos = Array.from(gmoBtnList.querySelectorAll('.gmo-btn')).map(btn => btn.dataset.gmo);
            const allSelected = allGmos.every(gmo => selectedGmos.includes(gmo));
            
            if (allSelected) {
                // 전체해제
                selectedGmos = [];
                gmoBtnList.querySelectorAll('.gmo-btn').forEach(btn => {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                });
                this.textContent = '전체선택';
            } else {
                // 전체선택
                selectedGmos = [...allGmos];
                gmoBtnList.querySelectorAll('.gmo-btn').forEach(btn => {
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-primary');
                });
                this.textContent = '전체해제';
            }
            updateGmoDisplay();
        };
    }
    
    // === 개별 버튼 클릭 이벤트 위임 ===
    // 알레르기 버튼 개별 클릭
    if (allergyBtnList) {
        allergyBtnList.querySelectorAll('.allergy-btn').forEach(btn => {
            btn.onclick = function() {
                const allergen = this.dataset.allergen;
                const idx = selectedAllergens.indexOf(allergen);
                if (idx > -1) {
                    selectedAllergens.splice(idx, 1);
                    this.classList.remove('btn-primary');
                    this.classList.add('btn-outline-primary');
                } else {
                    selectedAllergens.push(allergen);
                    this.classList.remove('btn-outline-primary');
                    this.classList.add('btn-primary');
                }
                updateAllergyDisplay();
                // 토글 버튼 텍스트 업데이트
                const allergyToggleBtn = document.getElementById('allergyToggleBtn');
                if (allergyToggleBtn) {
                    const allAllergens = Array.from(allergyBtnList.querySelectorAll('.allergy-btn')).map(b => b.dataset.allergen);
                    const allSelected = allAllergens.every(a => selectedAllergens.includes(a));
                    allergyToggleBtn.textContent = allSelected ? '전체해제' : '전체선택';
                }
            };
        });
    }
    
    // GMO 버튼 개별 클릭
    if (gmoBtnList) {
        gmoBtnList.querySelectorAll('.gmo-btn').forEach(btn => {
            btn.onclick = function() {
                const gmo = this.dataset.gmo;
                const idx = selectedGmos.indexOf(gmo);
                if (idx > -1) {
                    selectedGmos.splice(idx, 1);
                    this.classList.remove('btn-primary');
                    this.classList.add('btn-outline-primary');
                } else {
                    selectedGmos.push(gmo);
                    this.classList.remove('btn-outline-primary');
                    this.classList.add('btn-primary');
                }
                updateGmoDisplay();
                // 토글 버튼 텍스트 업데이트
                const gmoToggleBtn = document.getElementById('gmoToggleBtn');
                if (gmoToggleBtn) {
                    const allGmos = Array.from(gmoBtnList.querySelectorAll('.gmo-btn')).map(b => b.dataset.gmo);
                    const allSelected = allGmos.every(g => selectedGmos.includes(g));
                    gmoToggleBtn.textContent = allSelected ? '전체해제' : '전체선택';
                }
            };
        });
    }
}

// --- 알레르기 자동감지 기능 (label_creation.js와 동일한 로직 사용) ---
function autoDetectAllergensIngredient() {
    // 원재료명과 원재료 표시명 텍스트 가져오기
    const prdlstNmInput = document.getElementById('prdlst_nm');
    const displayNameInput = document.getElementById('ingredient_display_name');
    
    if (!prdlstNmInput && !displayNameInput) {
        alert('원재료명을 먼저 입력해주세요.');
        return;
    }
    
    // 두 필드의 텍스트를 합쳐서 검색
    const prdlstNmText = prdlstNmInput ? prdlstNmInput.value : '';
    const displayNameText = displayNameInput ? displayNameInput.value : '';
    const combinedText = `${prdlstNmText} ${displayNameText}`.trim();
    
    if (!combinedText) {
        alert('원재료명 또는 원재료 표시명을 먼저 입력해주세요.');
        return;
    }
    
    // constants.js의 ALLERGEN_KEYWORDS 사용
    const allergenKeywords = window.allergenKeywords || window.ALLERGEN_KEYWORDS || {
        '알류': ['달걀', '계란', '오리알', '메추리알', '전란', '전란액', '전란유', '전란분', '난백', '난백액', '난백분', '난황', '난황액', '난황분', '난황유', '거위알', '알부민', '레시틴(난황)', '라이소자임', '난류', 'egg', 'lysozyme'],
        '우유': ['우유', '원유', '산양유', '유청', '유청단백', '카제인', '카제인나트륨', '유당', '치즈', '버터', '크림', '생크림', '사워크림', '유크림', '연유', '분유', '전지분유', '탈지분유', '요구르트', 'milk', 'dairy', 'whey protein', 'sodium caseinate'],
        '메밀': ['메밀', '메밀가루', '메밀묵', 'buckwheat'],
        '밀': ['밀', '밀가루', '통밀', '글루텐', '세몰리나', '듀럼밀', '소맥', '부침가루', '튀김가루', '밀기울', '스펠트밀', 'wheat', 'gluten', 'wheat bran', 'spelt'],
        '대두': ['대두', '대두콩', '노란콩', '콩나물', '두부', '두유', '된장', '간장', '고추장', '콩가루', '콩기름', '대두유', '대두단백', '레시틴', '대두레시틴', 'soy', 'soybean', 'soy lecithin'],
        '땅콩': ['땅콩', '땅콩버터', '땅콩기름', '낙화생', 'peanut', 'peanuts'],
        '호두': ['호두', '호두유', 'walnut', 'walnuts'],
        '잣': ['잣', 'pine nuts', 'pine nut'],
        '쇠고기': ['쇠고기', '소고기', '우육', '소 내장', '곱창', '대창', '사골', '우족', '쇠고기추출물', '소고기육수', '사골육수', '소육수', '우지', '젤라틴', 'beef', 'tallow'],
        '돼지고기': ['돼지고기', '돈육', '돼지 내장', '돈골', '돈족', '베이컨', '햄', '소시지', '돈지', '젤라틴', 'pork', 'lard'],
        '닭고기': ['닭고기', '계육', '닭 내장', '닭발', '닭 육수', 'chicken'],
        '고등어': ['고등어', 'mackerel'],
        '게': ['게', '꽃게', 'crab'],
        '새우': ['새우', 'shrimp', 'prawns'],
        '오징어': ['오징어', 'squid'],
        '조개류': ['굴', '전복', '홍합', '꼬막', '바지락', '가리비', '소라', '재첩', '백합', '키조개', 'shellfish', 'clam', 'oyster'],
        '복숭아': ['복숭아', 'peach', 'peaches'],
        '토마토': ['토마토', '토마토 페이스트', '토마토 케첩', '토마토 퓌레', 'tomato', 'tomatoes'],
        '아황산류': ['아황산나트륨', '메타중아황산칼륨', '무수아황산', '산성아황산나트륨', '이산화황', 'sulfite', 'sulfur dioxide']
    };
    
    // 감지된 알레르기
    const detectedAllergens = new Set();
    
    // 각 알레르기 그룹의 키워드로 검색 (label_creation.js와 동일한 로직)
    for (const [allergen, keywords] of Object.entries(allergenKeywords)) {
        let allergenFound = false;
        for (const keyword of keywords) {
            let found = false;
            
            // 1글자 키워드는 단어 경계 체크 (오탐 방지)
            if (keyword.length === 1) {
                const regex = new RegExp(`[\\s,():]${keyword}[\\s,():]|^${keyword}[\\s,():]|[\\s,():]${keyword}$|^${keyword}$`, 'gi');
                if (regex.test(combinedText)) {
                    found = true;
                }
            } else {
                // 2글자 이상: 단순 포함 여부로 체크
                const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(escapedKeyword, 'gi');
                if (regex.test(combinedText)) {
                    found = true;
                }
            }
            
            if (found) {
                detectedAllergens.add(allergen);
                allergenFound = true;
                break;
            }
        }
    }
    
    // 감지된 알레르기 성분을 선택된 목록에 추가
    selectedAllergens = Array.from(detectedAllergens);
    
    // UI 업데이트
    const allergyBtnList = document.getElementById('allergyBtnList');
    if (allergyBtnList) {
        allergyBtnList.querySelectorAll('.allergy-btn').forEach(btn => {
            const allergen = btn.dataset.allergen;
            if (selectedAllergens.includes(allergen)) {
                btn.classList.remove('btn-outline-primary');
                btn.classList.add('btn-primary');
            } else {
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-outline-primary');
            }
        });
    }
    
    // 전체선택 버튼 텍스트 업데이트
    const allergyToggleBtn = document.getElementById('allergyToggleBtn');
    if (allergyToggleBtn && allergyBtnList) {
        const allAllergens = Array.from(allergyBtnList.querySelectorAll('.allergy-btn')).map(b => b.dataset.allergen);
        const allSelected = allAllergens.every(a => selectedAllergens.includes(a));
        allergyToggleBtn.textContent = allSelected ? '전체해제' : '전체선택';
    }
    
    updateAllergyDisplay();
    
    // 사용 로그 기록
    logAllergyAutoDetect();
}

// 알레르기 자동감지 사용 로그 기록
function logAllergyAutoDetect() {
    fetch('/label/log-allergy-auto-detect/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify({})
    }).catch(err => console.error('로그 기록 실패:', err));
}

// --- 품목보고번호 불러오기 기능 ---
function fetchFoodItemByReportNo() {
    const reportNoInput = document.getElementById('prdlst_report_no');
    const reportNo = reportNoInput ? reportNoInput.value.trim() : '';
    
    if (!reportNo) {
        alert('품목보고번호를 입력해주세요.');
        return;
    }
    
    fetch(`/label/fetch-food-item/${reportNo}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 원재료명 자동 입력
                if (data.prdlst_nm) {
                    const prdlstNmInput = document.getElementById('prdlst_nm');
                    if (prdlstNmInput) {
                        prdlstNmInput.value = data.prdlst_nm;
                    }
                }
                
                // 식품유형 자동 입력
                if (data.prdlst_dcnm) {
                    const foodType = data.prdlst_dcnm;
                    let detectedCategory = 'processed'; // 기본값
                    
                    // 식품유형 데이터 가져오기
                    const foodTypesData = document.getElementById('food-types-data');
                    const agriProductsData = document.getElementById('agricultural-products-data');
                    const foodAdditivesData = document.getElementById('food-additives-data');
                    
                    if (foodTypesData && agriProductsData && foodAdditivesData) {
                        const foodTypes = JSON.parse(foodTypesData.textContent || '[]');
                        const agriProducts = JSON.parse(agriProductsData.textContent || '[]');
                        const foodAdditives = JSON.parse(foodAdditivesData.textContent || '[]');
                        
                        // 식품유형으로 식품구분 추측
                        if (foodTypes.some(opt => opt.food_type === foodType)) {
                            detectedCategory = 'processed';
                        } else if (agriProducts.some(opt => opt.name_kr === foodType)) {
                            detectedCategory = 'agricultural';
                        } else if (foodAdditives.some(opt => opt.name_kr === foodType)) {
                            detectedCategory = 'additive';
                        }
                    }
                    
                    // 라디오 버튼 선택
                    const targetRadio = document.querySelector(`input[name="food_category"][value="${detectedCategory}"]`);
                    if (targetRadio) {
                        targetRadio.checked = true;
                        // 품목보고번호 행 표시/숨김 처리
                        if (typeof toggleReportNoRow === 'function') {
                            toggleReportNoRow();
                        }
                    }
                    
                    // 식품유형 옵션 업데이트 및 선택
                    if (typeof initFoodTypeSelect === 'function') {
                        initFoodTypeSelect();
                    }
                    
                    // select2로 식품유형 선택
                    const foodTypeSelect = document.getElementById('foodTypeSelect');
                    if (foodTypeSelect && typeof $ !== 'undefined' && $.fn.select2) {
                        setTimeout(() => {
                            $(foodTypeSelect).val(foodType).trigger('change.select2');
                        }, 100);
                    }
                }
                
                // 제조사 자동 입력
                if (data.bssh_nm) {
                    const bsshNmInput = document.getElementById('bssh_nm');
                    if (bsshNmInput) {
                        bsshNmInput.value = data.bssh_nm;
                    }
                }
                
                alert('정보를 불러왔습니다. 내용을 확인하고 필요하면 수정해주세요.');
            } else {
                alert('해당 품목보고번호를 찾을 수 없습니다.');
            }
        })
        .catch(error => {
            console.error('Fetch error:', error);
            alert('불러오기 중 오류가 발생했습니다.');
        });
}

// 삭제 확인 및 삭제 함수
function confirmDelete() {
    if (confirm('정말 삭제하시겠습니까?')) {
        deleteMyIngredient();
    }
}

function deleteMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    if (!my_ingredient_id) {
        alert('원료 ID가 없습니다.');
        return;
    }
    fetch(`/label/delete-my-ingredient/${my_ingredient_id}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('내 원료가 성공적으로 삭제되었습니다.');
            // 부모창 새로고침
            if (window.opener) {
                window.opener.location.reload();
            } else if (window.parent && window.parent !== window) {
                window.parent.location.reload();
            }
            // 현재창 새로고침
            window.location.reload();
        } else {
            alert(data.error || '삭제에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('삭제 중 오류가 발생했습니다.');
    });
}

// 삭제 버튼 클릭 이벤트 핸들러 (partial에서 사용)
function handleDeleteIngredientPartial(ingredientId) {
    if (!ingredientId) {
        alert('삭제할 원료 ID가 없습니다.');
        return;
    }
    if (!confirm('정말로 이 원료를 삭제하시겠습니까?')) {
        return;
    }
    fetch(`/label/delete-my-ingredient/${ingredientId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // 부모창 새로고침
            if (window.opener) {
                window.opener.location.reload();
            } else if (window.parent && window.parent !== window) {
                window.parent.location.reload();
            }
            // 현재 partial 창 새로고침
            window.location.reload();
        } else {
            alert(data.error || '삭제에 실패했습니다.');
        }
    })
    .catch(err => {
        alert('삭제 중 오류가 발생했습니다.');
        console.error(err);
    });
}

// 폼 저장 함수 (검색 조건 유지, 테이블 컬럼 순서 맞춤)
function saveMyIngredient() {
    const my_ingredient_id_elem = document.getElementById("my_ingredient_id");
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    const formElem = document.getElementById("ingredientForm");
    const formData = new FormData(formElem);
    let url;
    if (my_ingredient_id) {
        url = `/label/my-ingredient-detail/${my_ingredient_id}/`;
    } else {
        url = '/label/my-ingredient-detail/';
    }

    // 검색 조건 쿼리스트링 추출 (ingredientTable이 있는 페이지에서만 동작)
    let queryString = '';
    const searchForm = document.querySelector('form[action*="my_ingredient_list_combined"]');
    if (searchForm) {
        const params = new URLSearchParams(new FormData(searchForm));
        queryString = '?' + params.toString();
    } else {
        // fallback: 현재 URL에서 쿼리스트링만 추출
        const qs = window.location.search;
        if (qs) queryString = qs;
    }

    // 저장 버튼 비활성화 및 로딩 표시
    const saveBtn = document.querySelector('button[type="submit"][form="ingredientForm"]');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.className = 'btn btn-secondary';
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>저장중...';
    }

    // 원재료명 필수값 체크
    const prdlst_nm = formData.get('prdlst_nm')?.trim();
    if (!prdlst_nm) {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.className = 'btn btn-danger';
            saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>원재료명 필수';
            
            setTimeout(() => {
                saveBtn.className = 'btn btn-primary';
                saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장';
            }, 3000);
        }
        document.getElementById('prdlst_nm').focus();
        return;
    }

    // 원재료명 중복 체크 (신규 등록 시에만)
    if (!my_ingredient_id && prdlst_nm) {
        fetch('/label/check-my-ingredient/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ prdlst_nm })
        })
        .then(res => res.json())
        .then(data => {
            if (data.exists) {
                if (!confirm('동일한 이름의 원료가 이미 존재합니다. 그래도 저장하시겠습니까?')) {
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.className = 'btn btn-primary';
                        saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장';
                    }
                    return;
                } else {
                    // 중복 무시 의도 전달
                    formData.append('ignore_duplicate', 'Y');
                }
            }
            doSaveMyIngredient(url, formData, queryString, saveBtn);
        })
        .catch(() => {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.className = 'btn btn-danger';
                saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>중복체크 오류';
                
                setTimeout(() => {
                    saveBtn.className = 'btn btn-primary';
                    saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장';
                }, 3000);
            }
        });
        return;
    }
    // 기존 원료 수정 또는 원재료명 미입력 시 바로 저장
    doSaveMyIngredient(url, formData, queryString, saveBtn);
}

// doSaveMyIngredient 함수 수정
function doSaveMyIngredient(url, formData, queryString, saveBtn) {
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (response.ok) {
            if (response.headers.get('content-type').includes('application/json')) {
                return response.json();
            } else {
                return { success: true };
            }
        }
        throw new Error('Network response was not ok.');
    })
    .then(data => {
        if (data.success) {
            // 저장 성공 버튼 피드백
            if (saveBtn) {
                saveBtn.className = 'btn btn-success';
                saveBtn.innerHTML = '<i class="fas fa-check me-1"></i>저장완료';
                
                setTimeout(() => {
                    saveBtn.disabled = false;
                    saveBtn.className = 'btn btn-primary';
                    saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장';
                }, 1500);
            }
            
            // 버튼 피드백 표시 후 리스트 갱신 (300ms 지연)
            setTimeout(() => {
                // 신규 등록된 원료의 페이지 계산 및 이동
                if (data.ingredient_id && !document.getElementById('my_ingredient_id').value) {
                    // 신규 등록의 경우 해당 원료가 있는 페이지 계산
                    calculateIngredientPage(data.ingredient_id, queryString, function(targetPage) {
                        const urlParams = new URLSearchParams(queryString.replace('?', ''));
                        urlParams.set('page', targetPage);
                        const finalQueryString = '?' + urlParams.toString();
                        
                        // 해당 페이지로 리스트 갱신
                        updateIngredientListAndSelect(finalQueryString, data.ingredient_id);
                    });
                } else {
                    // 수정의 경우 현재 페이지에서 리스트 갱신
                    updateIngredientListAndSelect(queryString, data.ingredient_id);
                }
                
                // 저장 성공 후 변경 감지 플래그 해제
                if (typeof window.setDetailDirty === 'function') window.setDetailDirty(false);
            }, 300);
        } else {
            // 저장 실패 버튼 피드백
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.className = 'btn btn-danger';
                saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>저장실패: ' + (data.error || '알 수 없는 오류');
                
                setTimeout(() => {
                    saveBtn.className = 'btn btn-primary';
                    saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장';
                }, 3000);
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        
        // 통신 오류 버튼 피드백
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.className = 'btn btn-danger';
            saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>통신오류';
            
            setTimeout(() => {
                saveBtn.className = 'btn btn-primary';
                saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>저장';
            }, 3000);
        }
    });
}

// 신규 등록된 원료의 페이지 위치 계산
function calculateIngredientPage(ingredientId, queryString, callback) {
    // 현재 검색 조건으로 전체 리스트를 가져와서 해당 원료의 위치 계산
    const searchParams = new URLSearchParams(queryString.replace('?', ''));
    searchParams.delete('page'); // 페이지 파라미터 제거
    const searchQueryString = searchParams.toString();
    
    fetch(`/label/my-ingredient-calculate-page/?ingredient_id=${ingredientId}&${searchQueryString}`, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            callback(data.page || 1);
        } else {
            callback(1); // 오류 시 첫 번째 페이지로
        }
    })
    .catch(error => {
        console.error('Error calculating page:', error);
        callback(1); // 오류 시 첫 번째 페이지로
    });
}

// 리스트 갱신 및 원료 선택
function updateIngredientListAndSelect(queryString, ingredientId) {
    fetch('/label/my-ingredient-table-partial/' + queryString)
        .then(res => res.text())
        .then(tableHtml => {
            const tbody = document.querySelector('#ingredientTable tbody');
            if (tbody) {
                tbody.innerHTML = tableHtml;
                
                // 리스트 갱신 후 클릭 이벤트 재바인딩
                if (typeof window.bindIngredientRowClickEvents === 'function') {
                    window.bindIngredientRowClickEvents();
                }
                
                // 신규 등록된 원료 선택
                if (ingredientId) {
                    const targetRow = document.querySelector(`.ingredient-row[data-ingredient-id='${ingredientId}']`);
                    if (targetRow) {
                        loadIngredientDetail(ingredientId, targetRow);
                    } else {
                        // 해당 행이 없으면 첫 번째 행 선택
                        const firstRow = document.querySelector('.ingredient-row');
                        if (firstRow) {
                            const firstIngredientId = firstRow.getAttribute('data-ingredient-id');
                            loadIngredientDetail(firstIngredientId, firstRow);
                        }
                    }
                }
                
                // 페이지네이션 정보 업데이트
                if (typeof window.updatePaginationInfo === 'function') {
                    const currentPageMatch = queryString.match(/page=(\d+)/);
                    const currentPage = currentPageMatch ? parseInt(currentPageMatch[1]) : 1;
                    // 페이지네이션 정보는 서버에서 전달받아야 함
                    updatePaginationFromServer(queryString);
                }
            }
        })
        .catch(error => {
            console.error('Error updating ingredient list:', error);
        });
}

// 서버에서 페이지네이션 정보 가져오기
function updatePaginationFromServer(queryString) {
    fetch(`/label/my-ingredient-pagination-info/${queryString}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && typeof window.updatePaginationInfo === 'function') {
            window.updatePaginationInfo(data.current_page, data.total_pages, data.item_count);
        }
    })
    .catch(error => {
        console.error('Error updating pagination info:', error);
    });
}

// 원료 상세 상단에 연결된 표시사항 조회 버튼 추가 함수
function addLinkedLabelsButton(my_ingredient_id) {
    if (!my_ingredient_id) return;
    fetch(`/label/linked-labels-count/${my_ingredient_id}/`)
        .then(res => res.json())
        .then(data => {
            // 기존 버튼 있으면 제거
            const oldBtn = document.getElementById('linkedLabelsViewBtn');
            if (oldBtn) oldBtn.remove();
            // 버튼 생성
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-outline-info btn-sm ms-2';
            btn.id = 'linkedLabelsViewBtn';
            btn.innerHTML = `연결된 표시사항(<span id="linkedLabelsCount">${data.count}</span>품목) 조회`;
            btn.onclick = function() {
                // v2 컨텍스트이면 제품 관리(product_explorer)로, 아니면 v1 표시사항 목록으로 이동
                const isV2 = !!document.querySelector('.v2-wrapper');
                const url = isV2
                    ? '/products/explorer/?ingredient_id=' + encodeURIComponent(my_ingredient_id)
                    : '/label/my-labels/?ingredient_id=' + encodeURIComponent(my_ingredient_id);
                window.location.href = url;
            };
            // '원료 수정' 텍스트 옆에 삽입 (예시: id가 ingredientTitle인 요소 옆)
            const titleElem = document.getElementById('ingredientEditTitle') || document.querySelector('.ingredient-edit-title');
            if (titleElem) {
                titleElem.insertAdjacentElement('afterend', btn);
            }
        });
}

// 연결된 표시사항(00품목) 조회 버튼 텍스트 및 이벤트 설정
function updateLinkedLabelsButton(my_ingredient_id) {
    const btn = document.getElementById('linkedLabelsBtn');
    if (!btn || !my_ingredient_id) return;
    fetch(`/label/linked-labels-count/${my_ingredient_id}/`)
        .then(res => res.json())
        .then(data => {
            btn.innerHTML = `<i class="bi bi-link-45deg"></i> 연결 표시사항(<span id="linkedLabelsCount">${data.count}</span>품목)`;
            btn.onclick = function() {
                if (data.count && data.count > 0) {
                    // v2 컨텍스트이면 제품 관리(product_explorer)로, 아니면 v1 표시사항 목록으로 이동
                    const isV2 = !!document.querySelector('.v2-wrapper');
                    const url = isV2
                        ? '/products/explorer/?ingredient_id=' + encodeURIComponent(my_ingredient_id)
                        : '/label/my-labels/?ingredient_id=' + encodeURIComponent(my_ingredient_id);
                    window.location.href = url;
                } else {
                    alert('연결된 표시사항이 없습니다.');
                }
            };
        });
}

// 네임스페이스를 사용하여 전역 변수 충돌 방지
window.IngredientDetailPartial = window.IngredientDetailPartial || {};
window.IngredientDetailPartial.isSyncing = false;

// IIFE 외부(onclick 속성 등)에서 호출 가능하도록 전역 노출
window.fetchFoodItemByReportNo = function() { fetchFoodItemByReportNo(); };

// AJAX 재로드 시 재초기화 진입점
window.IngredientDetailPartial.reinit = function() {
    initFoodTypeSelect();
    setupFoodCategoryChangeEvent();
    toggleReportNoRow();
    initAllergyGmoButtonEvents();
    var autoDetectBtn = document.getElementById('allergyAutoDetectBtn');
    if (autoDetectBtn) {
        autoDetectBtn.onclick = autoDetectAllergensIngredient;
    }
    initAutoExpandTextareas();
    var form = document.getElementById('ingredientForm');
    if (form) {
        form.onsubmit = function(e) { e.preventDefault(); saveMyIngredient(); };
    }
    var deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) { deleteBtn.onclick = confirmDelete; }
    var closeBtn = document.getElementById('closeBtn');
    if (closeBtn) {
        closeBtn.onclick = function() {
            if (confirm('입력 내용을 초기화하시겠습니까?')) {
                var f = document.getElementById('ingredientForm');
                if (f) f.reset();
                initFoodTypeSelect();
                initAllergyGmoButtonEvents();
                if (typeof window.setDetailDirty === 'function') window.setDetailDirty(false);
            }
        };
    }
    var idElem = document.getElementById('my_ingredient_id');
    var ingredientId = idElem ? parseInt(idElem.value, 10) : null;
    updateLinkedLabelsButton(ingredientId);
    updateDisplayRegulation();
};

// CSRF 토큰 가져오기 유틸
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// select2 식품유형 드롭다운 초기화
function initFoodTypeSelect() {
    const foodTypesRaw = document.getElementById('food-types-data')?.textContent;
    const agriProductsRaw = document.getElementById('agricultural-products-data')?.textContent;
    const foodAdditivesRaw = document.getElementById('food-additives-data')?.textContent;
    
    let foodTypes = [], agriProducts = [], foodAdditives = [];
    try {
        foodTypes = JSON.parse(foodTypesRaw || '[]');
        agriProducts = JSON.parse(agriProductsRaw || '[]');
        foodAdditives = JSON.parse(foodAdditivesRaw || '[]');    } catch (e) {
        return;
    }
    
    const select = document.getElementById('foodTypeSelect');
    if (!select) {
        return;
    }
    
    // 현재 식품 구분 값을 가져옴 - 라디오 버튼에서
    const ingredientForm = document.getElementById('ingredientForm');
    const selectedCategoryRadio = ingredientForm ? ingredientForm.querySelector('input[name="food_category"]:checked') : null;
    const currentFoodCategory = selectedCategoryRadio ? selectedCategoryRadio.value : 'processed';
    const actualFoodCategory = currentFoodCategory || 'processed';
    
    // 식품 구분에 따라 옵션 필터링
    let options = [];
    
    if (actualFoodCategory === 'processed') {
        options = foodTypes.map(ft => {
            if (ft.food_type) {
                return { id: ft.food_type, text: ft.food_type, category: 'processed' };
            }
            return null;
        }).filter(Boolean);
    } else if (actualFoodCategory === 'agricultural') {
        options = agriProducts.map(ap => {
            const name = ap.name_kr;
            if (name) {
                return { id: name, text: name, category: 'agricultural' };
            }
            return null;
        }).filter(Boolean);
    } else if (actualFoodCategory === 'additive') {
        options = foodAdditives.map(fa => {
            const name = fa.name_kr;
            if (name) {
                return { id: name, text: name, category: 'additive' };
            }
            return null;
        }).filter(Boolean);    }
    
    // 옵션을 select에 직접 추가
    select.innerHTML = '<option></option>';
    options.forEach(opt => {
        if (!opt.id || !opt.text) return;
        const option = document.createElement('option');
        option.value = opt.id;
        option.text = opt.text;
        option.setAttribute('data-category', opt.category);
        select.appendChild(option);
    });

    // select2 중복 바인딩 방지
    if ($(select).data('select2')) {
        $(select).off('change.foodtype');
        $(select).select2('destroy');
    }
    $(select).select2({
        width: '100%',
        placeholder: '식품유형 선택',
        allowClear: true,
        dropdownParent: $('body')
    });
    
    // 기존 값이 있으면 선택
    const currentValue = select.getAttribute('data-selected') || select.value;
    if (currentValue) {
        $(select).val(currentValue).trigger('change.select2');
    } else {
        $(select).val(null).trigger('change.select2');
    }
    
    // select2 change 이벤트: 식품유형 선택 시 식품 구분 자동 선택
    $(select).on('change.foodtype', function (e) {
        if (window.IngredientDetailPartial.isSyncing) return;
        const selectedOption = select.options[select.selectedIndex];
        if (!selectedOption) return;
        const selectedCategory = selectedOption.getAttribute('data-category');
        if (!selectedCategory) return;
        
        // 라디오 버튼 값 변경
        const currentCategoryRadio = document.querySelector('input[name="food_category"]:checked');
        if (currentCategoryRadio && currentCategoryRadio.value !== selectedCategory) {
            window.IngredientDetailPartial.isSyncing = true;
            const targetRadio = document.querySelector(`input[name="food_category"][value="${selectedCategory}"]`);
            if (targetRadio) {
                targetRadio.checked = true;
                toggleReportNoRow();
            }
            initFoodTypeSelect();
            $(select).val(selectedOption.value).trigger('change.select2');
            window.IngredientDetailPartial.isSyncing = false;
        }
        
        // 표시규정 업데이트
        updateDisplayRegulation();
    });
}

// 식품 구분 선택 변경시 식품유형 드롭다운 갱신
function setupFoodCategoryChangeEvent() {
    // 라디오 버튼 이벤트 바인딩
    const foodCategoryRadios = document.querySelectorAll('input[name="food_category"]');
    foodCategoryRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            handleFoodCategoryChange();
            toggleReportNoRow();
        });
    });
}

// 품목보고번호 행 표시/숨김 처리
function toggleReportNoRow() {
    const reportNoRow = document.getElementById('reportNoRow');
    if (!reportNoRow) return;
    
    const selectedCategory = document.querySelector('input[name="food_category"]:checked');
    if (!selectedCategory) return;
    
    const category = selectedCategory.value;
    // 가공식품 또는 식품첨가물인 경우에만 표시
    if (category === 'processed' || category === 'additive') {
        reportNoRow.style.display = '';
    } else {
        reportNoRow.style.display = 'none';
    }
}

// 식품 구분 변경 핸들러
function handleFoodCategoryChange() {
    if (window.IngredientDetailPartial.isSyncing) {
        return;
    }
    initFoodTypeSelect();
    updateDisplayRegulation(); // 표시규정 업데이트
}

// DOMContentLoaded 또는 즉시 실행 패턴으로 이벤트 바인딩
function onReady(fn) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fn);
    } else {
        fn();
    }
}

onReady(function() {
    // DOM 요소들이 존재하는지 확인
    const foodCategorySelect = document.getElementById('foodCategorySelect');
    const foodTypeSelect = document.getElementById('foodTypeSelect');
    const ingredientForm = document.getElementById('ingredientForm');
    
    // window.setDetailDirty를 항상 전역에 노출 (dirty 감지 정상화)
    if (typeof window.setDetailDirty !== 'function' && typeof setDetailDirty === 'function') {
        window.setDetailDirty = setDetailDirty;
    }
    
    initFoodTypeSelect();
    setupFoodCategoryChangeEvent();
    toggleReportNoRow(); // 초기 품목보고번호 행 표시/숨김
    initAllergyGmoButtonEvents(); // 알레르기/GMO 버튼 초기화
    
    // 알레르기 자동감지 버튼 이벤트 바인딩
    const allergyAutoDetectBtn = document.getElementById('allergyAutoDetectBtn');
    if (allergyAutoDetectBtn) {
        allergyAutoDetectBtn.addEventListener('click', autoDetectAllergensIngredient);
    }
    
    // textarea 자동 확장 초기화
    initAutoExpandTextareas();
    
    // 폼 submit 이벤트 바인딩 (partial에서도 반드시 필요)
    var form = document.getElementById('ingredientForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            saveMyIngredient();
        });
    }

    // 삭제 버튼 이벤트 바인딩 
    var deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', confirmDelete);
    }
    
    // 초기화 버튼 이벤트 바인딩
    var closeBtn = document.getElementById('closeBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            if(confirm('입력 내용을 초기화하시겠습니까?')) {
                form.reset();
                initFoodTypeSelect(); // 식품유형도 초기화
                initAllergyGmoButtonEvents(); // 알레르기/GMO 초기화
                // 초기화 후 변경 감지 플래그 해제
                if (typeof window.setDetailDirty === 'function') window.setDetailDirty(false);
            }
        });
    }

    // 연결된 표시사항 버튼 텍스트 및 이벤트 연결
    const my_ingredient_id_elem = document.getElementById('my_ingredient_id');
    const my_ingredient_id = my_ingredient_id_elem ? parseInt(my_ingredient_id_elem.value, 10) : null;
    updateLinkedLabelsButton(my_ingredient_id);
    
    // 초기 표시규정 설정
    updateDisplayRegulation();
});

// 표시규정 정보 업데이트 함수
function updateDisplayRegulation() {
    const ingredientForm = document.getElementById('ingredientForm');
    const selectedCategoryRadio = ingredientForm ? ingredientForm.querySelector('input[name="food_category"]:checked') : null;
    const foodTypeSelect = document.getElementById('foodTypeSelect');
    const displayRegulationInfo = document.getElementById('display-regulation-info');
    const displayRegulationDisplay = document.getElementById('display_regulation_display');
    const displayRegulationButtons = document.getElementById('display_regulation_buttons');
    const ingredientDisplayNameHelp = document.getElementById('ingredient_display_name_help');
    
    if (!selectedCategoryRadio || !foodTypeSelect || !displayRegulationInfo || !displayRegulationDisplay) {
        return;
    }
    
    const foodCategory = selectedCategoryRadio.value;
    const foodType = foodTypeSelect.value;
    const prdlstNm = document.getElementById('prdlst_nm') ? document.getElementById('prdlst_nm').value : '';
    
    // 식품첨가물이 아니거나 식품유형이 없으면 숨김
    if (foodCategory !== 'additive' || !foodType) {
        displayRegulationInfo.style.display = 'none';
        if (ingredientDisplayNameHelp) ingredientDisplayNameHelp.style.display = '';
        displayRegulationDisplay.textContent = '';
        if (displayRegulationButtons) displayRegulationButtons.style.display = 'none';
        return;
    }
    
    // API 호출하여 표시규정 정보 가져오기
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/label/get-additive-regulation/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            food_type: foodType,
            prdlst_nm: prdlstNm
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.has_regulation) {
            // 구조화된 데이터 직접 사용
            const header = data.header || '';
            const buttons = data.buttons || [];
            
            // 헤더 텍스트 표시
            if (header) {
                displayRegulationDisplay.textContent = header;
            } else {
                displayRegulationDisplay.textContent = '';
            }
            
            // 버튼 생성
            if (displayRegulationButtons && buttons.length > 0) {
                displayRegulationButtons.innerHTML = '';
                displayRegulationButtons.style.display = 'flex';
                
                buttons.forEach(item => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn btn-sm';
                    btn.style.cssText = 'font-size: 0.72rem; padding: 3px 10px; border-radius: 12px; font-weight: 600; background: #e0e8ff; border: 1px solid #c4d3f8; color: #2c4fa0; transition: all 0.15s;';
                    btn.textContent = item.value;
                    btn.title = `클릭하면 "원재료 표시명"에 자동 입력됩니다.`;
                    
                    btn.onclick = function() {
                        const displayNameInput = document.getElementById('ingredient_display_name');
                        if (displayNameInput) {
                            displayNameInput.value = item.value;
                            // textarea 자동 확장
                            if (displayNameInput.classList.contains('auto-expand')) {
                                displayNameInput.style.height = 'auto';
                                displayNameInput.style.height = displayNameInput.scrollHeight + 'px';
                            }
                        }
                    };
                    
                    displayRegulationButtons.appendChild(btn);
                });
            } else if (displayRegulationButtons) {
                displayRegulationButtons.style.display = 'none';
            }
            
            // 기본 설명 숨기고 표시규정 표시
            if (ingredientDisplayNameHelp) ingredientDisplayNameHelp.style.display = 'none';
            displayRegulationInfo.style.display = '';
        } else {
            displayRegulationInfo.style.display = 'none';
            if (ingredientDisplayNameHelp) ingredientDisplayNameHelp.style.display = '';
            displayRegulationDisplay.textContent = '';
            if (displayRegulationButtons) displayRegulationButtons.style.display = 'none';
        }
    })
    .catch(error => {
        console.error('Error fetching regulation info:', error);
        displayRegulationInfo.style.display = 'none';
        if (ingredientDisplayNameHelp) ingredientDisplayNameHelp.style.display = '';
        displayRegulationDisplay.textContent = '';
        if (displayRegulationButtons) displayRegulationButtons.style.display = 'none';
    });
}

// textarea 자동 확장 함수들
function adjustTextareaHeight(element, maxHeight = 200) {
    if (!element) return;
    element.style.height = 'auto';
    const scrollHeight = element.scrollHeight + 2;
    element.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
}

function initAutoExpandTextareas() {
    // 모든 auto-expand textarea에 이벤트 리스너 추가
    document.querySelectorAll('textarea.auto-expand').forEach(textarea => {
        // 초기 높이 조정
        adjustTextareaHeight(textarea);
        
        // input 이벤트 리스너
        textarea.addEventListener('input', () => adjustTextareaHeight(textarea));
        textarea.addEventListener('change', () => adjustTextareaHeight(textarea));
    });
}

})(); // IIFE 끝