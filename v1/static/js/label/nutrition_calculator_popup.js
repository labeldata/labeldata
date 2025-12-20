// 영양성분 계산기 모듈 - 리팩토링된 버전
(function() {
'use strict';

// 영양성분 상수는 constants.js에서 로드됨
// window.NUTRITION_DATA, window.EMPHASIS_CRITERIA 사용

// 전역 변수
let currentNutritionData = {};

// ===== 유틸리티 함수들 =====

// 숫자에 쉼표 추가
function formatNumberWithCommas(num) {
  if (typeof num === 'string') {
    return num;
  }
  if (typeof num !== 'number' || isNaN(num)) {
    return '0';
  }
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// 강조표시 가능 여부 검증 함수
function checkEmphasisEligibility(key, value) {
  if (!value || value === 0) return null;
  
  const emphasis = [];
  
  // 무 함유 기준 확인
  if (EMPHASIS_CRITERIA.free[key] && value < EMPHASIS_CRITERIA.free[key].threshold) {
    emphasis.push({
      type: 'free',
      label: EMPHASIS_CRITERIA.free[key].label,
      threshold: EMPHASIS_CRITERIA.free[key].threshold
    });
  }
  
  // 저 함유 기준 확인
  if (EMPHASIS_CRITERIA.low[key] && value <= EMPHASIS_CRITERIA.low[key].threshold) {
    emphasis.push({
      type: 'low',
      label: EMPHASIS_CRITERIA.low[key].label,
      threshold: EMPHASIS_CRITERIA.low[key].threshold
    });
  }
  
  // 고 함유 기준 확인
  if (EMPHASIS_CRITERIA.high[key] && value >= EMPHASIS_CRITERIA.high[key].threshold) {
    emphasis.push({
      type: 'high',
      label: EMPHASIS_CRITERIA.high[key].label,
      threshold: EMPHASIS_CRITERIA.high[key].threshold
    });
  }
  
  return emphasis.length > 0 ? emphasis : null;
}

// 영양성분 값 처리 함수 (식품등의 표시기준 개선)
function processNutritionValue(key, value) {
  if (!value || value === 0) return '0';
  
  const roundedValue = parseFloat(value);
  if (isNaN(roundedValue)) return '0';
  
  switch (key) {
    case 'calories':
      if (roundedValue < 5) return '5kcal 미만';
      return formatNumberWithCommas(Math.round(roundedValue / 5) * 5); // 5kcal 단위
    case 'natriums':
    case 'sodium':
      if (roundedValue < 5) return '5mg 미만';
      if (roundedValue >= 1000) {
        const sodiumLargeResult = Math.round(roundedValue / 1000) * 1000;
        return formatNumberWithCommas(sodiumLargeResult);
      } else {
        const sodiumResult = Math.round(roundedValue / 5) * 5;
        return formatNumberWithCommas(sodiumResult);
      }
    case 'cholesterols':
    case 'cholesterol':
      if (roundedValue < 2) return '0';
      if (roundedValue < 5) return '5mg 미만';
      const cholesterolResult = Math.round(roundedValue / 5) * 5;
      return formatNumberWithCommas(cholesterolResult);
    case 'calcium':
    case 'iron':
    case 'potassium':
    case 'magnesium':
    case 'phosphorus':
    case 'zinc':
    case 'selenium':
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'carbohydrates':
    case 'carbohydrate':
    case 'proteins':
    case 'protein':
    case 'dietary_fiber':
      if (roundedValue < 1) return '1g 미만';
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'sugars': // 당류는 '미만' 표시 없음
      if (roundedValue < 0.5) return '0';
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'fats':
    case 'fat':
    case 'saturated_fats':
    case 'saturated_fat':
      if (roundedValue < 0.5) return '0';
      if (roundedValue <= 5) {
        const fatResult = Math.round(roundedValue * 10) / 10;
        return formatNumberWithCommas(fatResult);
      }
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'trans_fats':
    case 'trans_fat':
      if (roundedValue < 0.2) return '0';
      if (roundedValue < 0.5) return '0.5g 미만';
      const transResult = Math.round(roundedValue * 10) / 10;
      return formatNumberWithCommas(transResult);
    default:
      if (roundedValue < 0.1) return '0';
      const defaultResult = Math.round(roundedValue * 10) / 10;
      return formatNumberWithCommas(defaultResult);
  }
}

// % 영양성분 기준치 계산 함수 (가이드라인 준수)
function calculateDailyValuePercent(key, processedValue, originalValue) {
  const nutritionInfo = NUTRITION_DATA[key];
  if (key === 'calories' || key === 'trans_fats' || !nutritionInfo.daily_value) return null;

  let valueForCalc = originalValue;
  if (typeof processedValue === 'string' && processedValue.includes('미만')) {
    // "미만" 표시일 경우, 계산은 실제 값을 사용
    valueForCalc = originalValue;
  } else {
    // "미만"이 아닐 경우, 표시된 값(숫자)을 사용
    const cleanedValue = typeof processedValue === 'string' ? 
      processedValue.replace(/,/g, '') : processedValue;
    valueForCalc = parseFloat(cleanedValue);
  }
  
  if (isNaN(valueForCalc)) return '0';

  const percent = (valueForCalc / nutritionInfo.daily_value) * 100;
  
  // 식약처 기준: 1% 미만은 "1% 미만"으로 표시
  if (percent < 1) return '1% 미만';
  
  const roundedPercent = Math.round(percent);
  return formatNumberWithCommas(roundedPercent);
}

// ===== 데이터 수집 헬퍼 함수 =====
/**
 * @description DOM에서 현재 입력된 모든 영양성분 값을 읽어 객체로 반환합니다.
 * @returns {Object} 영양성분 키와 숫자 값으로 구성된 객체
 */
function getNutritionInputsFromDOM() {
  const nutritionInputs = {};
  Object.keys(NUTRITION_DATA).forEach(key => {
    const input = document.getElementById(key);
    if (input && input.value && input.value.trim() !== '') {
      // 소수점 포함 숫자로 변환
      const numericValue = parseFloat(input.value);
      if (!isNaN(numericValue) && numericValue >= 0) {
        // 소수점 2자리까지 반올림
        nutritionInputs[key] = Math.round(numericValue * 100) / 100;
      }
    }
  });
  return nutritionInputs;
}

// ===== 메인 기능 함수들 =====

// 영양성분 입력 폼 빌드
function buildInputForm() {
  const basicContainer = document.getElementById('basic-nutrient-inputs');
  const additionalContainer = document.getElementById('additional-nutrient-inputs');
  
  if (!basicContainer || !additionalContainer) return;
  
  basicContainer.innerHTML = '';
  additionalContainer.innerHTML = '';
  
  // 기본 영양성분 (필수)
  Object.entries(NUTRITION_DATA)
    .filter(([key, data]) => data.required)
    .sort((a, b) => a[1].order - b[1].order)
    .forEach(([key, data]) => {
      const div = document.createElement('div');
      div.className = 'nutrient-input-group';
      div.innerHTML = `
        <label for="${key}" class="${data.indent ? 'indent' : ''}">${data.label}</label>
        <input type="number" id="${key}" name="${key}" placeholder="0" step="0.01" min="0" data-nutrition-key="${key}">
        <span class="unit-label">${data.unit}</span>
      `;
      basicContainer.appendChild(div);
    });
    
  // 추가 영양성분 (선택)
  Object.entries(NUTRITION_DATA)
    .filter(([key, data]) => !data.required)
    .sort((a, b) => a[1].order - b[1].order)
    .forEach(([key, data]) => {
      const div = document.createElement('div');
      div.className = 'nutrient-input-group';
      div.innerHTML = `
        <label for="${key}">${data.label}</label>
        <input type="number" id="${key}" name="${key}" placeholder="0" step="0.01" min="0" data-nutrition-key="${key}">
        <span class="unit-label">${data.unit}</span>
      `;
      additionalContainer.appendChild(div);
    });
    
  // 모든 영양성분 입력 필드에 3자리 쉼표 이벤트 리스너 추가
  attachCommaFormattingToInputs();
}

// 3자리 쉼표 포맷팅 기능 추가
function attachCommaFormattingToInputs() {
  // 모든 영양성분 입력 필드 선택
  const nutritionInputs = document.querySelectorAll('input[data-nutrition-key]');
  
  nutritionInputs.forEach(input => {
    // input 이벤트로 실시간 검증 (소수점 2자리까지 허용)
    input.addEventListener('input', function(e) {
      let value = e.target.value;
      
      // 숫자와 소수점만 허용
      value = value.replace(/[^\d.]/g, '');
      
      // 소수점이 여러 개 입력된 경우 처리
      const parts = value.split('.');
      if (parts.length > 2) {
        value = parts[0] + '.' + parts.slice(1).join('');
      }
      
      // 소수점 두 번째 자리까지만 허용
      if (parts.length === 2 && parts[1].length > 2) {
        value = parts[0] + '.' + parts[1].substring(0, 2);
      }
      
      e.target.value = value;
    });
    
    // blur 이벤트에서 소수점 검증 및 포매팅
    input.addEventListener('blur', function(e) {
      let value = e.target.value;
      if (value && value !== '') {
        const numericValue = parseFloat(value);
        if (!isNaN(numericValue) && numericValue >= 0) {
          // 소수점 2자리까지 반올림
          e.target.value = Math.round(numericValue * 100) / 100;
        } else {
          e.target.value = '';
        }
      }
    });
  });
}

// 강조표시 검증 결과 표시 함수
function displayEmphasisValidation(nutritionInputs) {
  const emphasisContainer = document.getElementById('emphasisValidationResults');
  const emphasisContent = document.getElementById('emphasisValidationContent');
  
  // 강조표시 검증 결과 수집 - 가능한 항목만 필터링
  const validationResults = [];
  
  Object.entries(nutritionInputs).forEach(([key, value]) => {
    const nutritionInfo = NUTRITION_DATA[key];
    if (nutritionInfo) {
      const emphasisResult = checkEmphasisEligibility(key, value);
      
      // 강조표시가 가능한 항목만 추가
      if (emphasisResult && emphasisResult.length > 0) {
        validationResults.push({
          key: key,
          label: nutritionInfo.label,
          value: value,
          unit: nutritionInfo.unit,
          emphasisResult: emphasisResult
        });
      }
    }
  });
  
  if (validationResults.length === 0) {
    emphasisContainer.style.display = 'none';
    return;
  }
  
  // HTML 생성 - 가능한 항목만 표시
  let html = '';
  
  validationResults.forEach(result => {
    html += `<div class="emphasis-item emphasis-eligible">`;
    html += `<div class="emphasis-nutrient-name">${result.label} (${result.value}${result.unit})</div>`;
    
    html += '<div class="emphasis-labels">';
    result.emphasisResult.forEach(emphasis => {
      html += `<span class="emphasis-badge ${emphasis.type}">${emphasis.label}</span>`;
      html += `<span class="emphasis-threshold">${emphasis.threshold}${result.unit} ${emphasis.type === 'free' ? '미만' : emphasis.type === 'low' ? '이하' : '이상'}</span>`;
    });
    html += '</div>';
    
    html += '</div>';
  });
  
  emphasisContent.innerHTML = html;
  emphasisContainer.style.display = 'block';
}

// 영양성분 계산 메인 함수
function calculateNutrition() {
  const baseAmount = parseFloat(document.getElementById('serving_size').value) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('units_per_package').value) || 1;
  const style = document.getElementById('nutrition_display_unit').value;
  
  // [개선] DOM에서 최신 영양성분 입력값 수집
  const nutritionInputs = getNutritionInputsFromDOM();
  
  if (Object.keys(nutritionInputs).length === 0) {
    document.getElementById('resultDisplay').innerHTML = '<div class="empty-result">영양성분을 입력해주세요.</div>';
    document.getElementById('emphasisValidationResults').style.display = 'none';
    return;
  }
  
  // 강조표시 검증 결과 표시
  displayEmphasisValidation(nutritionInputs);
  
  let displayHTML = '';
  
  if (style === 'parallel') {
    displayHTML = generateParallelDisplayV3(nutritionInputs, baseAmount, servingsPerPackage);
  } else {
    displayHTML = generateBasicDisplayV3(nutritionInputs, baseAmount, servingsPerPackage);
  }
  
  document.getElementById('resultDisplay').innerHTML = displayHTML;
  
  // 마지막 계산 결과 저장
  currentNutritionData = nutritionInputs;
}

// 폼 초기화
function resetFormAndParent() {
  if (confirm('모든 입력 내용을 초기화하시겠습니까?')) {
    currentNutritionData = {};
    
    // 모든 영양성분 입력 초기화
    Object.keys(NUTRITION_DATA).forEach(key => {
      const input = document.getElementById(key);
      if (input) input.value = '';
    });
    
    // 기본값 설정
    document.getElementById('serving_size').value = '100';
    document.getElementById('units_per_package').value = '1';
    document.getElementById('nutrition_display_unit').value = 'basic';
    document.getElementById('basic_display_type').value = 'total';
    document.getElementById('parallel_display_type').value = 'unit_total';
    
    // 결과 초기화
    document.getElementById('resultDisplay').innerHTML = '<div class="empty-result">영양성분을 입력하고 계산 버튼을 눌러주세요.</div>';
    document.getElementById('emphasisValidationResults').style.display = 'none';
    
    // 부모 창에 초기화 알림
    if (window.opener && typeof window.opener.postMessage === 'function') {
      window.opener.postMessage({ type: 'nutritionReset' }, '*');
    }
  }
}

// [개선] 데이터를 부모 창으로 전송
function sendNutritionDataToParent() {
  // [수정] DOM에서 직접 최신 데이터를 가져옴
  const nutritionDataToSave = getNutritionInputsFromDOM();

  if (Object.keys(nutritionDataToSave).length === 0) {
    alert('저장할 영양성분 데이터가 없습니다. 값을 입력해주세요.');
    return;
  }

  const baseAmount = parseFloat(document.getElementById('serving_size').value) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('units_per_package').value) || 1;
  const style = document.getElementById('nutrition_display_unit').value;
  const basicDisplayType = document.getElementById('basic_display_type')?.value || 'per_100g';
  const parallelDisplayType = document.getElementById('parallel_display_type')?.value || 'per_serving';

  // 입력된 영양성분만 전달 (빈 값 제외)
  const formattedData = {};
  Object.keys(nutritionDataToSave).forEach(key => {
    const nutritionInfo = NUTRITION_DATA[key];
    if (nutritionInfo && nutritionDataToSave[key] !== '' && nutritionDataToSave[key] != null) {
      formattedData[key] = {
        label: nutritionInfo.label,
        value: nutritionDataToSave[key],
        unit: nutritionInfo.unit
      };
    }
  });

  const dataToSend = {
    type: 'nutritionData',
    data: {
      nutritionInputs: formattedData,
      settings: {
        serving_size: baseAmount,
        units_per_package: servingsPerPackage,
        nutrition_display_unit: style,
        basic_display_type: basicDisplayType,
        parallel_display_type: parallelDisplayType
      },
      html: document.getElementById('resultDisplay').innerHTML
    }
  };

  // 계산기에서 전송할 데이터 정보 (디버그 로그 제거)

  if (window.opener && typeof window.opener.postMessage === 'function') {
    window.opener.postMessage(dataToSend, '*');
    alert('영양성분 데이터가 저장되었습니다.');
  } else {
    alert('데이터 저장에 실패했습니다. 부모 창을 찾을 수 없습니다.');
  }
}

// PDF 내보내기
function exportToPDF() {
  const nutritionContainer = document.querySelector('#resultDisplay .nutrition-result-table, #resultDisplay .nutrition-style-basic, #resultDisplay .nutrition-style-parallel');
  
  if (!nutritionContainer) {
    alert('먼저 영양성분을 계산해주세요.');
    return;
  }
  
  const pdfButton = document.querySelector('button[onclick="exportToPDF()"]');
  const originalText = pdfButton.innerHTML;
  pdfButton.disabled = true;
  pdfButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>PDF 생성 중...';
  
  setTimeout(() => {
    html2canvas(nutritionContainer, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
      allowTaint: false,
      foreignObjectRendering: false,
      width: nutritionContainer.offsetWidth,
      height: nutritionContainer.offsetHeight,
      scrollX: 0,
      scrollY: 0
    }).then(canvas => {
      try {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4'
        });
        
        const imgWidth = 190;
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        const imgData = canvas.toDataURL('image/png', 1.0);
        
        pdf.addImage(imgData, 'PNG', 10, 10, imgWidth, imgHeight);
        
        const now = new Date();
        const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
        const styleText = document.getElementById('nutrition_display_unit').value === 'basic' ? '기본형' : '병행표시';
        // 제품명 가져오기 (우선순위: label_name -> prdlst_nm)
        let productName = '';
        // 1. label_name (부모창에서 전달된 경우)
        if (window.opener && window.opener.document) {
          const labelNameInput = window.opener.document.getElementById('my_label_name_top') || window.opener.document.getElementById('my_label_name_hidden');
          if (labelNameInput && labelNameInput.value) {
            productName = labelNameInput.value.trim();
          }
        }
        // 2. nutrition calculator 내에서 입력된 제품명 (있다면)
        if (!productName) {
          const prdlstNmInput = document.getElementById('prdlst_nm');
          if (prdlstNmInput && prdlstNmInput.value) {
            productName = prdlstNmInput.value.trim();
          }
        }
        // 파일명에 제품명 포함 (공백, 특수문자 제거)
        if (productName) {
          productName = productName.replace(/\s+/g, '_').replace(/[^\w가-힣_]/g, '');
        } else {
          productName = '제품명없음';
        }
  const fileName = `영양성분표(${styleText})_${productName}_${dateStr}`;
        pdf.save(`${fileName}.pdf`);
        alert('PDF가 성공적으로 저장되었습니다.');
        
      } catch (error) {

        alert('PDF 생성 중 오류가 발생했습니다: ' + error.message);
      } finally {
        pdfButton.disabled = false;
        pdfButton.innerHTML = originalText;
      }
    }).catch(error => {

      alert('이미지 변환 중 오류가 발생했습니다: ' + error.message);
      pdfButton.disabled = false;
      pdfButton.innerHTML = originalText;
    });
  }, 100);
}

