// 영양성분 정의
const NUTRITION_DATA = {
  // 기본 영양성분 (항상 표시)
  'calories': { label: '열량', unit: 'kcal', order: 1, basic: true },
  'carbohydrate': { label: '탄수화물', unit: 'g', order: 2, basic: true },
  'sugars': { label: '당류', unit: 'g', order: 3, parent: 'carbohydrate', indent: true, basic: true },
  'protein': { label: '단백질', unit: 'g', order: 4, basic: true },
  'fat': { label: '지방', unit: 'g', order: 5, basic: true },
  'saturated_fat': { label: '포화지방', unit: 'g', order: 6, parent: 'fat', indent: true, basic: true },
  'trans_fat': { label: '트랜스지방', unit: 'g', order: 7, parent: 'fat', indent: true, basic: true },
  'sodium': { label: '나트륨', unit: 'mg', order: 8, basic: true },
  'cholesterol': { label: '콜레스테롤', unit: 'mg', order: 9, basic: true },
  
  // 추가 영양성분
  'dietary_fiber': { label: '식이섬유', unit: 'g', order: 10 },
  'calcium': { label: '칼슘', unit: 'mg', order: 11 },
  'iron': { label: '철', unit: 'mg', order: 12 },
  'vitamin_a': { label: '비타민A', unit: 'μg RAE', order: 13 },
  'vitamin_c': { label: '비타민C', unit: 'mg', order: 14 },
  'potassium': { label: '칼륨', unit: 'mg', order: 15 },
  'magnesium': { label: '마그네슘', unit: 'mg', order: 16 },
  'phosphorus': { label: '인', unit: 'mg', order: 17 },
  'zinc': { label: '아연', unit: 'mg', order: 18 },
  'vitamin_d': { label: '비타민D', unit: 'μg', order: 19 },
  'vitamin_e': { label: '비타민E', unit: 'mg α-TE', order: 20 },
  'vitamin_b1': { label: '비타민B1', unit: 'mg', order: 21 },
  'vitamin_b2': { label: '비타민B2', unit: 'mg', order: 22 },
  'niacin': { label: '나이아신', unit: 'mg NE', order: 23 },
  'folic_acid': { label: '엽산', unit: 'μg DFE', order: 24 },
  'vitamin_b12': { label: '비타민B12', unit: 'μg', order: 25 },
  'biotin': { label: '비오틴', unit: 'μg', order: 26 },
  'pantothenic_acid': { label: '판토텐산', unit: 'mg', order: 27 },
  'iodine': { label: '요오드', unit: 'μg', order: 28 },
  'selenium': { label: '셀레늄', unit: 'μg', order: 29 },
  'copper': { label: '구리', unit: 'mg', order: 30 },
  'manganese': { label: '망간', unit: 'mg', order: 31 },
  'chromium': { label: '크롬', unit: 'μg', order: 32 },
  'molybdenum': { label: '몰리브덴', unit: 'μg', order: 33 }
};

// 전역 변수
let currentNutritionData = {};
let productName = ''; // 제품명 저장용

// 페이지 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
  buildInputForm();
  
  // URL 파라미터에서 기존 데이터 로드
  loadExistingDataFromUrl();
  
  // 커스텀 이벤트 발생
  const event = new CustomEvent('nutrition-calculator-ready');
  document.dispatchEvent(event);
});

