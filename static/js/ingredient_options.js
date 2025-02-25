// js/ingredient_options.js

// 알레르기 옵션 팝업 함수
function showAllergyOptions(input) {
    const options = [
        '난류(가금류)', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우', '돼지고기',
        '복숭아', '토마토', '아황산류', '호두', '닭고기', '쇠고기', '오징어', '조개류', '조개류(굴)',
        '조개류(전복)', '조개류(홍합)', '잣'
    ];
    const container = document.createElement('div');
    container.className = 'options-container';
    
    // 컨테이너를 문서 body에 추가하고, input 위치에 맞게 배치
    document.body.appendChild(container);
    container.style.position = 'absolute';
    const rect = input.getBoundingClientRect();
    container.style.top = (rect.bottom + window.scrollY) + 'px';
    container.style.left = (rect.left + window.scrollX) + 'px';
    
    const saveButton = document.createElement('button');
    saveButton.textContent = '저장';
    saveButton.className = 'btn btn-primary btn-sm';
    saveButton.onclick = () => saveOptions(input, container);
    container.appendChild(saveButton);

    options.forEach(option => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = option;
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(option));
        container.appendChild(label);
    });

    // 외부 클릭 감지해서 옵션 컨테이너 제거
    setTimeout(() => {
      document.addEventListener('click', function handler(event) {
          if (!container.contains(event.target) && event.target !== input) {
              container.remove();
              document.removeEventListener('click', handler);
          }
      });
    }, 0);
}

// GMO 옵션 팝업 함수
function showGMOOptions(input) {
    const options = ['콩', '옥수수', '면화', '카놀라', '사탕무', '알팔파'];
    const container = document.createElement('div');
    container.className = 'options-container';
    
    // 컨테이너를 body에 추가하고, input 위치에 맞게 배치
    document.body.appendChild(container);
    container.style.position = 'absolute';
    const rect = input.getBoundingClientRect();
    container.style.top = (rect.bottom + window.scrollY) + 'px';
    container.style.left = (rect.left + window.scrollX) + 'px';
    
    const saveButton = document.createElement('button');
    saveButton.textContent = '저장';
    saveButton.className = 'btn btn-primary btn-sm';
    saveButton.onclick = () => saveOptions(input, container);
    container.appendChild(saveButton);

    options.forEach(option => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = option;
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(option));
        container.appendChild(label);
    });

    // 외부 클릭 감지해서 옵션 컨테이너 제거
    setTimeout(() => {
      document.addEventListener('click', function handler(event) {
          if (!container.contains(event.target) && event.target !== input) {
              container.remove();
              document.removeEventListener('click', handler);
          }
      });
    }, 0);
}

// 선택된 옵션을 input에 저장하는 함수
function saveOptions(input, container) {
    const selectedOptions = Array.from(container.querySelectorAll('input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.value)
        .join(', ');
    input.value = selectedOptions;
    container.remove();
}