// 기존 데이터 로드 (DOM 준비 후 호출)
// 데이터 로드 중복 실행 방지 플래그
let isLoadingData = false;

function loadExistingData(data) {
  try {
  // 데이터 로딩 시작 (디버그 로그 제거)
    if (!data || typeof data !== 'object') return;
    
    // 중복 실행 방지 - 단, 부모창 데이터는 우선 처리
    const hasParentData = data.calories !== undefined || data.natriums !== undefined || data.carbohydrates !== undefined || data.fats !== undefined;
    
    if (isLoadingData && !hasParentData) {
      return;
    }
    
    if (hasParentData) {
      isLoadingData = false; // 부모창 데이터는 항상 처리하도록 플래그 리셋 
      
      // 중첩 구조 데이터가 있어도 부모창 데이터로 덮어쓰기
      if (data.nutrients) {
        delete data.nutrients; // 중첩 구조 데이터 제거하여 부모창 데이터만 사용
      }
    }
    
    isLoadingData = true;
    
    // DOM이 준비될 때까지 대기 후 실행
    const waitForDOM = () => {
      const basicContainer = document.getElementById('basic-nutrient-inputs');
      const additionalContainer = document.getElementById('additional-nutrient-inputs');
      const allNutritionInputs = document.querySelectorAll('input[data-nutrition-key]');
      
      // DOM이 준비되지 않았으면 다시 시도
      if (!basicContainer || !additionalContainer || allNutritionInputs.length === 0) {
        setTimeout(waitForDOM, 100);
        return;
      }
      
      // DOM이 준비되면 데이터 로드 실행
      executeDataLoad();
    };
    
    const executeDataLoad = () => {
    
    // 기본 설정값 로드
    if (data.baseAmount || data.nutrition_base_amount || data.serving_size) {
      const baseValue = data.baseAmount || data.nutrition_base_amount || data.serving_size;
      document.getElementById('serving_size').value = baseValue;
    }
    
    if (data.servingsPerPackage || data.units_per_package) {
      const servingValue = data.servingsPerPackage || data.units_per_package;
      document.getElementById('units_per_package').value = servingValue;
    }
    
    if (data.style || data.nutrition_display_unit) {
      const styleValue = data.style || data.nutrition_display_unit;
      document.getElementById('nutrition_display_unit').value = styleValue;
      // 스타일 변경 후 옵션 표시 업데이트
      if (typeof window.toggleStyleOptions === 'function') {
        window.toggleStyleOptions();
      }
    }
    
    // 표시기준 로드
    if (data.basic_display_type) {
      const basicDisplayElement = document.getElementById('basic_display_type');
      if (basicDisplayElement) {
        basicDisplayElement.value = data.basic_display_type;
      }
    }
    
    if (data.parallel_display_type) {
      const parallelDisplayElement = document.getElementById('parallel_display_type');
      if (parallelDisplayElement) {
        parallelDisplayElement.value = data.parallel_display_type;
      }
    }
    
    // 영양성분 데이터 로드 - 부모창에서 전달받는 형식에 맞게 수정
    let hasAdditionalValue = false;
    
    // 부모창 필드명과 팝업 필드명 매핑 (복수형으로 통일)
    const fieldMapping = {
      'calories': 'calories',
      'calorie': 'calories',
      'kcal': 'calories',
      'natriums': 'natriums',
      'sodium': 'natriums',
      'na': 'natriums',
      'carbohydrates': 'carbohydrates',
      'carbohydrate': 'carbohydrates',
      'carbs': 'carbohydrates',
      'sugars': 'sugars',
      'sugar': 'sugars',
      'fats': 'fats',
      'fat': 'fats',
      'total_fat': 'fats',
      'trans_fats': 'trans_fats',
      'trans_fat': 'trans_fats',
      'transfat': 'trans_fats',
      'saturated_fats': 'saturated_fats',
      'saturated_fat': 'saturated_fats',
      'sat_fat': 'saturated_fats',
      'cholesterols': 'cholesterols',
      'cholesterol': 'cholesterols',
      'proteins': 'proteins',
      'protein': 'proteins',
      // 추가 영양성분 매핑
      'dietary_fiber': 'dietary_fiber',
      'fiber': 'dietary_fiber',
      'calcium': 'calcium',
      'ca': 'calcium',
      'iron': 'iron',
      'fe': 'iron',
      'potassium': 'potassium',
      'k': 'potassium',
      'magnesium': 'magnesium',
      'mg': 'magnesium',
      'zinc': 'zinc',
      'zn': 'zinc',
      'phosphorus': 'phosphorus',
      'p': 'phosphorus',
      'vitamin_a': 'vitamin_a',
      'vitaminA': 'vitamin_a',
      'vit_a': 'vitamin_a',
      'vitamin_d': 'vitamin_d',
      'vitaminD': 'vitamin_d',
      'vit_d': 'vitamin_d',
      'vitamin_e': 'vitamin_e',
      'vitaminE': 'vitamin_e',
      'vit_e': 'vitamin_e',
      'vitamin_c': 'vitamin_c',
      'vitaminC': 'vitamin_c',
      'vit_c': 'vitamin_c',
      'thiamine': 'thiamine',
      'thiamin': 'thiamine',
      'vitamin_b1': 'thiamine',
      'riboflavin': 'riboflavin',
      'vitamin_b2': 'riboflavin',
      'niacin': 'niacin',
      'vitamin_b3': 'niacin',
      'vitamin_b6': 'vitamin_b6',
      'vitaminB6': 'vitamin_b6',
      'vit_b6': 'vitamin_b6',
      'folic_acid': 'folic_acid',
      'folate': 'folic_acid',
      'vitamin_b9': 'folic_acid',
      'vit_b9': 'folic_acid',
      'vitamin_b12': 'vitamin_b12',
      'vitaminB12': 'vitamin_b12',
      'vit_b12': 'vitamin_b12',
      'selenium': 'selenium',
      'se': 'selenium',
      
      // 추가 영양성분들
      'pantothenic_acid': 'pantothenic_acid',
      'pantothen': 'pantothenic_acid',
      'biotin': 'biotin',
      'vitamin_b7': 'biotin',
      'iodine': 'iodine',
      'i': 'iodine',
      'vitamin_k': 'vitamin_k',
      'vitaminK': 'vitamin_k',
      'vit_k': 'vitamin_k',
      'copper': 'copper',
      'cu': 'copper',
      'manganese': 'manganese',
      'mn': 'manganese',
      'chromium': 'chromium',
      'cr': 'chromium',
      'molybdenum': 'molybdenum',
      'mo': 'molybdenum'
    };
    
    // 세 가지 데이터 형식 지원 - 우선순위에 따라 처리
    // 1. 중첩 구조 형식이 있으면 우선 처리 (nutrients.calories.value)
    if (data.nutrients) {
      Object.keys(data.nutrients).forEach(key => {
        // 필드명은 이제 복수형으로 통일되어 직접 사용
        const popupFieldName = key;
        const input = document.getElementById(popupFieldName);
        const nutrientData = data.nutrients[key];
        
        if (input && nutrientData && nutrientData.value && nutrientData.value !== '' && nutrientData.value !== '0') {
          const value = nutrientData.value;
          const numValue = parseFloat(value);
          
          if (!isNaN(numValue)) {
            const formattedValue = numValue.toLocaleString('ko-KR');
            input.value = formattedValue;
            
            // 이벤트 발생시켜 리액트/뷰 등의 프레임워크 대응
            const inputEvent = new Event('input', { bubbles: true });
            input.dispatchEvent(inputEvent);
            
            const changeEvent = new Event('change', { bubbles: true });
            input.dispatchEvent(changeEvent);
            
            if (NUTRITION_DATA[popupFieldName] && !NUTRITION_DATA[popupFieldName].required) {
              hasAdditionalValue = true;
            }
          }
        } else if (input) {
          input.value = '';
        }
      });
    } 
    // 2. 부모창에서 전달받는 평면 구조 형식 (collectExistingNutritionData에서 수집)
    else if (data.calories !== undefined || data.sodium !== undefined || data.carbohydrate !== undefined || data.fat !== undefined) {
      
      Object.keys(fieldMapping).forEach(parentFieldName => {
        const popupFieldName = fieldMapping[parentFieldName];
        const input = document.getElementById(popupFieldName);
        
        if (input && data[parentFieldName] !== undefined && data[parentFieldName] !== null && data[parentFieldName] !== '' && data[parentFieldName] !== '0') {
          const value = data[parentFieldName];
          
          // 문자열에서 숫자만 추출 (쉼표 제거)
          const cleanValue = String(value).replace(/,/g, '');
          const numValue = parseFloat(cleanValue);
          
          if (!isNaN(numValue)) {
            const formattedValue = numValue.toLocaleString('ko-KR');
            
            try {
              // 직접 값 설정
              input.value = formattedValue;
              
              // 이벤트 발생시켜 리액트/뷰 등의 프레임워크 대응
              const inputEvent = new Event('input', { bubbles: true });
              input.dispatchEvent(inputEvent);
              
              const changeEvent = new Event('change', { bubbles: true });
              input.dispatchEvent(changeEvent);
              
            } catch (setError) {
            }
            
            // 추가 영양성분에 값이 있으면 펼침
            if (NUTRITION_DATA[popupFieldName] && !NUTRITION_DATA[popupFieldName].required) {
              hasAdditionalValue = true;
            }
          }
        } else {
          // 부모창 데이터가 비어있는 경우, 기존 값이 있다면 유지 (덮어쓰지 않음)
          if (input && input.value && input.value.trim() !== '') {
            // 기존에 값이 있는 추가 영양성분이면 섹션 펼침
            if (NUTRITION_DATA[popupFieldName] && !NUTRITION_DATA[popupFieldName].required) {
              hasAdditionalValue = true;
            }
          }
        }
      });
      
    } 
    // 3. 팝업 내부에서 생성된 데이터 구조 (nutritionInputs)
    else if (data.nutritionInputs) {
      Object.keys(NUTRITION_DATA).forEach(key => {
        const input = document.getElementById(key);
        const item = data.nutritionInputs[key];
        let valueToSet = '';
        if (input && item && item.value !== undefined && item.value !== null && item.value !== '') {
          const numValue = parseFloat(item.value);
          if (!isNaN(numValue) && numValue !== 0) {
            valueToSet = numValue.toLocaleString('ko-KR');
            if (!NUTRITION_DATA[key].required) {
              hasAdditionalValue = true;
            }
          }
          input.value = valueToSet;
        } else if (input) {
          input.value = '';
        }
      });
    } else {
      // 부모창에서 전달받는 형식 (collectExistingNutritionData에서 수집)
      Object.keys(fieldMapping).forEach(parentFieldName => {
        const popupFieldName = fieldMapping[parentFieldName];
        const input = document.getElementById(popupFieldName);
        
        if (input && data[parentFieldName] !== undefined && data[parentFieldName] !== null && data[parentFieldName] !== '' && data[parentFieldName] !== '0') {
          const value = data[parentFieldName];
          
          // 문자열에서 숫자만 추출 (쉼표 제거)
          const cleanValue = String(value).replace(/,/g, '');
          const numValue = parseFloat(cleanValue);
          
          if (!isNaN(numValue)) {
            const formattedValue = numValue.toLocaleString('ko-KR');
            // 다양한 방법으로 값 설정 시도
            try {
              // 방법 1: 직접 설정
              input.value = formattedValue;
              
              // 방법 2: setAttribute 사용
              input.setAttribute('value', formattedValue);
              
              // 방법 3: 이벤트 발생시켜 리액트/뷰 등의 프레임워크 대응
              const inputEvent = new Event('input', { bubbles: true });
              input.dispatchEvent(inputEvent);
              
              const changeEvent = new Event('change', { bubbles: true });
              input.dispatchEvent(changeEvent);
              
            } catch (setError) {
            }
            
            // 값이 실제로 설정되었는지 확인
            setTimeout(() => {
              const actualValue = document.getElementById(popupFieldName)?.value;
              
              // 만약 여전히 값이 설정되지 않았다면 추가 시도
              if (!actualValue || actualValue === '') {
                const retryInput = document.getElementById(popupFieldName);
                if (retryInput) {
                  retryInput.value = formattedValue;
                  retryInput.setAttribute('value', formattedValue);
                }
              }
            }, 100);
            
            // 추가 영양성분에 값이 있으면 펼침
            if (NUTRITION_DATA[popupFieldName] && !NUTRITION_DATA[popupFieldName].required) {
              hasAdditionalValue = true;
            }
          } else {
            input.value = '';
          }
        } else {
          if (!input) {


          }
          if (input) {
            input.value = '';
          }
        }
      });
    }
    // 값이 있는 추가 영양성분이 있으면 자동으로 펼침
    const additionalSection = document.getElementById('additional-nutrients');
    const toggleIcon = document.getElementById('nutrition-toggle');
    const toggleText = document.getElementById('nutrition-toggle-text');
    
    if (hasAdditionalValue && additionalSection) {
      // 강제로 펼치기 (display 상태에 관계없이)
      additionalSection.style.display = 'block';
      
      if (toggleIcon) {
        toggleIcon.textContent = '▲';
        toggleIcon.classList.add('rotated');
      }
      if (toggleText) {
        toggleText.textContent = '성분 접기';
      }
    }
    // 자동 계산 제거 - 계산 버튼을 눌렀을 때만 계산
    // 스타일 옵션만 설정
    setTimeout(() => {
      if (typeof window.toggleStyleOptions === 'function') {
        window.toggleStyleOptions();
      }
    }, 100);
    };
    
    // DOM 대기 시작
    waitForDOM();
    
  } catch (error) {

  } finally {
    // 3초 후 플래그 해제 (DOM 로드 및 처리 완료 대기)
    setTimeout(() => {
      isLoadingData = false;
    }, 3000);
  }
}