// URL 파라미터에서 기존 데이터 로드
function loadExistingDataFromUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  console.log('URL 파라미터:', urlParams.toString());
  
  // 제품명 로드
  const productNameParam = urlParams.get('product_name');
  if (productNameParam) {
    productName = productNameParam;
    console.log('제품명 로드:', productName);
  }
  
  // 기본 설정값 로드
  const servingSize = urlParams.get('serving_size');
  const servingSizeUnit = urlParams.get('serving_size_unit');
  const unitsPerPackage = urlParams.get('units_per_package');
  const nutritionStyle = urlParams.get('nutrition_style');
  const nutritionDisplayType = urlParams.get('nutrition_display_type');
  const nutritionBaseAmount = urlParams.get('nutrition_base_amount');
  const nutritionBaseAmountUnit = urlParams.get('nutrition_base_amount_unit');
  
  // 기본 설정값 적용
  if (servingSize) {
    const baseAmountField = document.getElementById('base_amount');
    if (baseAmountField) baseAmountField.value = servingSize;
  }
  
  if (unitsPerPackage) {
    const servingsField = document.getElementById('servings_per_package');
    if (servingsField) servingsField.value = unitsPerPackage;
  }
  
  // 영양성분 표시 스타일 설정
  if (nutritionStyle) {
    const styleField = document.getElementById('nutrition_style');
    if (styleField) {
      styleField.value = nutritionStyle;
      // 스타일 변경 시 옵션 토글
      if (window.toggleStyleOptions) {
        toggleStyleOptions();
      }
    }
  }
  
  // 표시 타입 설정
  if (nutritionDisplayType) {
    if (nutritionStyle === 'parallel') {
      const parallelTypeField = document.getElementById('parallel_display_type');
      if (parallelTypeField) parallelTypeField.value = nutritionDisplayType;
    } else {
      const basicTypeField = document.getElementById('basic_display_type');
      if (basicTypeField) basicTypeField.value = nutritionDisplayType;
    }
  }
  
  // 영양성분 필드 매핑 (메인 페이지 -> 계산기)
  const fieldMapping = {
    'calories': 'calories',
    'natriums': 'sodium',
    'carbohydrates': 'carbohydrate',
    'sugars': 'sugars',
    'fats': 'fat',
    'trans_fats': 'trans_fat',
    'saturated_fats': 'saturated_fat',
    'cholesterols': 'cholesterol',
    'proteins': 'protein'
  };
  
  // 영양성분 데이터 로드
  Object.keys(fieldMapping).forEach(mainFieldName => {
    const calculatorFieldName = fieldMapping[mainFieldName];
    const value = urlParams.get(mainFieldName);
    
    if (value && value !== '') {
      const field = document.getElementById(calculatorFieldName);
      if (field) {
        field.value = value;
        console.log(`기존 데이터 로드: ${calculatorFieldName} = ${value}`);
      }
    }
  });
  
  // 데이터가 있으면 자동 계산
  if (servingSize && unitsPerPackage) {
    setTimeout(() => {
      calculateNutrition();
    }, 500);
  }
}

// 입력 폼 생성
function buildInputForm() {
  console.log('buildInputForm 함수 호출됨');
  
  const basicContainer = document.getElementById('basic-nutrient-inputs');
  const additionalContainer = document.getElementById('additional-nutrient-inputs');
  
  console.log('basicContainer:', basicContainer);
  console.log('additionalContainer:', additionalContainer);
  
  if (!basicContainer || !additionalContainer) {
    console.error('영양성분 컨테이너를 찾을 수 없습니다.');
    console.error('basic-nutrient-inputs 존재:', !!basicContainer);
    console.error('additional-nutrient-inputs 존재:', !!additionalContainer);
    return;
  }
  
  basicContainer.innerHTML = '';
  additionalContainer.innerHTML = '';
  
  console.log('NUTRITION_DATA:', NUTRITION_DATA);
  
  // 영양성분을 순서대로 정렬
  const sortedNutrients = Object.entries(NUTRITION_DATA)
    .sort((a, b) => a[1].order - b[1].order);
  
  console.log('sortedNutrients:', sortedNutrients);
  
  let basicCount = 0;
  let additionalCount = 0;
  
  sortedNutrients.forEach(([key, data]) => {
    console.log(`영양성분 생성 중: ${key}`, data);
    
    const item = document.createElement('div');
    item.className = 'nutrient-item';
    
    if (data.indent) {
      item.classList.add('sub-item');
    }
    
    const label = document.createElement('label');
    label.textContent = data.label;
    if (data.indent) {
      label.classList.add('indent');
    }
    
    const input = document.createElement('input');
    input.type = 'number';
    input.id = key;
    input.placeholder = '0';
    input.step = 'any';
    input.min = '0';
    input.max = '99999';
    
    const unitSpan = document.createElement('select');
    unitSpan.innerHTML = `<option value="${data.unit}">${data.unit}</option>`;
    
    item.appendChild(label);
    item.appendChild(input);
    item.appendChild(unitSpan);
    
    // 기본 영양성분과 추가 영양성분으로 분리
    if (data.basic) {
      basicContainer.appendChild(item);
      basicCount++;
      console.log(`기본 영양성분 추가: ${key} (총 ${basicCount}개)`);
    } else {
      additionalContainer.appendChild(item);
      additionalCount++;
      console.log(`추가 영양성분 추가: ${key} (총 ${additionalCount}개)`);
    }
  });
  
  console.log(`영양성분 입력 폼 생성 완료 - 기본: ${basicCount}개, 추가: ${additionalCount}개`);
}

