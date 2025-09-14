// 영양성분 계산기 모듈 - 리팩토링된 버전
(function() {
'use strict';

// 영양성분 정의 - 한눈에 보는 영양표시 가이드라인 순서 (MFDS 2024 기준)
const NUTRITION_DATA = {
  // 필수 영양성분 (9가지) - 가이드라인 순서
  'calories': { label: '열량', unit: 'kcal', order: 1, required: true, daily_value: null },
  'sodium': { label: '나트륨', unit: 'mg', order: 2, required: true, daily_value: 2000 },
  'carbohydrate': { label: '탄수화물', unit: 'g', order: 3, required: true, daily_value: 324 },
  'sugars': { label: '당류', unit: 'g', order: 4, parent: 'carbohydrate', indent: true, required: true, daily_value: 100 },
  'fat': { label: '지방', unit: 'g', order: 5, required: true, daily_value: 54 },
  'trans_fat': { label: '트랜스지방', unit: 'g', order: 6, parent: 'fat', indent: true, required: true, daily_value: null },
  'saturated_fat': { label: '포화지방', unit: 'g', order: 7, parent: 'fat', indent: true, required: true, daily_value: 15 },
  'cholesterol': { label: '콜레스테롤', unit: 'mg', order: 8, required: true, daily_value: 300 },
  'protein': { label: '단백질', unit: 'g', order: 9, required: true, daily_value: 55 },
  
  // 추가 영양성분 - 식약처 기준 업데이트
  'dietary_fiber': { label: '식이섬유', unit: 'g', order: 10, daily_value: 25 },
  'calcium': { label: '칼슘', unit: 'mg', order: 11, daily_value: 700 },
  'iron': { label: '철', unit: 'mg', order: 12, daily_value: 12 },
  'magnesium': { label: '마그네슘', unit: 'mg', order: 13, daily_value: 315 },
  'phosphorus': { label: '인', unit: 'mg', order: 14, daily_value: 700 },
  'potassium': { label: '칼륨', unit: 'mg', order: 15, daily_value: 3500 },
  'zinc': { label: '아연', unit: 'mg', order: 16, daily_value: 8.5 },
  'vitamin_a': { label: '비타민A', unit: 'μg RAE', order: 17, daily_value: 700 },
  'vitamin_d': { label: '비타민D', unit: 'μg', order: 18, daily_value: 10 },
  'vitamin_e': { label: '비타민E', unit: 'mg α-TE', order: 19, daily_value: 12 },
  'vitamin_c': { label: '비타민C', unit: 'mg', order: 20, daily_value: 100 },
  'thiamine': { label: '티아민', unit: 'mg', order: 21, daily_value: 1.2 },
  'riboflavin': { label: '리보플라빈', unit: 'mg', order: 22, daily_value: 1.4 },
  'niacin': { label: '니아신', unit: 'mg NE', order: 23, daily_value: 15 },
  'vitamin_b6': { label: '비타민B6', unit: 'mg', order: 24, daily_value: 1.5 },
  'folic_acid': { label: '엽산', unit: 'μg DFE', order: 25, daily_value: 400 },
  'vitamin_b12': { label: '비타민B12', unit: 'μg', order: 26, daily_value: 2.4 },
  'selenium': { label: '셀레늄', unit: 'μg', order: 27, daily_value: 55 },
  
  // 추가 영양성분들 (식약처 기준)
  'pantothenic_acid': { label: '판토텐산', unit: 'mg', order: 28, daily_value: 5 },
  'biotin': { label: '비오틴', unit: 'μg', order: 29, daily_value: 30 },
  'iodine': { label: '요오드', unit: 'μg', order: 30, daily_value: 150 },
  'vitamin_k': { label: '비타민K', unit: 'μg', order: 31, daily_value: 70 },
  'copper': { label: '구리', unit: 'mg', order: 32, daily_value: 0.8 },
  'manganese': { label: '망간', unit: 'mg', order: 33, daily_value: 3.0 },
  'chromium': { label: '크롬', unit: 'μg', order: 34, daily_value: 30 },
  'molybdenum': { label: '몰리브덴', unit: 'μg', order: 35, daily_value: 25 }
};

// 강조표시 기준 (식약처 기준)
const EMPHASIS_CRITERIA = {
  // 저 함유 기준 (100g 또는 100ml 기준)
  low: {
    'calories': { threshold: 40, label: '저열량' }, // 40kcal 이하
    'fat': { threshold: 3, label: '저지방' }, // 3g 이하
    'saturated_fat': { threshold: 1.5, label: '저포화지방' }, // 1.5g 이하
    'sugars': { threshold: 5, label: '저당' }, // 5g 이하
    'sodium': { threshold: 120, label: '저나트륨' }, // 120mg 이하
    'cholesterol': { threshold: 20, label: '저콜레스테롤' } // 20mg 이하
  },
  // 무 함유 기준
  free: {
    'calories': { threshold: 4, label: '무열량' }, // 4kcal 미만
    'fat': { threshold: 0.5, label: '무지방' }, // 0.5g 미만
    'saturated_fat': { threshold: 0.1, label: '무포화지방' }, // 0.1g 미만
    'sugars': { threshold: 0.5, label: '무당' }, // 0.5g 미만
    'sodium': { threshold: 5, label: '무나트륨' }, // 5mg 미만
    'cholesterol': { threshold: 2, label: '무콜레스테롤' } // 2mg 미만
  },
  // 고 함유 기준 (100g 또는 100ml 기준, 1일 기준치의 30% 이상)
  high: {
    'protein': { threshold: 16.5, label: '고단백' }, // 1일기준치 30% 이상
    'dietary_fiber': { threshold: 7.5, label: '고식이섬유' }, // 1일기준치 30% 이상
    'calcium': { threshold: 210, label: '고칼슘' }, // 1일기준치 30% 이상
    'iron': { threshold: 3.6, label: '고철분' }, // 1일기준치 30% 이상
    'vitamin_e': { threshold: 3.6, label: '고비타민E' }, // 1일기준치 30% 이상
    'vitamin_c': { threshold: 30, label: '고비타민C' } // 1일기준치 30% 이상
  }
};

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
    case 'sodium':
      if (roundedValue < 5) return '5mg 미만';
      if (roundedValue >= 1000) {
        // 1000mg 이상은 1000mg 단위로 반올림
        const sodiumLargeResult = Math.round(roundedValue / 1000) * 1000;
        return formatNumberWithCommas(sodiumLargeResult);
      } else {
        // 1000mg 미만은 5mg 단위로 반올림
        const sodiumResult = Math.round(roundedValue / 5) * 5;
        return formatNumberWithCommas(sodiumResult);
      }
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
    case 'carbohydrate':
    case 'protein':
    case 'dietary_fiber':
      if (roundedValue < 1) return '1g 미만';
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'sugars': // 당류는 '미만' 표시 없음
      if (roundedValue < 0.5) return '0';
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'fat':
    case 'saturated_fat':
      if (roundedValue < 0.5) return '0';
      if (roundedValue <= 5) {
        const fatResult = Math.round(roundedValue * 10) / 10;
        return formatNumberWithCommas(fatResult);
      }
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'trans_fat':
      if (roundedValue < 0.2) return '0'; // 식약처 기준: 0.2g 미만은 0g
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
  if (key === 'calories' || key === 'trans_fat' || !nutritionInfo.daily_value) return null;

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
      // 쉼표 제거 후 숫자로 변환
      const cleanValue = input.value.replace(/,/g, '');
      const numericValue = parseFloat(cleanValue);
      if (!isNaN(numericValue)) {
        nutritionInputs[key] = numericValue;
      }
    }
  });
  return nutritionInputs;
}