// ===== 이벤트 핸들러들 =====

// 스타일 옵션 토글
window.toggleStyleOptions = function() {
  const style = document.getElementById('nutrition_display_unit').value;
  const basicVerticalOptions = document.getElementById('basic-vertical-options');
  const parallelOptions = document.getElementById('parallel-options');
  
  if (style === 'parallel') {
    basicVerticalOptions.classList.remove('show');
    parallelOptions.classList.add('show');
  } else {
    basicVerticalOptions.classList.add('show');
    parallelOptions.classList.remove('show');
  }
  
  // 스타일 변경 시 자동 계산 (영양성분 데이터가 있는 경우에만)
  const baseAmount = document.getElementById('serving_size').value;
  const servingsPerPackage = document.getElementById('units_per_package').value;
  
  // 자동 계산 제거 - 계산 버튼을 눌렀을 때만 계산
  // 영양성분 입력값 확인은 하지만 자동 계산은 하지 않음
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

// 페이지 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
  buildInputForm();
  
  // buildInputForm이 완료될 때까지 충분히 기다린 후 데이터 로드
  setTimeout(() => {
    
    // DOM 요소가 실제로 생성되었는지 여러 번 확인
    const waitForFormReady = () => {
      const testFields = [
        document.getElementById('calories'),
        document.getElementById('sodium'), 
        document.getElementById('carbohydrate')
      ];
      
      const allFieldsReady = testFields.every(field => field !== null);
      
      if (allFieldsReady) {
        loadDataAfterFormReady();
      } else {
        setTimeout(waitForFormReady, 100);
      }
    };
    
    waitForFormReady();
  }, 200);

  // 입력 패널 숫자 입력에 쉼표 자동 추가 기능
  setTimeout(() => {
    const inputPanel = document.querySelector('.input-panel');
    if (inputPanel) {
      inputPanel.addEventListener('input', function(e) {
        if (e.target.type === 'number' || e.target.classList.contains('ratio-input')) {
          const value = e.target.value.replace(/,/g, '');
          if (!isNaN(value) && value.length > 0) {
            const formattedValue = Number(value).toLocaleString('ko-KR');
            // 커서 위치 유지를 위해 현재 값과 다를 때만 업데이트
            if (e.target.value !== formattedValue) {
                e.target.value = formattedValue;
            }
          }
        }
      });
    }
  }, 400);

  // 커스텀 이벤트 발생
  const event = new CustomEvent('nutrition-calculator-ready');
  document.dispatchEvent(event);
});