// 영양성분 계산
function calculateNutrition() {
  // 계산 버튼을 비활성화하고 로딩 표시
  const calculateBtn = document.getElementById('calculateBtn');
  const originalText = calculateBtn.innerHTML;
  calculateBtn.disabled = true;
  calculateBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>계산 중...';
  
  const baseAmount = parseFloat(document.getElementById('base_amount').value) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('servings_per_package').value) || 1;
  const style = document.getElementById('nutrition_style').value;
  
  // 입력된 영양성분 데이터 수집
  const nutritionInputs = {};
  Object.keys(NUTRITION_DATA).forEach(key => {
    const input = document.getElementById(key);
    if (input && input.value) {
      nutritionInputs[key] = parseFloat(input.value);
    }
  });
  
  if (Object.keys(nutritionInputs).length === 0) {
    alert('영양성분을 입력해주세요.');
    calculateBtn.disabled = false;
    calculateBtn.innerHTML = originalText;
    return;
  }
  
  // 짧은 지연 후 계산 실행 (UI 반응성 개선)
  setTimeout(() => {
    try {
      // 현재 데이터 저장
      currentNutritionData = {
        base_amount: baseAmount,
        servings_per_package: servingsPerPackage,
        nutrition_style: style,
        inputs: nutritionInputs
      };
      
      // 계산 및 결과 표시
      performNutritionCalculation(nutritionInputs, baseAmount, servingsPerPackage, style);
      
    } catch (error) {
      console.error('계산 오류:', error);
      alert('계산 중 오류가 발생했습니다: ' + error.message);
    } finally {
      // 버튼 복원
      calculateBtn.disabled = false;
      calculateBtn.innerHTML = originalText;
    }
  }, 300);
}

// 실제 영양성분 계산 수행
function performNutritionCalculation(nutritionInputs, baseAmount, servingsPerPackage, style) {
  // 표시 방식에 따른 계산 및 표시
  let displayHTML = '';
  
  if (style === 'parallel') {
    displayHTML = generateParallelDisplay(nutritionInputs, baseAmount, servingsPerPackage);
  } else {
    displayHTML = generateBasicDisplay(nutritionInputs, baseAmount, servingsPerPackage, style);
  }
  
  document.getElementById('resultDisplay').innerHTML = displayHTML;
}

// 기본형/세로형 표시 생성
function generateBasicDisplay(nutritionInputs, baseAmount, servingsPerPackage, style) {
  const displayType = document.getElementById('basic_display_type').value;
  let multiplier = 1;
  let displayUnit = '';
  
  switch (displayType) {
    case 'total':
      multiplier = (baseAmount / 100) * servingsPerPackage;
      displayUnit = `총 내용량당(${(baseAmount * servingsPerPackage)}g)`;
      break;
    case 'unit':
      multiplier = baseAmount / 100;
      displayUnit = `단위내용량당(${baseAmount}g)`;
      break;
    case '100g':
      multiplier = 1;
      displayUnit = '100g당';
      break;
  }
  
  const styleClass = `nutrition-style-${style}`;
  
  let html = `<div class="${styleClass}">`;
  html += '<table class="nutrition-table">';
  html += `<tr><td class="nutrition-header" colspan="2">영양정보</td></tr>`;
  html += `<tr><td class="nutrition-subheader" colspan="2">${displayUnit}</td></tr>`;
  
  // 영양성분을 순서대로 정렬
  const sortedNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => nutritionInputs[key] !== undefined)
    .sort((a, b) => a[1].order - b[1].order);
  
  sortedNutrients.forEach(([key, data]) => {
    const value = nutritionInputs[key] * multiplier;
    const displayValue = value % 1 === 0 ? value.toString() : value.toFixed(1);
    
    html += '<tr class="nutrition-row">';
    html += `<td class="nutrition-name${data.indent ? ' nutrition-indent' : ''}">${data.label}</td>`;
    html += `<td class="nutrition-value">${displayValue}${data.unit}</td>`;
    html += '</tr>';
  });
  
  html += '</table></div>';
  return html;
}

