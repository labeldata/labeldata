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
    document.getElementById('allergens').value = selectedAllergies.join(', ');
}

// GMO 정보를 업데이트하는 함수
function updateGmoInfo() {
    const gmoOptions = document.querySelectorAll('#gmoSelection input[type="radio"]');
    let selectedGmo = '';
    
    gmoOptions.forEach(option => {
        if (option.checked) {
            selectedGmo = option.value;
        }
    });
    
    // 선택된 GMO 정보를 필드에 설정
    document.getElementById('gmo').value = selectedGmo;
}

// 알레르기 옵션 표시 함수
function showAllergyOptions() {
    const container = document.getElementById('allergySelection');
    if (!container) return;
    
    // 현재 알레르기 값 가져오기
    const currentAllergies = document.getElementById('allergens').value;
    const selectedOptions = currentAllergies.split(',').map(item => item.trim());
    
    // 알레르기 옵션 목록
    const allergyOptions = [
        '난류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우', 
        '돼지고기', '복숭아', '토마토', '아황산류', '호두', '닭고기', '쇠고기', '오징어', '조개류'
    ];
    
    // 각 알레르기 옵션에 대한 체크박스 생성
    allergyOptions.forEach(option => {
        const isChecked = selectedOptions.includes(option);
        
        const div = document.createElement('div');
        div.className = 'allergy-option';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `allergy-${option}`;
        input.value = option;
        input.checked = isChecked;
        input.onchange = updateAllergyInfo; // 체크박스 변경 시 알레르기 정보 업데이트
        
        const label = document.createElement('label');
        label.htmlFor = `allergy-${option}`;
        label.textContent = option;
        
        div.appendChild(input);
        div.appendChild(label);
        container.appendChild(div);
    });
}

// GMO 옵션 표시 함수
function showGmoOptions() {
    const container = document.getElementById('gmoSelection');
    if (!container) return;
    
    // 현재 GMO 값 가져오기
    const currentGmo = document.getElementById('gmo').value.trim();
    
    // GMO 옵션 목록
    const gmoOptions = ['GMO 없음', 'Non-GMO', 'GMO'];
    
    // 각 GMO 옵션에 대한 라디오 버튼 생성
    gmoOptions.forEach(option => {
        const isChecked = currentGmo === option;
        
        const div = document.createElement('div');
        div.className = 'gmo-option';
        
        const input = document.createElement('input');
        input.type = 'radio';
        input.name = 'gmo-option';
        input.id = `gmo-${option}`;
        input.value = option;
        input.checked = isChecked;
        input.onchange = updateGmoInfo; // 라디오 버튼 변경 시 GMO 정보 업데이트
        
        const label = document.createElement('label');
        label.htmlFor = `gmo-${option}`;
        label.textContent = option;
        
        div.appendChild(input);
        div.appendChild(label);
        container.appendChild(div);
    });
}

// 알레르기 선택 칸을 접었다 폈다 하는 함수
function toggleAllergySelection() {
    const container = document.getElementById('allergySelection');
    const button = document.getElementById('allergyToggleButton');
    if (container.style.display === 'none' || container.style.display === '') {
        container.style.display = 'flex';
        button.textContent = '접기';
    } else {
        container.style.display = 'none';
        button.textContent = '펼치기';
    }
}
// gmo 선택 칸을 접었다 폈다 하는 함수
function toggleGmoSelection() {
    const container = document.getElementById('gmoSelection');
    const button = document.getElementById('gmoToggleButton');
    if (container.style.display === 'none' || container.style.display === '') {
        container.style.display = 'flex';
        button.textContent = '접기';
    } else {
        container.style.display = 'none';
        button.textContent = '펼치기';
    }
}

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