// 입력 폼 준비 완료 후 데이터 로드 함수
let loadDataAfterFormReadyExecuted = false;
function loadDataAfterFormReady() {
  // 중복 실행 방지
  if (loadDataAfterFormReadyExecuted) {
    return;
  }
  loadDataAfterFormReadyExecuted = true;
  
  if (window.opener && !window.opener.closed) {
    
    try {
      const parentData = window.opener.getNutritionDataForPopup();
      
      if (parentData && Object.keys(parentData).length > 0) {
        loadExistingData(parentData);
      } else {
        loadDataFromUrlParams();
      }
    } catch (e) {

      loadDataFromUrlParams();
    }
  } else {
    loadDataFromUrlParams();
  }
}

// URL 파라미터에서 데이터 로드
function loadDataFromUrlParams() {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const data = {};
    
    // 기본 설정값 로드
    if (urlParams.get('nutrition_base_amount')) {
      data.baseAmount = parseFloat(urlParams.get('nutrition_base_amount'));
    } else if (urlParams.get('serving_size')) {
      data.baseAmount = parseFloat(urlParams.get('serving_size'));
    }
    
    if (urlParams.get('units_per_package')) {
      data.servingsPerPackage = parseFloat(urlParams.get('units_per_package'));
    }
    
    if (urlParams.get('nutrition_display_unit')) {
      data.style = urlParams.get('nutrition_display_unit');
    }
    
    // 영양성분 데이터 로드
    const nutritionInputs = {};
    
    // 필드명 매핑 (URL 파라미터 -> NUTRITION_DATA 키)
    const fieldMapping = {
      'calories': 'calories',
      'natriums': 'sodium',
      'carbohydrates': 'carbohydrate', 
      'sugars': 'sugars',
      'fats': 'fat',
      'trans_fats': 'trans_fat',
      'saturated_fats': 'saturated_fat',
      'cholesterols': 'cholesterol',
      'proteins': 'protein',
      // 추가 영양성분 매핑
      'dietary_fiber': 'dietary_fiber',
      'calcium': 'calcium',
      'iron': 'iron',
      'potassium': 'potassium',
      'magnesium': 'magnesium',
      'zinc': 'zinc',
      'phosphorus': 'phosphorus',
      'vitamin_a': 'vitamin_a',
      'vitamin_d': 'vitamin_d',
      'vitamin_e': 'vitamin_e',
      'vitamin_c': 'vitamin_c',
      'thiamine': 'thiamine',
      'riboflavin': 'riboflavin',
      'niacin': 'niacin',
      'vitamin_b6': 'vitamin_b6',
      'folic_acid': 'folic_acid',
      'vitamin_b12': 'vitamin_b12',
      'selenium': 'selenium',
      // 추가 영양성분들
      'pantothenic_acid': 'pantothenic_acid',
      'biotin': 'biotin',
      'iodine': 'iodine',
      'vitamin_k': 'vitamin_k',
      'copper': 'copper',
      'manganese': 'manganese',
      'chromium': 'chromium',
      'molybdenum': 'molybdenum'
    };
    
    Object.entries(fieldMapping).forEach(([urlKey, dataKey]) => {
      const value = urlParams.get(urlKey);
      if (value && value.trim() !== '') {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
          nutritionInputs[dataKey] = { value: numValue };
        }
      }
    });
    
    if (Object.keys(nutritionInputs).length > 0) {
      data.nutritionInputs = nutritionInputs;
    }
    
    // 데이터가 있으면 로드
    if (Object.keys(data).length > 0) {
      loadExistingData(data);
    }
    
  } catch (error) {

  }
}