// 병행표시 생성
function generateParallelDisplay(nutritionInputs, baseAmount, servingsPerPackage) {
  const displayType = document.getElementById('parallel_display_type').value;
  let multiplier1 = 1, multiplier2 = 1;
  let unit1 = '', unit2 = '';
  
  switch (displayType) {
    case 'unit_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = (baseAmount / 100) * servingsPerPackage;
      unit1 = `단위내용량당(${baseAmount}g)`;
      unit2 = `총내용량당(${baseAmount * servingsPerPackage}g)`;
      break;
    case 'unit_100g':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      unit1 = `단위내용량당(${baseAmount}g)`;
      unit2 = '100g당';
      break;
    case 'serving_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = (baseAmount / 100) * servingsPerPackage;
      unit1 = `1회 섭취참고량당(${baseAmount}g)`;
      unit2 = `총내용량당(${baseAmount * servingsPerPackage}g)`;
      break;
    case 'serving_100ml':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      unit1 = `1회 섭취참고량당(${baseAmount}ml)`;
      unit2 = '100ml당';
      break;
  }
  
  let html = '<div class="nutrition-style-parallel">';
  html += '<table class="nutrition-table">';
  html += '<tr><td class="nutrition-header" colspan="4">영양정보</td></tr>';
  html += '<tr>';
  html += `<td class="nutrition-subheader" colspan="2">${unit1}</td>`;
  html += `<td class="nutrition-subheader" colspan="2">${unit2}</td>`;
  html += '</tr>';
  
  // 영양성분을 순서대로 정렬
  const sortedNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => nutritionInputs[key] !== undefined)
    .sort((a, b) => a[1].order - b[1].order);
  
  sortedNutrients.forEach(([key, data]) => {
    const value1 = nutritionInputs[key] * multiplier1;
    const value2 = nutritionInputs[key] * multiplier2;
    const displayValue1 = value1 % 1 === 0 ? value1.toString() : value1.toFixed(1);
    const displayValue2 = value2 % 1 === 0 ? value2.toString() : value2.toFixed(1);
    
    html += '<tr class="nutrition-row">';
    html += `<td class="nutrition-name${data.indent ? ' nutrition-indent' : ''}">${data.label}</td>`;
    html += `<td class="nutrition-value">${displayValue1}${data.unit}</td>`;
    html += `<td class="nutrition-name${data.indent ? ' nutrition-indent' : ''}">${data.label}</td>`;
    html += `<td class="nutrition-value">${displayValue2}${data.unit}</td>`;
    html += '</tr>';
  });
  
  html += '</table></div>';
  return html;
}

// 폼 및 부모 창 초기화
function resetFormAndParent() {
  if (confirm('모든 입력 내용을 초기화하시겠습니까?')) {
    // 폼 초기화
    document.getElementById('base_amount').value = '100';
    document.getElementById('servings_per_package').value = '1';
    document.getElementById('nutrition_style').value = 'basic';
    toggleStyleOptions();
    
    // 영양성분 입력 초기화
    Object.keys(NUTRITION_DATA).forEach(key => {
      const input = document.getElementById(key);
      if (input) {
        input.value = '';
      }
    });
    
    // 결과 초기화
    document.getElementById('resultDisplay').innerHTML = 
      '<div class="empty-result">영양성분을 입력하고 계산 버튼을 눌러주세요.</div>';
    
    // 전역 데이터 초기화
    currentNutritionData = {};
    
    // 부모 창에 초기화 신호 전송
    try {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({
          type: 'nutrition-data-reset'
        }, '*');
      }
    } catch (error) {
      console.error('부모 창 통신 오류:', error);
    }
  }
}