// ===== 영양성분표 생성 함수들 =====

// 기본형/세로형 영양성분표 생성 (가이드라인 준수)
function generateBasicDisplay(nutritionInputs, baseAmount, servingsPerPackage, style) {
  // 세로형인 경우 별도 함수 호출
  if (style === 'vertical') {
    return generateVerticalDisplay(nutritionInputs, baseAmount, servingsPerPackage);
  }
  
  // 표시 기준 확인
  const displayType = document.getElementById('basic_display_type').value;
  let displayAmount, multiplier, headerText;
  
  switch (displayType) {
    case 'unit':
      displayAmount = baseAmount;
      multiplier = baseAmount / 100;
      headerText = `단위내용량 ${baseAmount.toLocaleString()}g당`;
      break;
    case '100g':
      displayAmount = 100;
      multiplier = 1;
      headerText = `100g당`;
      break;
    case 'total':
    default:
      displayAmount = (baseAmount * servingsPerPackage);
      multiplier = displayAmount / 100;
      headerText = `총 내용량 ${displayAmount.toLocaleString()}g당`;
      break;
  }
  
  const calories = processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier);

  // 헤더 HTML - 표시 기준에 따른 동적 헤더
  let html = `
  <div class="nutrition-header">
    <div class="nutrition-title">영양정보</div>
    <div class="nutrition-subheader">${headerText} / <span class="calories-value">${calories.toLocaleString()}</span>kcal</div>
  </div>
  <table class="nutrition-table">
    <thead>
      <tr>
        <th class="nutrition-name">영양성분</th>
        <th class="nutrition-content">함량</th>
        <th class="nutrition-daily">기준치(%)</th>
      </tr>
    </thead>
    <tbody>`;

  // 본문(영양성분) HTML - 가이드라인 순서 준수
  // 9대 기본 성분은 0이어도 항상 표시
  const sortedNutrients = Object.entries(NUTRITION_DATA)
      .filter(([key]) => {
        if (key === 'calories') return false; // 열량은 헤더에 이미 표시
        // 9대 기본 성분(required: true)은 항상 표시, 추가 성분은 값이 있을 때만 표시
        return NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined;
      })
      .sort((a, b) => a[1].order - b[1].order);

  sortedNutrients.forEach(([key, data]) => {
      const originalValue = (nutritionInputs[key] || 0) * multiplier;
      const processedValue = processNutritionValue(key, originalValue);
      const percent = calculateDailyValuePercent(key, processedValue, originalValue);
      
      let displayValue;
      if (processedValue.includes('미만')) {
        displayValue = processedValue;
      } else {
        const numericValue = Number(processedValue.replace(/,/g, ''));
        displayValue = `${numericValue.toLocaleString()}${data.unit}`;
      }

      html += `
      <tr class="nutrition-row">
        <td class="nutrition-name ${data.indent ? 'nutrition-indent' : ''}">${data.label}</td>
        <td class="nutrition-content">${displayValue}</td>
        <td class="nutrition-daily">${percent !== null ? `${percent}%` : '-'}</td>
      </tr>`;
  });

  html += `</tbody>`;
  
  // 푸터 HTML
  html += `
    <tfoot>
      <tr class="nutrition-footer">
        <td colspan="3">* 1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td>
      </tr>
    </tfoot>
  </table>`;
  return html;
}