// ===== V3 영양성분표 생성 함수들 =====

// V3 기본형 영양정보표 생성
function generateBasicDisplayV3(nutritionInputs, baseAmount, servingsPerPackage) {
  
  console.log('generateBasicDisplayV3 호출됨:', nutritionInputs, baseAmount, servingsPerPackage);
  
  // 표시 기준 확인
  const displayType = document.getElementById('basic_display_type')?.value || 'total';
  let displayAmount, multiplier;
  
  // 단위 확인 (g 또는 ml)
  const baseUnit = document.getElementById('serving_size_unit')?.value || 'g';
  
  switch (displayType) {
    case 'unit':
      displayAmount = baseAmount;
      multiplier = baseAmount / 100;
      break;
    case '100g':
      displayAmount = 100;
      multiplier = 1;
      break;
    case 'total':
    default:
      displayAmount = (baseAmount * servingsPerPackage);
      multiplier = displayAmount / 100;
      break;
  }
  
  const calories = window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier);

  // V3 요구사항에 맞춘 기본형 HTML 구조
  let html = '<div class="nutrition-facts-container">';
  html += '<div class="nutrition-style-basic">';
  
  // 1.2. 표 머리글 (Header) - 검은색 배경
  html += '<div class="nutrition-header">';
  html += '<div class="nutrition-title">영양정보</div>';
  html += '<div class="nutrition-subtitle">';
  html += '<div class="nutrition-total-amount">총 내용량 ' + displayAmount.toLocaleString() + baseUnit + '</div>';
  html += '<div class="nutrition-calories">' + calories + 'kcal</div>';
  html += '</div>';
  html += '</div>';
  
  html += '<table class="nutrition-table">';
  html += '<thead>';
  html += '<tr>';
  
  // 표시기준 텍스트 생성
  let displayTypeText = '';
  switch (displayType) {
    case 'unit':
      displayTypeText = '단위내용량당';
      break;
    case '100g':
      displayTypeText = '100' + baseUnit + '당';
      break;
    case 'total':
    default:
      displayTypeText = '총내용량당';
      break;
  }
  
  html += '<th>' + displayTypeText + '</th>';
  html += '<th>1일 영양성분<br>기준치에 대한 비율</th>';
  html += '</tr>';
  html += '</thead>';
  html += '<tbody>';

  // 본문(영양성분) HTML - 가이드라인 순서 준수
  const sortedNutrients = Object.entries(window.NUTRITION_DATA)
      .filter(function(item) {
        const key = item[0];
        if (key === 'calories') return false; // 열량은 헤더에 이미 표시
        return window.NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined;
      })
      .sort(function(a, b) {
        return a[1].order - b[1].order;
      });

  sortedNutrients.forEach(function(item, index) {
      const key = item[0];
      const data = item[1];
      
      const originalValue = (nutritionInputs[key] || 0) * multiplier;
      const processedValue = window.processNutritionValue(key, originalValue);
      const percent = window.calculateDailyValuePercent(key, processedValue, originalValue);
      
      let displayValue;
      if (processedValue.includes('미만')) {
        displayValue = processedValue;
      } else {
        const numericValue = Number(processedValue.replace(/,/g, ''));
        displayValue = numericValue.toLocaleString() + data.unit;
      }

      const percentDisplay = percent !== null ? (percent.includes('미만') ? percent : '<strong>' + percent + '</strong>%') : '';
      
      // 주요 영양성분 그룹 구분 (단백질 다음에 구분선)
      const isGroupEnd = key === 'proteins';
      const rowClass = isGroupEnd ? 'nutrition-row major-group-end' : 'nutrition-row';
      
      html += '<tr class="' + rowClass + '">';
      html += '<td class="nutrition-name-content ' + (data.indent ? 'nutrition-indent' : '') + '"><strong>' + data.label + '</strong> ' + displayValue + '</td>';
      html += '<td class="nutrition-daily">' + percentDisplay + '</td>';
      html += '</tr>';
  });

  // 1.4. 표 바닥글 (Footer)
  html += '</tbody>';
  html += '<tfoot>';
  html += '<tr class="nutrition-footer">';
  html += '<td colspan="2">* <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td>';
  html += '</tr>';
  html += '</tfoot>';
  html += '</table>';
  html += '</div>';
  html += '</div>';
  
  return html;
}