// 부모 창에 영양성분 데이터 전송
function sendNutritionDataToParent() {
  console.log('sendNutritionDataToParent 호출됨');
  console.log('currentNutritionData:', currentNutritionData);
  
  if (Object.keys(currentNutritionData).length === 0) {
    alert('먼저 영양성분을 계산해주세요.');
    return;
  }
  
  // 저장 버튼을 비활성화하고 로딩 표시
  const saveButton = document.querySelector('.btn-success');
  const originalText = saveButton.innerHTML;
  saveButton.disabled = true;
  saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>저장 중...';
  
  try {
    if (window.opener && !window.opener.closed) {
      // 결과 HTML도 함께 전송
      const resultDisplay = document.getElementById('resultDisplay');
      const resultHTML = resultDisplay ? resultDisplay.innerHTML : '';
      
      console.log('resultHTML:', resultHTML);
      
      // 영양성분 데이터를 부모 창에 전송 (항목명, 숫자, 단위 형태로)
      const formattedData = {};
      Object.keys(NUTRITION_DATA).forEach(key => {
        const input = document.getElementById(key);
        if (input && input.value) {
          const nutritionInfo = NUTRITION_DATA[key];
          formattedData[key] = {
            label: nutritionInfo.label,
            value: parseFloat(input.value),
            unit: nutritionInfo.unit,
            order: nutritionInfo.order,
            indent: nutritionInfo.indent || false
          };
        }
      });
      
      console.log('formattedData:', formattedData);
      
      const messageData = {
        type: 'nutrition-data-updated',
        data: currentNutritionData, // 계산용 원본 데이터
        formattedData: formattedData, // 표시용 포맷된 데이터
        resultHTML: resultHTML,
        settings: {
          base_amount: document.getElementById('base_amount').value,
          base_amount_unit: 'g', // 기본 단위
          servings_per_package: document.getElementById('servings_per_package').value,
          nutrition_style: document.getElementById('nutrition_style').value,
          display_type: document.getElementById('nutrition_style').value === 'parallel' 
            ? document.getElementById('parallel_display_type').value 
            : document.getElementById('basic_display_type').value
        }
      };
      
      console.log('부모 창에 전송할 데이터:', messageData);
      
      window.opener.postMessage(messageData, '*');
      
      // 성공 후 잠시 대기하고 창 닫기
      setTimeout(() => {
        alert('영양성분 데이터가 저장되었습니다.');
        window.close();
      }, 500);
      
    } else {
      console.error('부모 창이 없거나 닫혀있음');
      alert('부모 창을 찾을 수 없습니다.');
      saveButton.disabled = false;
      saveButton.innerHTML = originalText;
    }
  } catch (error) {
    console.error('데이터 전송 오류:', error);
    alert('데이터 전송 중 오류가 발생했습니다: ' + error.message);
    saveButton.disabled = false;
    saveButton.innerHTML = originalText;
  }
}

// PDF 내보내기
function exportToPDF() {
  if (Object.keys(currentNutritionData).length === 0) {
    alert('먼저 영양성분을 계산해주세요.');
    return;
  }
  
  // PDF 버튼을 비활성화하고 로딩 표시
  const pdfButton = document.querySelector('button[onclick="exportToPDF()"]');
  const originalText = pdfButton.innerHTML;
  pdfButton.disabled = true;
  pdfButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>PDF 생성 중...';
  
  // 결과 영역만 PDF로 변환
  const resultDisplay = document.getElementById('resultDisplay');
  
  if (!resultDisplay || resultDisplay.innerHTML.includes('영양성분을 입력하고 계산 버튼을 눌러주세요.')) {
    alert('영양성분 계산 결과가 없습니다.');
    pdfButton.disabled = false;
    pdfButton.innerHTML = originalText;
    return;
  }
  
  // html2canvas로 영역을 이미지로 변환
  html2canvas(resultDisplay, {
    scale: 2, // 고해상도
    useCORS: true,
    backgroundColor: '#ffffff',
    logging: false
  }).then(canvas => {
    try {
      // jsPDF 인스턴스 생성
      const { jsPDF } = window.jspdf;
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4'
      });
      
      // 이미지 크기 계산
      const imgWidth = 190; // A4 너비에서 여백 제외
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      
      // 현재 날짜와 시간으로 파일명 생성
      const now = new Date();
      const dateStr = now.getFullYear() + 
        String(now.getMonth() + 1).padStart(2, '0') + 
        String(now.getDate()).padStart(2, '0');
      
      // 파일명에 제품명 포함 (특수문자 제거)
      let fileName = '영양성분표';
      if (productName) {
        const cleanProductName = productName.replace(/[<>:"/\\|?*]/g, '').trim();
        if (cleanProductName) {
          fileName += `_${cleanProductName}`;
        }
      }
      fileName += `_${dateStr}`;
      
      // 제목 추가
      pdf.setFontSize(16);
      pdf.text('영양성분표', 105, 20, { align: 'center' });
      
      // 제품명 추가 (있는 경우)
      if (productName) {
        pdf.setFontSize(12);
        pdf.text(`제품명: ${productName}`, 10, 35);
      }
      
      // 생성 일시 추가
      pdf.setFontSize(10);
      pdf.text(`생성일시: ${now.toLocaleString('ko-KR')}`, 10, productName ? 45 : 35);
      
      // 이미지 추가 (제품명 유무에 따라 위치 조정)
      const imgData = canvas.toDataURL('image/png');
      const yPosition = productName ? 55 : 45;
      pdf.addImage(imgData, 'PNG', 10, yPosition, imgWidth, imgHeight);
      
      // PDF 저장
      pdf.save(`${fileName}.pdf`);
      
      // 성공 메시지
      alert('PDF가 성공적으로 저장되었습니다.');
      
    } catch (error) {
      console.error('PDF 생성 오류:', error);
      alert('PDF 생성 중 오류가 발생했습니다: ' + error.message);
    } finally {
      // 버튼 복원
      pdfButton.disabled = false;
      pdfButton.innerHTML = originalText;
    }
  }).catch(error => {
    console.error('이미지 변환 오류:', error);
    alert('이미지 변환 중 오류가 발생했습니다: ' + error.message);
    pdfButton.disabled = false;
    pdfButton.innerHTML = originalText;
  });
}