// 세로형 영양성분표 생성 (공간 협소 시 사용 - 식약처 표준 도안)
function generateVerticalDisplay(nutritionInputs, baseAmount, servingsPerPackage) {
  // 표시 기준 확인
  const displayType = document.getElementById('basic_display_type').value;
  let displayAmount, multiplier, headerText;
  
  switch (displayType) {
    case 'unit':
      displayAmount = baseAmount;
      multiplier = baseAmount / 100;
      headerText = `단위내용량 ${baseAmount.toLocaleString()}g당`;
      break;
    case '100g':
      displayAmount = 100;
      multiplier = 1;
      headerText = `100g당`;
      break;
    case 'total':
    default:
      displayAmount = (baseAmount * servingsPerPackage);
      multiplier = displayAmount / 100;
      headerText = `총 내용량 ${displayAmount.toLocaleString()}g당`;
      break;
  }
  
  const calories = processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier);

  // 세로형 헤더 HTML (식약처 표준 도안) - 표시 기준에 따른 동적 헤더
  let html = `
  <div class="nutrition-vertical">
    <div class="nutrition-vertical-header">
      <div class="nutrition-title-vertical">영양정보</div>
      <div class="nutrition-amount-vertical">${headerText}</div>
      <div class="nutrition-calories-vertical">열량 ${calories.toLocaleString()}kcal</div>
    </div>
    <div class="nutrition-vertical-content">`;

  // 영양성분 세로 나열 (식약처 표준 순서)
  // 9대 기본 성분은 0이어도 항상 표시
  const sortedNutrients = Object.entries(NUTRITION_DATA)
      .filter(([key]) => {
        if (key === 'calories') return false; // 열량은 헤더에 이미 표시
        // 9대 기본 성분(required: true)은 항상 표시, 추가 성분은 값이 있을 때만 표시
        return NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined;
      })
      .sort((a, b) => a[1].order - b[1].order);

  sortedNutrients.forEach(([key, data]) => {
      const originalValue = (nutritionInputs[key] || 0) * multiplier;
      const processedValue = processNutritionValue(key, originalValue);
      const percent = calculateDailyValuePercent(key, processedValue, originalValue);
      
      let displayValue;
      if (processedValue.includes('미만')) {
        displayValue = processedValue;
      } else {
        const numericValue = Number(processedValue.replace(/,/g, ''));
        displayValue = `${numericValue.toLocaleString()}${data.unit}`;
      }

      html += `
      <div class="nutrition-vertical-item ${data.indent ? 'nutrition-vertical-indent' : ''}">
        <span class="nutrition-vertical-name">${data.label}</span>
        <span class="nutrition-vertical-value">${displayValue}</span>
        ${percent !== null ? `<span class="nutrition-vertical-percent">(${percent}%)</span>` : ''}
      </div>`;
  });

  html += `
    </div>
    <div class="nutrition-vertical-footer">
      * 1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.
    </div>
  </div>`;
  
  return html;
}