// V3 병행표시 영양정보표 생성
function generateParallelDisplayV3(nutritionInputs, baseAmount, servingsPerPackage) {
  
  // 병행표시 유형 확인
  const parallelType = document.getElementById('parallel_display_type').value;
  const totalAmount = (baseAmount * servingsPerPackage);
  
  // 단위 확인 (g 또는 ml)
  const baseUnit = document.getElementById('serving_size_unit')?.value || 'g';
  
  let multiplier1, multiplier2, headerText1, headerText2, subHeaderText1, subHeaderText2, unitText1, unitText2;
  
  switch (parallelType) {
    case 'unit_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = '총 내용량 ' + totalAmount.toLocaleString() + baseUnit + '(' + baseAmount.toLocaleString() + baseUnit + ' X ' + servingsPerPackage.toLocaleString() + ')';
      headerText2 = '1조각(' + baseAmount.toLocaleString() + baseUnit + ')당 ' + window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1) + 'kcal';
      subHeaderText1 = '1조각당';
      subHeaderText2 = '총내용량당';
      unitText1 = '조각';
      unitText2 = '총량';
      break;
      
    case 'unit_100g':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = '총 내용량 ' + totalAmount.toLocaleString() + baseUnit + '(' + baseAmount.toLocaleString() + baseUnit + ' X ' + servingsPerPackage.toLocaleString() + ')';
      headerText2 = '1조각(' + baseAmount.toLocaleString() + baseUnit + ')당 ' + window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1) + 'kcal';
      subHeaderText1 = '1조각당';
      subHeaderText2 = '100' + baseUnit + '당';
      unitText1 = '조각';
      unitText2 = '100' + baseUnit;
      break;
      
    case 'serving_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = '총 내용량 ' + totalAmount.toLocaleString() + baseUnit;
      headerText2 = '1회량(' + baseAmount.toLocaleString() + baseUnit + ')당 ' + window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1) + 'kcal';
      subHeaderText1 = '1회량당';
      subHeaderText2 = '총내용량당';
      unitText1 = '회';
      unitText2 = '총량';
      break;
      
    case 'serving_100ml':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = '총 내용량 ' + totalAmount.toLocaleString() + baseUnit;
      headerText2 = '1회량(' + baseAmount.toLocaleString() + baseUnit + ')당 ' + window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1) + 'kcal';
      subHeaderText1 = '1회량당';
      subHeaderText2 = '100ml당';
      unitText1 = '회';
      unitText2 = '100ml';
      break;
      
    default:
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = '총 내용량 ' + totalAmount.toLocaleString() + baseUnit + '(' + baseAmount.toLocaleString() + baseUnit + ' X ' + servingsPerPackage.toLocaleString() + ')';
      headerText2 = '1조각(' + baseAmount.toLocaleString() + baseUnit + ')당 ' + window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1) + 'kcal';
      subHeaderText1 = '1조각당';
      subHeaderText2 = '총내용량당';
      unitText1 = '조각';
      unitText2 = '총량';
      break;
  }
  
  const calories1 = window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1);
  const calories2 = window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier2);

  // V3 요구사항에 맞춘 병행표시 HTML 구조
  let html = '<div class="nutrition-facts-container">';
  html += '<div class="nutrition-style-parallel">';
  
  // 2.2. 표 머리글 (Header) - 검은색 배경
  html += '<div class="nutrition-header">';
  html += '<div class="nutrition-header-left">';
  html += '<div class="nutrition-title">영양정보</div>';
  html += '</div>';
  html += '<div class="nutrition-header-right">';
  html += '<div class="nutrition-subtitle">' + headerText1 + '</div>';
  html += '<div class="nutrition-calories"><strong>' + headerText2 + '</strong></div>';
  html += '</div>';
  html += '</div>';
  
  // 컬럼 헤더 구조
  html += '<table class="nutrition-table">';
  html += '<thead>';
  
  html += '<tr>';
  html += '<th class="left-section" colspan="2">';
  html += '<div class="header-flex">';
  html += '<span class="header-left">' + subHeaderText1 + '</span>';
  html += '<span class="header-right">1일 영양성분 기준치에 대한 비율</span>';
  html += '</div>';
  html += '</th>';
  html += '<th class="right-section parallel-section" colspan="2">';
  html += '<div class="header-flex">';
  html += '<span class="header-empty"></span>';
  html += '<span class="header-right">' + subHeaderText2 + '</span>';
  html += '</div>';
  html += '</th>';
  html += '</tr>';
  
  html += '</thead>';
  html += '<tbody>';

  // 본문(영양성분) HTML
  const sortedNutrients = Object.entries(window.NUTRITION_DATA)
      .filter(function(item) {
        const key = item[0];
        if (key === 'calories') return false; // 열량은 이미 처리함
        return window.NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined;
      })
      .sort(function(a, b) {
        return a[1].order - b[1].order;
      });
  
  sortedNutrients.forEach(function(item, index) {
      const key = item[0];
      const data = item[1];
      
      const originalValue1 = (nutritionInputs[key] || 0) * multiplier1;
      const processedValue1 = window.processNutritionValue(key, originalValue1);
      const percent1 = window.calculateDailyValuePercent(key, processedValue1, originalValue1);
      
      let displayValue1;
      if (processedValue1.includes('미만')) {
        displayValue1 = processedValue1;
      } else {
        const numericValue1 = Number(processedValue1.replace(/,/g, ''));
        displayValue1 = numericValue1.toLocaleString() + data.unit;
      }

      const originalValue2 = (nutritionInputs[key] || 0) * multiplier2;
      const processedValue2 = window.processNutritionValue(key, originalValue2);
      const percent2 = window.calculateDailyValuePercent(key, processedValue2, originalValue2);
      
      let displayValue2;
      if (processedValue2.includes('미만')) {
        displayValue2 = processedValue2;
      } else {
        const numericValue2 = Number(processedValue2.replace(/,/g, ''));
        displayValue2 = numericValue2.toLocaleString() + data.unit;
      }

      const percentDisplay1 = percent1 !== null ? (percent1.includes('미만') ? percent1 : '<strong>' + percent1 + '</strong>%') : '';
      const percentDisplay2 = percent2 !== null ? (percent2.includes('미만') ? percent2 : '<strong>' + percent2 + '</strong>%') : '';
      
      // 주요 영양성분 그룹 구분 (단백질 다음에 구분선)
      const isGroupEnd = key === 'proteins';
      const rowClass = isGroupEnd ? 'nutrition-row major-group-end' : 'nutrition-row';
      
      html += '<tr class="' + rowClass + '">';
      html += '<td class="nutrition-name ' + (data.indent ? 'nutrition-indent' : '') + '"><strong>' + data.label + '</strong> ' + displayValue1 + '</td>';
      html += '<td class="nutrition-daily">' + percentDisplay1 + '</td>';
      html += '<td class="nutrition-content parallel-section">' + displayValue2 + '</td>';
      html += '<td class="nutrition-daily parallel-section">' + percentDisplay2 + '</td>';
      html += '</tr>';
  });

  // 2.4. 표 바닥글 (Footer)
  html += '</tbody>';
  html += '<tfoot>';
  html += '<tr class="nutrition-footer">';
  html += '<td colspan="4">* <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td>';
  html += '</tr>';
  html += '</tfoot>';
  html += '</table>';
  html += '</div>';
  html += '</div>';
  
  return html;
}

// ===== 전역 함수로 노출 =====
// 전역 스코프에 필요한 함수들 노출
window.calculateNutrition = calculateNutrition;
window.resetFormAndParent = resetFormAndParent;
window.sendNutritionDataToParent = sendNutritionDataToParent;
window.exportToPDF = exportToPDF;
window.loadExistingData = loadExistingData;
window.buildInputForm = buildInputForm;
window.NUTRITION_DATA = NUTRITION_DATA;
window.loadDataAfterFormReady = loadDataAfterFormReady;
window.processNutritionValue = processNutritionValue;
window.calculateDailyValuePercent = calculateDailyValuePercent;
// V3 함수들도 전역으로 노출
window.generateBasicDisplayV3 = generateBasicDisplayV3;
window.generateParallelDisplayV3 = generateParallelDisplayV3;

})(); // IIFE 종료