// 스타일 옵션 토글
window.toggleStyleOptions = function() {
  const style = document.getElementById('nutrition_style').value;
  const basicVerticalOptions = document.getElementById('basic-vertical-options');
  const parallelOptions = document.getElementById('parallel-options');
  
  if (style === 'parallel') {
    basicVerticalOptions.classList.remove('show');
    parallelOptions.classList.add('show');
  } else {
    basicVerticalOptions.classList.add('show');
    parallelOptions.classList.remove('show');
  }
  
  // 스타일 변경 시 자동 계산
  if (document.getElementById('base_amount').value && document.getElementById('servings_per_package').value) {
    calculateNutrition();
  }
};

// 영양성분 섹션 토글
window.toggleNutritionSection = function() {
  const additionalSection = document.getElementById('additional-nutrients');
  const toggleIcon = document.getElementById('nutrition-toggle');
  const toggleText = document.getElementById('nutrition-toggle-text');
  
  if (additionalSection.style.display === 'none') {
    additionalSection.style.display = 'block';
    toggleIcon.textContent = '▲';
    toggleIcon.classList.add('rotated');
    toggleText.textContent = '성분 접기';
  } else {
    additionalSection.style.display = 'none';
    toggleIcon.textContent = '▼';
    toggleIcon.classList.remove('rotated');
    toggleText.textContent = '성분 추가';
  }
};

// 기존 데이터 로드
function loadExistingData(data) {
  try {
    // 기본 정보 설정
    if (data.base_amount) {
      document.getElementById('base_amount').value = data.base_amount;
    }
    if (data.servings_per_package) {
      document.getElementById('servings_per_package').value = data.servings_per_package;
    }
    if (data.nutrition_style) {
      document.getElementById('nutrition_style').value = data.nutrition_style;
      toggleStyleOptions();
    }
    
    // 영양성분 데이터 설정
    Object.keys(NUTRITION_DATA).forEach(key => {
      const input = document.getElementById(key);
      if (input && data[key] !== undefined) {
        input.value = data[key];
      }
    });
    
    // 자동 계산
    if (data.base_amount && data.servings_per_package) {
      calculateNutrition();
    }
    
    // 계산기에서는 항상 수정 가능한 상태로 유지
    console.log('기존 데이터를 로드했습니다. 계산기에서는 수정이 가능합니다.');
  } catch (error) {
    console.error('데이터 로드 중 오류:', error);
  }
}

// 전역 함수로 노출
window.calculateNutrition = calculateNutrition;
window.resetFormAndParent = resetFormAndParent;
window.sendNutritionDataToParent = sendNutritionDataToParent;
window.exportToPDF = exportToPDF;
window.loadExistingData = loadExistingData;