// 병행표시 영양성분표 생성 (가이드라인 준수 - 4가지 케이스 지원)
function generateParallelDisplay(nutritionInputs, baseAmount, servingsPerPackage) {
  // 병행표시 유형 확인
  const parallelType = document.getElementById('parallel_display_type').value;
  const totalAmount = (baseAmount * servingsPerPackage);
  
  // 단위 확인 (g 또는 ml)
  const baseUnit = document.getElementById('base_amount_unit')?.value || 'g';
  
  let multiplier1, multiplier2, headerText1, headerText2, calories1, calories2;
  
  switch (parallelType) {
    case 'unit_total':
      // Case 1: 단위내용량당 + 총내용량당
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `단위내용량당(${baseAmount.toLocaleString()}${baseUnit})`;
      headerText2 = `총 내용량당(${totalAmount.toLocaleString()}${baseUnit})`;
      break;
      
    case 'unit_100g':
      // Case 2: 단위내용량당 + 100g당
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = `단위내용량당(${baseAmount.toLocaleString()}${baseUnit})`;
      headerText2 = `100${baseUnit}당`;
      break;
      
    case 'serving_total':
      // Case 3: 1회 섭취참고량당 + 총내용량당
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `1회 섭취참고량당(${baseAmount.toLocaleString()}${baseUnit})`;
      headerText2 = `총 내용량당(${totalAmount.toLocaleString()}${baseUnit})`;
      break;
      
    case 'serving_100ml':
      // Case 4: 1회 섭취참고량당 + 100ml당 (주로 음료용)
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = `1회 섭취참고량당(${baseAmount.toLocaleString()}${baseUnit})`;
      headerText2 = `100${baseUnit === 'ml' ? 'ml' : 'g'}당`;
      break;
      
    default:
      // 기본값: 단위내용량당 + 총내용량당
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `단위내용량당(${baseAmount.toLocaleString()}${baseUnit})`;
      headerText2 = `총 내용량당(${totalAmount.toLocaleString()}${baseUnit})`;
      break;
  }
  
  console.log('병행표시 설정:', {
    parallelType,
    baseAmount,
    servingsPerPackage,
    totalAmount,
    baseUnit,
    headerText1,
    headerText2,
    multiplier1,
    multiplier2
  });
  
  calories1 = processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1);
  calories2 = processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier2);

  // 헤더 HTML - 병행형 (표시 유형에 따른 동적 헤더)
  let html = `
  <div class="nutrition-header">
    <div class="nutrition-title">영양정보</div>
    <div class="nutrition-total-info">총 내용량 ${totalAmount.toLocaleString()}g (${baseAmount.toLocaleString()}g X ${servingsPerPackage.toLocaleString()}개)</div>
  </div>
  <table class="nutrition-table">
    <thead>
      <tr class="parallel-header-top">
        <th rowspan="2">영양성분</th>
        <th colspan="2">${headerText1}</th>
        <th colspan="2" class="parallel-divider">${headerText2}</th>
      </tr>
      <tr class="parallel-header-bottom">
        <th>함량</th>
        <th>기준치(%)</th>
        <th class="parallel-divider">함량</th>
        <th>기준치(%)</th>
      </tr>
    </thead>
    <tbody>`;

  // 열량 표시 (9대 기본 성분이므로 항상 표시)
  html += `
    <tr class="nutrition-row">
      <td class="nutrition-name" style="font-weight: bold;">열량</td>
      <td style="text-align:center; font-weight:bold;">${calories1}kcal</td>
      <td style="text-align:center;"></td>
      <td style="text-align:center; font-weight:bold;" class="parallel-divider">${calories2}kcal</td>
      <td style="text-align:center;"></td>
    </tr>`;

  // 본문(영양성분) HTML - 가이드라인 순서 준수
  // 9대 기본 성분은 0이어도 항상 표시
  const sortedNutrients = Object.entries(NUTRITION_DATA)
      .filter(([key]) => {
        if (key === 'calories') return false; // 열량은 별도 처리
        // 9대 기본 성분(required: true)은 항상 표시, 추가 성분은 값이 있을 때만 표시
        return NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined;
      })
      .sort((a, b) => a[1].order - b[1].order);
  
  sortedNutrients.forEach(([key, data]) => {
      const originalValue1 = (nutritionInputs[key] || 0) * multiplier1;
      const processedValue1 = processNutritionValue(key, originalValue1);
      const percent1 = calculateDailyValuePercent(key, processedValue1, originalValue1);
      
      let displayValue1;
      if (processedValue1.includes('미만')) {
        displayValue1 = processedValue1;
      } else {
        const numericValue1 = Number(processedValue1.replace(/,/g, ''));
        displayValue1 = `${numericValue1.toLocaleString()}${data.unit}`;
      }

      const originalValue2 = (nutritionInputs[key] || 0) * multiplier2;
      const processedValue2 = processNutritionValue(key, originalValue2);
      const percent2 = calculateDailyValuePercent(key, processedValue2, originalValue2);
      
      let displayValue2;
      if (processedValue2.includes('미만')) {
        displayValue2 = processedValue2;
      } else {
        const numericValue2 = Number(processedValue2.replace(/,/g, ''));
        displayValue2 = `${numericValue2.toLocaleString()}${data.unit}`;
      }

      html += `
      <tr class="nutrition-row">
        <td class="nutrition-name ${data.indent ? 'nutrition-indent' : ''}">${data.label}</td>
        <td style="text-align:center;">${displayValue1}</td>
        <td style="text-align:center; font-weight:bold;">${percent1 !== null ? (percent1.includes('미만') ? percent1 : percent1 + '%') : ''}</td>
        <td style="text-align:center;" class="parallel-divider">${displayValue2}</td>
        <td style="text-align:center; font-weight:bold;">${percent2 !== null ? (percent2.includes('미만') ? percent2 : percent2 + '%') : ''}</td>
      </tr>`;
  });

  html += `</tbody>`;
  
  // 푸터 HTML
  html += `
    <tfoot>
      <tr class="nutrition-footer">
        <td colspan="5">* 1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td>
      </tr>
    </tfoot>
  </table>`;
  return html;
}

