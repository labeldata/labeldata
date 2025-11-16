// 알레르기 정보를 업데이트하는 함수
function updateAllergyInfo() {
    const allergyOptions = document.querySelectorAll('#allergySelection input[type="checkbox"]');
    const selectedAllergies = [];
    
    allergyOptions.forEach(option => {
        if (option.checked) {
            selectedAllergies.push(option.value);
        }
    });
    
    // 선택된 알레르기를 단일 문자열로 결합하여 필드에 설정
    var allergyField = document.getElementById('allergy_info') || document.getElementById('allergens');
    if (allergyField) {
        allergyField.value = selectedAllergies.join(', ');
    }
}
window.updateAllergyInfo = updateAllergyInfo;

// GMO 정보를 업데이트하는 함수 (체크박스용)
function updateGmoInfo() {
    const gmoOptions = document.querySelectorAll('#gmoSelection input[type="checkbox"]');
    let selectedGmos = [];
    
    gmoOptions.forEach(option => {
        if (option.checked) {
            selectedGmos.push(option.value);
        }
    });
    
    // 선택된 GMO 정보를 필드에 설정 (콤마로 구분)
    var gmoField = document.getElementById('gmo_info') || document.getElementById('gmo');
    if (gmoField) {
        gmoField.value = selectedGmos.join(', ');
    }
}
window.updateGmoInfo = updateGmoInfo;

// 알레르기 옵션 표시 함수
function showAllergyOptions() {
    const optionsContainer = document.getElementById('allergyOptions');
    if (!optionsContainer) return;
    optionsContainer.innerHTML = '';
    const currentAllergies = document.getElementById('allergy_info').value.split(',').map(s => s.trim());
    
    // constants.js의 ALLERGEN_KEYWORDS와 일치하는 19개 알레르기 항목
    const allergyOptions = [
        '알류', '우유', '메밀', '밀', '대두', '땅콩', '호두', '잣',
        '쇠고기', '돼지고기', '닭고기', '고등어', '게', '새우', '오징어',
        '조개류', '복숭아', '토마토', '아황산류'
    ];
    
    allergyOptions.forEach(option => {
        const div = document.createElement('div');
        div.className = 'form-check form-check-inline mb-1';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'form-check-input';
        input.id = `allergy-${option}`;
        input.value = option;
        input.checked = currentAllergies.includes(option);
        input.onchange = updateAllergyInfo;
        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.htmlFor = `allergy-${option}`;
        label.textContent = option;
        div.appendChild(input);
        div.appendChild(label);
        optionsContainer.appendChild(div);
    });
}
window.showAllergyOptions = showAllergyOptions;

// GMO 옵션 표시 함수 (체크박스용)
function showGmoOptions() {
    const optionsContainer = document.getElementById('gmoOptions');
    if (!optionsContainer) return;
    optionsContainer.innerHTML = '';
    const currentGmo = document.getElementById('gmo_info').value.trim();
    const currentGmos = currentGmo ? currentGmo.split(',').map(g => g.trim()) : [];
    const gmoOptions = ['대두', '옥수수', '면화', '카놀라', '사탕무', '알팔파'];
    gmoOptions.forEach(option => {
        const div = document.createElement('div');
        div.className = 'form-check form-check-inline mb-1';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'form-check-input';
        input.name = 'gmo-option';
        input.id = `gmo-${option}`;
        input.value = option;
        input.checked = currentGmos.includes(option);
        input.onchange = updateGmoInfo;
        const label = document.createElement('label');
        label.className = 'form-check-label';
        label.htmlFor = `gmo-${option}`;
        label.textContent = option;
        div.appendChild(input);
        div.appendChild(label);
        optionsContainer.appendChild(div);
    });
}
window.showGmoOptions = showGmoOptions;

// 알레르기 선택 칸을 접었다 폈다 하는 함수
function toggleAllergySelection() {
    const container = document.getElementById('allergySelection');
    const button = document.getElementById('allergyToggleButton');
    if (container.style.display === 'none' || container.style.display === '') {
        showAllergyOptions(); // 펼칠 때 옵션 동적 생성
        container.style.display = 'flex';
        button.textContent = '접기';
    } else {
        container.style.display = 'none';
        button.textContent = '선택';
    }
}
window.toggleAllergySelection = toggleAllergySelection;

// gmo 선택 칸을 접었다 폈다 하는 함수
function toggleGmoSelection() {
    const container = document.getElementById('gmoSelection');
    const button = document.getElementById('gmoToggleButton');
    if (container.style.display === 'none' || container.style.display === '') {
        showGmoOptions(); // 펼칠 때 옵션 동적 생성
        container.style.display = 'flex';
        button.textContent = '접기';
    } else {
        container.style.display = 'none';
        button.textContent = '선택';
    }
}
window.toggleGmoSelection = toggleGmoSelection;

// 페이지 로드 시 알레르기 옵션 표시 코드 제거 (ingredient_detail.js에서 처리)
// document.addEventListener('DOMContentLoaded', () => {
//     showAllergyOptions();
//     showGmoOptions();
//     document.getElementById('allergySelection').style.display = 'none';
//     document.getElementById('gmoSelection').style.display = 'none';
// });

// 대신 초기화 함수를 추가하여 필요할 때 호출
function initializeSelections() {
    if (document.getElementById('allergySelection')) {
        document.getElementById('allergySelection').style.display = 'none'; // 초기 상태를 숨김으로 설정
    }
    if (document.getElementById('gmoSelection')) {
        document.getElementById('gmoSelection').style.display = 'none'; // 초기 상태를 숨김으로 설정
    }
}
window.initializeSelections = initializeSelections;