// 단위내용량당 + 총내용량당 병행표시 생성
function generateUnitTotalParallelDisplay(nutritionInputs, baseAmount, servingsPerPackage) {
  const totalAmount = parseFloat((baseAmount * servingsPerPackage).toFixed(1));
  const unitMultiplier = baseAmount / 100;
  const totalMultiplier = totalAmount / 100;
  
  const unitCalories = nutritionInputs['calories'] ? nutritionInputs['calories'] * unitMultiplier : 0;
  const totalCalories = nutritionInputs['calories'] ? nutritionInputs['calories'] * totalMultiplier : 0;
  const processedUnitCalories = processNutritionValue('calories', unitCalories);
  const processedTotalCalories = processNutritionValue('calories', totalCalories);

  let html = '<div id="nutrition-facts-label" class="nutrition-style-parallel">';
  
  // 검은색 헤더 영역 분리
  html += '<div class="nutrition-header">';
  html += '<div class="nutrition-title">영양정보</div>';
  html += '<div class="nutrition-subtitle-parallel">';
  html += `<span class="left-header">1조각당 (${baseAmount}g) ${processedUnitCalories}kcal</span>`;
  html += `<span class="right-header">총 내용량당 (${totalAmount}g) ${processedTotalCalories}kcal</span>`;
  html += '</div>';
  html += '<div class="nutrition-total-info">총 내용량 ${totalAmount}g (${baseAmount}g X ${servingsPerPackage}조각)</div>';
  html += '</div>';
  
  // 흰색 표 영역
  html += '<table class="nutrition-table">';
  html += '<thead>';
  html += '<tr class="nutrition-column-header-top">';
  html += '<th rowspan="2" class="nutrition-name-header">영양성분</th>';
  html += '<th colspan="2" class="nutrition-section-header">1조각당 (${baseAmount}g)</th>';
  html += '<th colspan="2" class="nutrition-section-header parallel-divider">총 내용량당 (${totalAmount}g)</th>';
  html += '</tr>';
  html += '<tr class="nutrition-column-header-bottom">';
  html += '<th class="nutrition-value-header">함량</th>';
  html += '<th class="nutrition-percent-header">영양성분 기준치(%)</th>';
  html += '<th class="nutrition-value-header parallel-divider">함량</th>';
  html += '<th class="nutrition-percent-header">영양성분 기준치(%)</th>';
  html += '</tr>';
  html += '</thead>';
  html += '<tbody>';
  
  const requiredNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && nutritionInputs[key] !== undefined && NUTRITION_DATA[key].required)
    .sort((a, b) => a[1].order - b[1].order);

  requiredNutrients.forEach(([key, data], idx) => {
    const unitValue = nutritionInputs[key] * unitMultiplier;
    const totalValue = nutritionInputs[key] * totalMultiplier;
    const processedUnitValue = processNutritionValue(key, unitValue);
    const processedTotalValue = processNutritionValue(key, totalValue);
    const percentValue = calculateDailyValuePercent(key, processedUnitValue, unitValue);

    const unitDisplay = processedUnitValue.includes('미만') ? processedUnitValue : `${processedUnitValue}${data.unit}`;
    const totalDisplay = processedTotalValue.includes('미만') ? processedTotalValue : `${processedTotalValue}${data.unit}`;

    html += `<tr class="nutrition-row nutrition-thin-line">`;
    html += `<td class="nutrition-name" style="text-align:left;">${data.label}</td>`;
    html += `<td class="nutrition-value" style="text-align:right;">${unitDisplay}</td>`;
    html += `<td class="nutrition-percent nutrition-bold" style="text-align:right;">${percentValue !== null ? percentValue+'%' : ''}</td>`;
    html += `<td class="nutrition-value" style="text-align:right; border-left:4px solid #fff;">${totalDisplay}</td>`;
    html += `<td class="nutrition-percent nutrition-bold" style="text-align:right;">${percentValue !== null ? percentValue+'%' : ''}</td>`;
    html += '</tr>';
  });
  
  const additionalNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && nutritionInputs[key] !== undefined && !NUTRITION_DATA[key].required)
    .sort((a, b) => a[1].order - b[1].order);

  additionalNutrients.forEach(([key, data], idx) => {
    const unitValue = nutritionInputs[key] * unitMultiplier;
    const totalValue = nutritionInputs[key] * totalMultiplier;
    const processedUnitValue = processNutritionValue(key, unitValue);
    const processedTotalValue = processNutritionValue(key, totalValue);
    const percentValue = calculateDailyValuePercent(key, processedUnitValue, unitValue);

    const unitDisplay = processedUnitValue.includes('미만') ? processedUnitValue : `${processedUnitValue}${data.unit}`;
    const totalDisplay = processedTotalValue.includes('미만') ? processedTotalValue : `${processedTotalValue}${data.unit}`;

    html += `<tr class="nutrition-row nutrition-thin-line">`;
    html += `<td class="nutrition-name" style="text-align:left;">${data.label}</td>`;
    html += `<td class="nutrition-value" style="text-align:right;">${unitDisplay}</td>`;
    html += `<td class="nutrition-percent nutrition-bold" style="text-align:right;">${percentValue !== null ? percentValue+'%' : ''}</td>`;
    html += `<td class="nutrition-value" style="text-align:right; border-left:4px solid #fff;">${totalDisplay}</td>`;
    html += `<td class="nutrition-percent nutrition-bold" style="text-align:right;">${percentValue !== null ? percentValue+'%' : ''}</td>`;
    html += '</tr>';
  });

  html += '</tbody>';
  html += '<tfoot>';
  html += `<tr class="nutrition-thick-line"><td colspan="5" class="nutrition-footer">* 1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.<br>총 내용량 ${totalAmount}g (${baseAmount}g X ${servingsPerPackage}조각)</td></tr>`;
  html += '</tfoot>';
  html += '</table>';
  html += '</div>';
  
  return html;
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
      div.className = 'nutrient-item';
      div.innerHTML = `
        <label for="${key}" class="${data.indent ? 'indent' : ''}">${data.label}</label>
        <input type="text" id="${key}" name="${key}" placeholder="0" data-nutrition-key="${key}">
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
      div.className = 'nutrient-item';
      div.innerHTML = `
        <label for="${key}">${data.label}</label>
        <input type="text" id="${key}" name="${key}" placeholder="0" data-nutrition-key="${key}">
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
    // input 이벤트로 실시간 포맷팅
    input.addEventListener('input', function(e) {
      let value = e.target.value;
      
      // 숫자가 아닌 문자 제거 (쉼표와 소수점 제외)
      value = value.replace(/[^\d.,]/g, '');
      
      // 쉼표 제거 후 숫자로 변환
      const numericValue = value.replace(/,/g, '');
      
      // 유효한 숫자인지 확인
      if (numericValue && !isNaN(numericValue)) {
        // 3자리마다 쉼표 추가
        const formattedValue = parseFloat(numericValue).toLocaleString('ko-KR');
        e.target.value = formattedValue;
      } else if (numericValue === '') {
        e.target.value = '';
      }
    });
    
    // focus 이벤트에서 쉼표 제거 (편집 모드)
    input.addEventListener('focus', function(e) {
      const value = e.target.value;
      if (value) {
        console.log(`Focus 이벤트 - ${e.target.id}: "${value}" -> "${value.replace(/,/g, '')}"`);
        e.target.value = value.replace(/,/g, '');
      }
    });
    
    // blur 이벤트에서 쉼표 복원 (표시 모드)
    input.addEventListener('blur', function(e) {
      const value = e.target.value;
      if (value && !isNaN(value.replace(/,/g, ''))) {
        const numericValue = parseFloat(value.replace(/,/g, ''));
        const formattedValue = numericValue.toLocaleString('ko-KR');
        console.log(`Blur 이벤트 - ${e.target.id}: "${value}" -> "${formattedValue}"`);
        e.target.value = formattedValue;
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
  const baseAmount = parseFloat(document.getElementById('base_amount').value) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('servings_per_package').value) || 1;
  const style = document.getElementById('nutrition_style').value;
  
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
    displayHTML = generateParallelDisplay(nutritionInputs, baseAmount, servingsPerPackage);
  } else {
    displayHTML = generateBasicDisplay(nutritionInputs, baseAmount, servingsPerPackage, style);
  }
  
  document.getElementById('resultDisplay').innerHTML = `<div id="nutrition-facts-label" class="nutrition-style-${style}">${displayHTML}</div>`;
  
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
    document.getElementById('base_amount').value = '100';
    document.getElementById('servings_per_package').value = '1';
    document.getElementById('nutrition_style').value = 'basic';
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

  const baseAmount = parseFloat(document.getElementById('base_amount').value) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('servings_per_package').value) || 1;
  const style = document.getElementById('nutrition_style').value;

  // 모든 영양성분을 그대로 전달
  const formattedData = {};
  Object.keys(NUTRITION_DATA).forEach(key => {
    const nutritionInfo = NUTRITION_DATA[key];
    formattedData[key] = {
      label: nutritionInfo.label,
      value: nutritionDataToSave[key] || '',
      unit: nutritionInfo.unit
    };
  });

  const dataToSend = {
    type: 'nutritionData',
    data: {
      nutritionInputs: formattedData,
      baseAmount: baseAmount,
      servingsPerPackage: servingsPerPackage,
      style: style,
      html: document.getElementById('resultDisplay').innerHTML
    }
  };

  if (window.opener && typeof window.opener.postMessage === 'function') {
    window.opener.postMessage(dataToSend, '*');
    alert('영양성분 데이터가 저장되었습니다.');
  } else {
    console.error('부모 창을 찾을 수 없습니다.', dataToSend);
    alert('데이터 저장에 실패했습니다. 부모 창을 찾을 수 없습니다.');
  }
}

// PDF 내보내기
function exportToPDF() {
  const nutritionContainer = document.querySelector('#resultDisplay .nutrition-result-table, #resultDisplay .nutrition-style-basic, #resultDisplay .nutrition-style-vertical, #resultDisplay .nutrition-style-parallel');
  
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
        const styleText = document.getElementById('nutrition_style').value === 'basic' ? '기본형' :
                         document.getElementById('nutrition_style').value === 'vertical' ? '세로형' : '병행표시';
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
        console.error('PDF 생성 오류:', error);
        alert('PDF 생성 중 오류가 발생했습니다: ' + error.message);
      } finally {
        pdfButton.disabled = false;
        pdfButton.innerHTML = originalText;
      }
    }).catch(error => {
      console.error('이미지 변환 오류:', error);
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
    if (!data || typeof data !== 'object') return;
    
    // 중복 실행 방지 - 단, 부모창 데이터는 우선 처리
    const hasParentData = data.calories !== undefined || data.sodium !== undefined || data.carbohydrate !== undefined || data.fat !== undefined;
    
    if (isLoadingData && !hasParentData) {
      console.log('loadExistingData 이미 실행 중입니다 (부모창 데이터 아님).');
      return;
    }
    
    if (hasParentData) {
      console.log('🚀 부모창 데이터 감지 - 우선 처리 시작');
      console.log('🔍 부모창 데이터 상세:', {
        calories: data.calories,
        sodium: data.sodium,
        carbohydrate: data.carbohydrate,
        sugars: data.sugars
      });
      isLoadingData = false; // 부모창 데이터는 항상 처리하도록 플래그 리셋 
      
      // 중첩 구조 데이터가 있어도 부모창 데이터로 덮어쓰기
      if (data.nutrients) {
        console.log('⚠️ 중첩 구조 데이터도 존재하지만 부모창 데이터를 우선 사용');
        delete data.nutrients; // 중첩 구조 데이터 제거하여 부모창 데이터만 사용
      }
    }
    
    isLoadingData = true;
    console.log('loadExistingData 호출됨:', JSON.stringify(data, null, 2));
    
    // DOM이 준비될 때까지 대기 후 실행
    const waitForDOM = () => {
      const basicContainer = document.getElementById('basic-nutrient-inputs');
      const additionalContainer = document.getElementById('additional-nutrient-inputs');
      const allNutritionInputs = document.querySelectorAll('input[data-nutrition-key]');
      
      console.log('입력 폼 준비 상태 확인:', {
        basicContainer: !!basicContainer,
        additionalContainer: !!additionalContainer,
        nutritionInputsCount: allNutritionInputs.length,
        inputIds: Array.from(allNutritionInputs).map(el => el.id)
      });
      
      // DOM이 준비되지 않았으면 다시 시도
      if (!basicContainer || !additionalContainer || allNutritionInputs.length === 0) {
        console.log('DOM이 아직 준비되지 않음, 100ms 후 재시도...');
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
      document.getElementById('base_amount').value = baseValue;
    }
    
    if (data.servingsPerPackage || data.units_per_package) {
      const servingValue = data.servingsPerPackage || data.units_per_package;
      document.getElementById('servings_per_package').value = servingValue;
    }
    
    if (data.style || data.nutrition_style) {
      const styleValue = data.style || data.nutrition_style;
      document.getElementById('nutrition_style').value = styleValue;
    }
    
    // 영양성분 데이터 로드 - 부모창에서 전달받는 형식에 맞게 수정
    let hasAdditionalValue = false;
    
    // 부모창 필드명과 팝업 필드명 매핑 (다양한 변형 포함)
    const fieldMapping = {
      'calories': 'calories',
      'calorie': 'calories',
      'kcal': 'calories',
      'natriums': 'sodium',
      'sodium': 'sodium',
      'na': 'sodium',
      'carbohydrates': 'carbohydrate',
      'carbohydrate': 'carbohydrate',
      'carbs': 'carbohydrate',
      'sugars': 'sugars',
      'sugar': 'sugars',
      'fats': 'fat',
      'fat': 'fat',
      'total_fat': 'fat',
      'trans_fats': 'trans_fat',
      'trans_fat': 'trans_fat',
      'transfat': 'trans_fat',
      'saturated_fats': 'saturated_fat',
      'saturated_fat': 'saturated_fat',
      'sat_fat': 'saturated_fat',
      'cholesterols': 'cholesterol',
      'cholesterol': 'cholesterol',
      'proteins': 'protein',
      'protein': 'protein',
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
    
    // 두 가지 데이터 형식 모두 지원
    // 1. 부모창에서 전달받는 형식 최우선 처리 (collectExistingNutritionData에서 수집)
    if (data.calories !== undefined || data.sodium !== undefined || data.carbohydrate !== undefined || data.fat !== undefined) {
      console.log('📥 부모창 평면 구조 데이터 처리 시작');
      
      Object.keys(fieldMapping).forEach(parentFieldName => {
        const popupFieldName = fieldMapping[parentFieldName];
        const input = document.getElementById(popupFieldName);
        
        // 모든 필드에 대해 입력 필드 존재 여부 확인
        console.log(`필드 검색: ${parentFieldName} -> ${popupFieldName}`, {
          inputExists: !!input,
          hasValue: data[parentFieldName] !== undefined && data[parentFieldName] !== null && data[parentFieldName] !== '',
          actualValue: data[parentFieldName],
          dataType: typeof data[parentFieldName]
        });
        
        if (input && data[parentFieldName] !== undefined && data[parentFieldName] !== null && data[parentFieldName] !== '' && data[parentFieldName] !== '0') {
          const value = data[parentFieldName];
          console.log(`영양성분 로드 시도: ${parentFieldName} -> ${popupFieldName} = ${value}`);
          
          // 문자열에서 숫자만 추출 (쉼표 제거)
          const cleanValue = String(value).replace(/,/g, '');
          const numValue = parseFloat(cleanValue);
          
          if (!isNaN(numValue)) {
            const formattedValue = numValue.toLocaleString('ko-KR');
            console.log(`✅ 값 설정: ${popupFieldName} = ${formattedValue}`);
            
            try {
              // 직접 값 설정
              input.value = formattedValue;
              
              // 이벤트 발생시켜 리액트/뷰 등의 프레임워크 대응
              const inputEvent = new Event('input', { bubbles: true });
              input.dispatchEvent(inputEvent);
              
              const changeEvent = new Event('change', { bubbles: true });
              input.dispatchEvent(changeEvent);
              
            } catch (setError) {
              console.error(`값 설정 오류 - ${popupFieldName}:`, setError);
            }
            
            // 추가 영양성분에 값이 있으면 펼침
            if (NUTRITION_DATA[popupFieldName] && !NUTRITION_DATA[popupFieldName].required) {
              hasAdditionalValue = true;
            }
          }
        }
      });
      
    } else if (data.nutritionInputs) {
      // 2. 기존 형식 (팝업 내부에서 생성된 데이터)
      console.log('📥 팝업 내부 데이터 구조 처리');
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
    } else if (data.nutrients) {
      // 3. 중첩 구조 형식 (nutrients.calories.value)
      console.log('📥 중첩 구조 데이터 처리');
      Object.keys(data.nutrients).forEach(key => {
        const input = document.getElementById(key);
        const nutrientData = data.nutrients[key];
        
        if (input && nutrientData && nutrientData.value && nutrientData.value !== '' && nutrientData.value !== '0') {
          const value = nutrientData.value;
          const numValue = parseFloat(value);
          
          if (!isNaN(numValue)) {
            const formattedValue = numValue.toLocaleString('ko-KR');
            input.value = formattedValue;
            
            if (NUTRITION_DATA[key] && !NUTRITION_DATA[key].required) {
              hasAdditionalValue = true;
            }
          }
        }
      });
    } else {
      // 부모창에서 전달받는 형식 (collectExistingNutritionData에서 수집)
      Object.keys(fieldMapping).forEach(parentFieldName => {
        const popupFieldName = fieldMapping[parentFieldName];
        const input = document.getElementById(popupFieldName);
        
        // 모든 필드에 대해 입력 필드 존재 여부 확인
        console.log(`필드 검색: ${parentFieldName} -> ${popupFieldName}`, {
          inputExists: !!input,
          hasValue: data[parentFieldName] !== undefined && data[parentFieldName] !== null && data[parentFieldName] !== '',
          actualValue: data[parentFieldName],
          dataType: typeof data[parentFieldName]
        });
        
        if (input && data[parentFieldName] !== undefined && data[parentFieldName] !== null && data[parentFieldName] !== '' && data[parentFieldName] !== '0') {
          const value = data[parentFieldName];
          console.log(`영양성분 로드 시도: ${parentFieldName} -> ${popupFieldName} = ${value}`);
          
          // 문자열에서 숫자만 추출 (쉼표 제거)
          const cleanValue = String(value).replace(/,/g, '');
          const numValue = parseFloat(cleanValue);
          
          if (!isNaN(numValue)) {
            const formattedValue = numValue.toLocaleString('ko-KR');
            console.log(`DOM 필드 확인 - ${popupFieldName}:`, {
              element: !!input,
              tagName: input?.tagName,
              id: input?.id,
              currentValue: input?.value,
              newValue: formattedValue,
              isReadOnly: input?.readOnly,
              isDisabled: input?.disabled
            });
            
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
              
              console.log(`값 설정 완료 - ${popupFieldName}: ${formattedValue}`);
            } catch (setError) {
              console.error(`값 설정 오류 - ${popupFieldName}:`, setError);
            }
            
            // 값이 실제로 설정되었는지 확인
            setTimeout(() => {
              const actualValue = document.getElementById(popupFieldName)?.value;
              console.log(`값 설정 확인 - ${popupFieldName}: 설정값="${formattedValue}", 실제값="${actualValue}"`);
              
              // 만약 여전히 값이 설정되지 않았다면 추가 시도
              if (!actualValue || actualValue === '') {
                const retryInput = document.getElementById(popupFieldName);
                if (retryInput) {
                  retryInput.value = formattedValue;
                  retryInput.setAttribute('value', formattedValue);
                  console.log(`재설정 시도 - ${popupFieldName}: ${formattedValue}`);
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
            console.warn(`입력 필드를 찾을 수 없음: ${popupFieldName}`);
            // 전체 DOM에서 해당 ID를 가진 요소가 있는지 확인
            const allElements = document.querySelectorAll(`#${popupFieldName}, [name="${popupFieldName}"], [data-nutrition-key="${popupFieldName}"]`);
            console.log(`DOM 검색 결과 - ${popupFieldName}:`, allElements.length, allElements);
            
            // 모든 input 요소 출력 (디버깅용)
            const allInputs = document.querySelectorAll('input[data-nutrition-key]');
            console.log('현재 존재하는 영양성분 입력 필드들:', Array.from(allInputs).map(el => el.id));
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
    if (hasAdditionalValue && additionalSection && additionalSection.style.display === 'none') {
      additionalSection.style.display = 'block';
      if (toggleIcon) {
        toggleIcon.textContent = '▲';
        toggleIcon.classList.add('rotated');
      }
      if (toggleText) {
        toggleText.textContent = '성분 접기';
      }
    }
    // 자동 계산
    setTimeout(() => {
      calculateNutrition();
    }, 100);
    };
    
    // DOM 대기 시작
    waitForDOM();
    
  } catch (error) {
    console.error('데이터 로드 오류:', error);
  } finally {
    // 3초 후 플래그 해제 (DOM 로드 및 처리 완료 대기)
    setTimeout(() => {
      isLoadingData = false;
      console.log('loadExistingData 플래그 해제됨');
    }, 3000);
  }
}

// ===== 이벤트 핸들러들 =====

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
  
  // 스타일 변경 시 자동 계산 (영양성분 데이터가 있는 경우에만)
  const baseAmount = document.getElementById('base_amount').value;
  const servingsPerPackage = document.getElementById('servings_per_package').value;
  
  // 영양성분 입력값이 하나라도 있는지 확인
  const hasNutritionData = Object.keys(NUTRITION_DATA).some(key => {
    const input = document.getElementById(key);
    return input && input.value && input.value.trim() !== '';
  });
  
  if (baseAmount && servingsPerPackage && hasNutritionData) {
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

// 페이지 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM 로드 완료, 입력 폼 생성 시작');
  buildInputForm();
  
  // buildInputForm이 완료될 때까지 충분히 기다린 후 데이터 로드
  setTimeout(() => {
    console.log('입력 폼 생성 완료 대기 중...');
    
    // DOM 요소가 실제로 생성되었는지 여러 번 확인
    const waitForFormReady = () => {
      const testFields = [
        document.getElementById('calories'),
        document.getElementById('sodium'), 
        document.getElementById('carbohydrate')
      ];
      
      const allFieldsReady = testFields.every(field => field !== null);
      console.log('폼 준비 상태 체크:', {
        allFieldsReady,
        calories: !!testFields[0],
        sodium: !!testFields[1], 
        carbohydrate: !!testFields[2]
      });
      
      if (allFieldsReady) {
        console.log('모든 입력 필드 준비 완료, 데이터 로드 시작');
        loadDataAfterFormReady();
      } else {
        console.log('입력 필드 아직 준비 안됨, 100ms 후 재시도');
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
function loadDataAfterFormReady() {
  console.log('loadDataAfterFormReady 시작');
  
  if (window.opener && !window.opener.closed) {
    console.log('부모창 접근 가능');
    
    try {
      const parentData = window.opener.getNutritionDataForPopup();
      console.log('부모창에서 받은 데이터:', JSON.stringify(parentData, null, 2));
      console.log('부모창 데이터 키들:', Object.keys(parentData));
      console.log('부모창 calories 값:', parentData.calories);
      console.log('부모창 sodium 값:', parentData.sodium);
      
      if (parentData && Object.keys(parentData).length > 0) {
        console.log('부모창 데이터 존재, 데이터 로드 시작');
        loadExistingData(parentData);
      } else {
        console.log('부모창 데이터 없음, URL 파라미터 사용');
        loadDataFromUrlParams();
      }
    } catch (e) {
      console.error('부모창 데이터 전달 오류:', e);
      loadDataFromUrlParams();
    }
  } else {
    console.log('부모창 접근 불가, URL 파라미터 사용');
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
    
    if (urlParams.get('nutrition_style')) {
      data.style = urlParams.get('nutrition_style');
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
      console.log('URL 파라미터에서 데이터 로드:', data);
      loadExistingData(data);
    }
    
  } catch (error) {
    console.error('URL 파라미터 로드 오류:', error);
  }
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

})(); // IIFE 종료