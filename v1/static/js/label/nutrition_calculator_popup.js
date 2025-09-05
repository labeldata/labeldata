// 영양성분 정의 - 한눈에 보는 영양표시 가이드라인 순서 (MFDS 2024 기준)
const NUTRITION_DATA = {
  // 필수 영양성분 (9가지) - 가이드라인 순서
  'calories': { label: '열량', unit: 'kcal', order: 1, required: true, daily_value: null },
  'sodium': { label: '나트륨', unit: 'mg', order: 2, required: true, daily_value: 2000 },
  'carbohydrate': { label: '탄수화물', unit: 'g', order: 3, required: true, daily_value: 324 },
  'sugars': { label: '당류', unit: 'g', order: 4, parent: 'carbohydrate', indent: true, required: true, daily_value: 100 },
  'fat': { label: '지방', unit: 'g', order: 5, required: true, daily_value: 54 },
  'saturated_fat': { label: '포화지방', unit: 'g', order: 6, parent: 'fat', indent: true, required: true, daily_value: 15 },
  'trans_fat': { label: '트랜스지방', unit: 'g', order: 7, parent: 'fat', indent: true, required: true, daily_value: null },
  'cholesterol': { label: '콜레스테롤', unit: 'mg', order: 8, required: true, daily_value: 300 },
  'protein': { label: '단백질', unit: 'g', order: 9, required: true, daily_value: 55 },
  
  // 추가 영양성분 - 식약처 기준 업데이트
  'dietary_fiber': { label: '식이섬유', unit: 'g', order: 10, daily_value: 25 },
  'calcium': { label: '칼슘', unit: 'mg', order: 11, daily_value: 700 },
  'iron': { label: '철', unit: 'mg', order: 12, daily_value: 12 },
  'vitamin_a': { label: '비타민A', unit: 'μg RE', order: 13, daily_value: 700 },
  'vitamin_c': { label: '비타민C', unit: 'mg', order: 14, daily_value: 100 },
  'potassium': { label: '칼륨', unit: 'mg', order: 15, daily_value: 3500 },
  'magnesium': { label: '마그네슘', unit: 'mg', order: 16, daily_value: 315 },
  'phosphorus': { label: '인', unit: 'mg', order: 17, daily_value: 700 },
  'zinc': { label: '아연', unit: 'mg', order: 18, daily_value: 8.5 },
  'vitamin_d': { label: '비타민D', unit: 'μg', order: 19, daily_value: 10 },
  'vitamin_e': { label: '비타민E', unit: 'mg α-TE', order: 20, daily_value: 12 },
  'vitamin_k': { label: '비타민K', unit: 'μg', order: 21, daily_value: 70 },
  'vitamin_b1': { label: '티아민', unit: 'mg', order: 22, daily_value: 1.2 },
  'vitamin_b2': { label: '리보플라빈', unit: 'mg', order: 23, daily_value: 1.4 },
  'niacin': { label: '나이아신', unit: 'mg NE', order: 24, daily_value: 15 },
  'folic_acid': { label: '엽산', unit: 'μg DFE', order: 25, daily_value: 400 },
  'vitamin_b12': { label: '비타민B12', unit: 'μg', order: 26, daily_value: 2.4 },
  'selenium': { label: '셀레늄', unit: 'μg', order: 27, daily_value: 55 }
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
    'trans_fat': { threshold: 0.2, label: '무트랜스지방' }, // 0.2g 미만
    'sugars': { threshold: 0.5, label: '무당' }, // 0.5g 미만
    'sodium': { threshold: 5, label: '무나트륨' }, // 5mg 미만
    'cholesterol': { threshold: 2, label: '무콜레스테롤' } // 2mg 미만
  },
  // 고 함유 기준 (100g 기준)
  high: {
    'protein': { threshold: 12, label: '고단백' }, // 12g 이상
    'dietary_fiber': { threshold: 6, label: '고식이섬유' }, // 6g 이상
    'calcium': { threshold: 210, label: '고칼슘' }, // 1일기준치 30% 이상
    'iron': { threshold: 3.6, label: '고철분' }, // 1일기준치 30% 이상
    'vitamin_c': { threshold: 30, label: '고비타민C' } // 1일기준치 30% 이상
  }
};

// 강조표시 가능 여부 검증 함수
function checkEmphasisEligibility(key, value) {
  if (!value || value === 0) return null;
  
  const emphasis = [];
  
  // 무 함유 기준 체크 (가장 우선순위 높음)
  if (EMPHASIS_CRITERIA.free[key]) {
    const freeThreshold = EMPHASIS_CRITERIA.free[key].threshold;
    if (value < freeThreshold) {
      emphasis.push({
        type: 'free',
        label: EMPHASIS_CRITERIA.free[key].label,
        priority: 1
      });
    }
  }
  
  // 저 함유 기준 체크
  if (EMPHASIS_CRITERIA.low[key]) {
    const lowThreshold = EMPHASIS_CRITERIA.low[key].threshold;
    if (value <= lowThreshold) {
      emphasis.push({
        type: 'low',
        label: EMPHASIS_CRITERIA.low[key].label,
        priority: 2
      });
    }
  }
  
  // 고 함유 기준 체크
  if (EMPHASIS_CRITERIA.high[key]) {
    const highThreshold = EMPHASIS_CRITERIA.high[key].threshold;
    if (value >= highThreshold) {
      emphasis.push({
        type: 'high',
        label: EMPHASIS_CRITERIA.high[key].label,
        priority: 3
      });
    }
  }
  
  // 우선순위가 높은 것 반환 (무 > 저 > 고)
  if (emphasis.length > 0) {
    return emphasis.sort((a, b) => a.priority - b.priority)[0];
  }
  
  return null;
}

// 강조표시 추천 메시지 생성
function generateEmphasisRecommendations(nutritionInputs) {
  const recommendations = [];
  const usedNutrients = new Set(); // 중복 방지를 위한 Set
  
  Object.keys(nutritionInputs).forEach(key => {
    const value = nutritionInputs[key];
    const emphasis = checkEmphasisEligibility(key, value);
    
    if (emphasis) {
      const nutrientName = NUTRITION_DATA[key]?.label || key;
      const emphasisLabel = emphasis.label;
      
      // 강조표시만 표시 (영양소명 제외)
      // 예: "저나트륨"만 표시, "나트륨"은 표시하지 않음
      const duplicateKey = `${nutrientName}`;
      if (!usedNutrients.has(duplicateKey)) {
        usedNutrients.add(duplicateKey);
        recommendations.push({
          nutrient: emphasisLabel, // 영양소명 대신 강조표시명만 사용
          emphasis: emphasisLabel,
          type: emphasis.type,
          message: `${emphasisLabel} 기준에 해당합니다.`
        });
      }
    }
  });
  
  return recommendations;
}

// 강조표시 검토 결과 HTML 생성
function generateEmphasisReviewHTML(nutritionInputs) {
  const recommendations = generateEmphasisRecommendations(nutritionInputs);
  
  if (recommendations.length === 0) {
    return '<div class="emphasis-review-section"><h4 class="emphasis-title">강조표시 검토결과</h4><p class="no-emphasis">현재 입력된 영양성분으로는 강조표시 기준에 해당하는 항목이 없습니다.</p></div>';
  }
  
  let html = '<div class="emphasis-review-section">';
  html += '<h4 class="emphasis-title">강조표시 검토결과</h4>';
  html += '<div class="emphasis-recommendations">';
  
  // 타입별로 그룹화
  const groupedRecs = {
    free: recommendations.filter(r => r.type === 'free'),
    low: recommendations.filter(r => r.type === 'low'),
    high: recommendations.filter(r => r.type === 'high')
  };
  
  if (groupedRecs.free.length > 0) {
    html += '<div class="emphasis-group emphasis-group-free">';
    html += '<span class="emphasis-group-title">무 함유 표시 가능:</span>';
    html += '<ul class="emphasis-list">';
    groupedRecs.free.forEach(rec => {
      html += `<li class="emphasis-item emphasis-free-item"><span class="emphasis-badge emphasis-free">${rec.emphasis}</span></li>`;
    });
    html += '</ul></div>';
  }
  
  if (groupedRecs.low.length > 0) {
    html += '<div class="emphasis-group emphasis-group-low">';
    html += '<span class="emphasis-group-title">저 함유 표시 가능:</span>';
    html += '<ul class="emphasis-list">';
    groupedRecs.low.forEach(rec => {
      html += `<li class="emphasis-item emphasis-low-item"><span class="emphasis-badge emphasis-low">${rec.emphasis}</span></li>`;
    });
    html += '</ul></div>';
  }
  
  if (groupedRecs.high.length > 0) {
    html += '<div class="emphasis-group emphasis-group-high">';
    html += '<span class="emphasis-group-title">고 함유 표시 가능:</span>';
    html += '<ul class="emphasis-list">';
    groupedRecs.high.forEach(rec => {
      html += `<li class="emphasis-item emphasis-high-item"><span class="emphasis-badge emphasis-high">${rec.emphasis}</span></li>`;
    });
    html += '</ul></div>';
  }
  
  html += '</div>';
  html += '<p class="emphasis-note">※ 강조표시 사용 시 식약처 기준을 준수하고 필요시 승인을 받으시기 바랍니다.</p>';
  html += '</div>';
  
  return html;
}

// 강조표시 추천 메시지 표시
function showEmphasisRecommendations(nutritionInputs) {
  const recommendations = generateEmphasisRecommendations(nutritionInputs);
  
  if (recommendations.length === 0) return;
  
  let message = '💡 강조표시 추천:\n\n';
  recommendations.forEach(rec => {
    message += `• ${rec.message}\n`;
  });
  
  message += '\n이러한 강조표시를 제품 포장에 추가하면 소비자에게 더 명확한 정보를 제공할 수 있습니다.';
  
  // 3초 후에 추천 메시지 표시 (사용자가 결과를 먼저 확인할 수 있도록)
  setTimeout(() => {
    if (confirm(message + '\n\n자세한 강조표시 기준을 확인하시겠습니까?')) {
      showEmphasisCriteria();
    }
  }, 3000);
}

// 강조표시 기준 상세 정보 표시
function showEmphasisCriteria() {
  let criteriaMessage = '📋 강조표시 기준 (100g 기준):\n\n';
  
  criteriaMessage += '🔸 무 함유 기준:\n';
  criteriaMessage += '• 무열량: 4kcal 미만\n';
  criteriaMessage += '• 무지방: 0.5g 미만\n';
  criteriaMessage += '• 무당: 0.5g 미만\n';
  criteriaMessage += '• 무나트륨: 5mg 미만\n';
  criteriaMessage += '• 무트랜스지방: 0.2g 미만\n\n';
  
  criteriaMessage += '🔸 저 함유 기준:\n';
  criteriaMessage += '• 저열량: 40kcal 이하\n';
  criteriaMessage += '• 저지방: 3g 이하\n';
  criteriaMessage += '• 저당: 5g 이하\n';
  criteriaMessage += '• 저나트륨: 120mg 이하\n\n';
  
  criteriaMessage += '🔸 고 함유 기준:\n';
  criteriaMessage += '• 고단백: 12g 이상\n';
  criteriaMessage += '• 고식이섬유: 6g 이상\n';
  criteriaMessage += '• 고칼슘: 210mg 이상 (1일기준치 30%)\n';
  criteriaMessage += '• 고철분: 3.6mg 이상 (1일기준치 30%)\n';
  criteriaMessage += '• 고비타민C: 30mg 이상 (1일기준치 30%)\n\n';
  
  criteriaMessage += '※ 강조표시 사용 시 식약처 승인이 필요할 수 있습니다.';
  
  alert(criteriaMessage);
}

// 전역 변수
let currentNutritionData = {};
let productName = ''; // 제품명 저장용

// 숫자 3자리 단위 쉼표 포맷팅 함수
function formatNumberWithCommas(num) {
  if (typeof num === 'string') {
    // 이미 포맷된 문자열이거나 특수 값('0', '미만' 포함) 처리
    if (num.includes('미만') || num === '0') return num;
    const numValue = parseFloat(num);
    if (isNaN(numValue)) return num;
    return numValue.toLocaleString('ko-KR');
  }
  if (typeof num === 'number') {
    return num.toLocaleString('ko-KR');
  }
  return num;
}

// 영양성분표 검증 함수들 (식약처 기준)
function validateMandatoryItems(nutritionData) {
  const mandatoryItems = [
    'calories', 'carbohydrate', 'sugars', 'protein', 'fat', 
    'saturated_fat', 'trans_fat', 'cholesterol', 'sodium'
  ];
  
  const missingItems = [];
  mandatoryItems.forEach(item => {
    const value = nutritionData[item];
    if (!value || value === 0 || value === '') {
      missingItems.push(NUTRITION_DATA[item].label);
    }
  });
  
  return missingItems;
}

function validateNutritionLabel(nutritionData) {
  const errors = [];
  const warnings = [];
  
  // 필수 항목 검증
  const missingItems = validateMandatoryItems(nutritionData);
  if (missingItems.length > 0) {
    errors.push(`필수 영양성분이 누락되었습니다: ${missingItems.join(', ')}`);
  }
  
  // 단위 검증 (이미 NUTRITION_DATA에 정의된 표준 단위 사용)
  Object.keys(nutritionData).forEach(key => {
    if (NUTRITION_DATA[key] && nutritionData[key] !== null && nutritionData[key] !== '') {
      // 값이 음수인지 확인
      if (parseFloat(nutritionData[key]) < 0) {
        errors.push(`${NUTRITION_DATA[key].label}은(는) 음수가 될 수 없습니다.`);
      }
    }
  });
  
  // 논리적 관계 검증 (MFDS 기준)
  const carbs = parseFloat(nutritionData.carbohydrate) || 0;
  const sugars = parseFloat(nutritionData.sugars) || 0;
  const fat = parseFloat(nutritionData.fat) || 0;
  const saturatedFat = parseFloat(nutritionData.saturated_fat) || 0;
  const transFat = parseFloat(nutritionData.trans_fat) || 0;
  const calories = parseFloat(nutritionData.calories) || 0;
  const protein = parseFloat(nutritionData.protein) || 0;
  
  // 당류는 탄수화물을 초과할 수 없음
  if (sugars > carbs) {
    errors.push('당류가 탄수화물보다 많습니다. 확인해주세요.');
  }
  
  // 포화지방은 총 지방을 초과할 수 없음
  if (saturatedFat > fat) {
    errors.push('포화지방이 총 지방보다 많습니다. 확인해주세요.');
  }
  
  // 트랜스지방은 총 지방을 초과할 수 없음
  if (transFat > fat) {
    errors.push('트랜스지방이 총 지방보다 많습니다. 확인해주세요.');
  }
  
  // 현실성 검증 (100g 기준)
  if (calories > 0) {
    // 열량 대비 영양소 비율 검증 (아트워터 공식)
    // 탄수화물: 4kcal/g, 지방: 9kcal/g, 단백질: 4kcal/g
    const calculatedCalories = (carbs * 4) + (fat * 9) + (protein * 4);
    const difference = Math.abs(calories - calculatedCalories);
    
    if (difference > calories * 0.2) { // 20% 이상 차이
      const formattedCalories = formatNumberWithCommas(calories);
      const formattedCalculatedCalories = formatNumberWithCommas(Math.round(calculatedCalories));
      const formattedCarbs = formatNumberWithCommas(carbs);
      const formattedFat = formatNumberWithCommas(fat);
      const formattedProtein = formatNumberWithCommas(protein);
      
      warnings.push(`입력된 열량(${formattedCalories}kcal)과 계산된 열량(${formattedCalculatedCalories}kcal)의 차이가 큽니다.\n계산 공식: 탄수화물(${formattedCarbs}g×4) + 지방(${formattedFat}g×9) + 단백질(${formattedProtein}g×4) = ${formattedCalculatedCalories}kcal\n확인해주세요.`);
    }
    
    // 비현실적인 열량 검증
    if (calories < 5 && (carbs > 1 || fat > 1 || protein > 1)) {
      warnings.push('영양성분에 비해 열량이 너무 낮습니다.');
    }
    
    if (calories > 900) {
      const formattedCalories = formatNumberWithCommas(calories);
      warnings.push(`100g당 열량이 ${formattedCalories}kcal로 900kcal를 초과합니다. 확인해주세요.`);
    }
  }
  
  // 트랜스지방 현실성 검증
  if (transFat > 5) {
    const formattedTransFat = formatNumberWithCommas(transFat);
    warnings.push(`트랜스지방이 ${formattedTransFat}g으로 5g을 초과합니다. 일반적으로 트랜스지방은 매우 낮은 수준입니다.`);
  }
  
  // 나트륨 현실성 검증
  const sodium = parseFloat(nutritionData.sodium) || 0;
  if (sodium > 5000) {
    const formattedSodium = formatNumberWithCommas(sodium);
    warnings.push(`나트륨이 ${formattedSodium}mg으로 5,000mg을 초과합니다. 확인해주세요.`);
  }
  
  return { errors, warnings };
}

// 영양성분값 처리 함수 (가이드라인 기준)
function processNutritionValue(key, value) {
  if (value === null || isNaN(value)) return '0';
  const roundedValue = Math.round(value * 100) / 100; // 소수점 둘째자리까지 계산

  switch (key) {
    case 'calories':
      if (roundedValue < 5) return '0';
      const caloriesResult = Math.round(roundedValue / 5) * 5;
      return formatNumberWithCommas(caloriesResult);
    case 'sodium':
      if (roundedValue < 5) return '0';
      let sodiumResult;
      if (roundedValue <= 120) {
        sodiumResult = Math.round(roundedValue / 5) * 5;
      } else {
        sodiumResult = Math.round(roundedValue / 10) * 10;
      }
      return formatNumberWithCommas(sodiumResult);
    case 'carbohydrate':
    case 'protein':
      if (roundedValue < 0.5) return '0';
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
      if (roundedValue < 0.2) return '0';
      if (roundedValue < 0.5) return '0.5g 미만';
      const transResult = Math.round(roundedValue * 10) / 10;
      return formatNumberWithCommas(transResult);
    case 'cholesterol':
      if (roundedValue < 2) return '0';
      if (roundedValue < 5) return '5mg 미만';
      const cholesterolResult = Math.round(roundedValue / 5) * 5;
      return formatNumberWithCommas(cholesterolResult);
    default:
      if (roundedValue < 0.1) return '0';
      const defaultResult = Math.round(roundedValue * 10) / 10;
      return formatNumberWithCommas(defaultResult);
  }
}

// % 영양성분 기준치 계산 함수
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
  const roundedPercent = Math.round(percent);
  return formatNumberWithCommas(roundedPercent);
}

// 총 내용량 표시 문구 생성
function generateTotalContentText(baseAmount, servingsPerPackage, displayType) {
  const totalAmount = baseAmount * servingsPerPackage;
  
  switch (displayType) {
    case 'total':
      return `총 내용량 ${totalAmount}g당`;
    case 'unit':
      return `1회 제공량 ${baseAmount}g당`;
    case '100g':
      return '100g당';
    case 'serving_total':
    case 'unit_total':
      return `1회 제공량 ${baseAmount}g당`;
    case 'serving_100ml':
      return `1회 제공량 ${baseAmount}ml당`;
    case 'unit_100g':
      return `1회 제공량 ${baseAmount}g당`;
    default:
      return `총 내용량 ${totalAmount}g당`;
  }
}

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
  
  // 기존 데이터가 있으면 필드에 자동으로 입력 (자동 계산은 하지 않음)
  if (servingSize && unitsPerPackage) {
    console.log('기존 데이터 로드 완료 - 자동 계산 없음');
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
    if (data.required) {
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
  // 입력 필드 데이터 확인
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

  // 영양성분 데이터가 없으면 경고 메시지 표시
  if (Object.keys(nutritionInputs).length === 0) {
    alert('영양성분 데이터를 입력해주세요.');
    return;
  }

  // 계산 버튼을 비활성화하고 로딩 표시
  const calculateBtn = document.getElementById('calculateBtn');
  const originalText = calculateBtn.innerHTML;
  calculateBtn.disabled = true;
  calculateBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>계산 중...';
  
  // 영양성분표 검증 실행
  const validation = validateNutritionLabel(nutritionInputs);
  if (validation.errors.length > 0) {
    alert('오류가 발견되었습니다:\n' + validation.errors.join('\n'));
    calculateBtn.disabled = false;
    calculateBtn.innerHTML = originalText;
    return;
  }
  
  // 경고사항이 있는 경우 사용자에게 알림 (계속 진행 가능)
  if (validation.warnings.length > 0) {
    const proceed = confirm('다음 사항을 확인해주세요:\n' + validation.warnings.join('\n') + '\n\n계속 진행하시겠습니까?');
    if (!proceed) {
      calculateBtn.disabled = false;
      calculateBtn.innerHTML = originalText;
      return;
    }
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
  let totalContentText = '';
  
  const totalAmount = parseFloat((baseAmount * servingsPerPackage).toFixed(1));

  switch (displayType) {
    case 'total':
      multiplier = totalAmount / 100;
      totalContentText = `총 내용량 ${totalAmount}g`;
      break;
    case 'unit':
      multiplier = baseAmount / 100;
      totalContentText = `1회 제공량 ${baseAmount}g`;
      break;
    case '100g':
      multiplier = 1;
      totalContentText = '100g';
      break;
  }

  const caloriesValue = nutritionInputs['calories'] ? nutritionInputs['calories'] * multiplier : 0;
  const processedCalories = processNutritionValue('calories', caloriesValue);

  const styleClass = `nutrition-style-${style}`;

  let html = `<div class="${styleClass}">`;
  html += '<table class="nutrition-table">';

  // <thead>: 제목, 부제목, 컬럼 헤더
  html += '<thead>';
  html += `<tr><th class="nutrition-title" colspan="3">영양정보</th></tr>`;
  html += `<tr><th class="nutrition-subheader" colspan="3">${totalContentText} <span class="calories-value">${processedCalories}kcal</span></th></tr>`;
  html += '</thead>';

  // <tbody>: 영양성분 목록
  html += '<tbody>';
  
  // 필수 영양성분 먼저 표시
  const requiredNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && nutritionInputs[key] !== undefined && NUTRITION_DATA[key].required)
    .sort((a, b) => a[1].order - b[1].order);

  requiredNutrients.forEach(([key, data]) => {
    const originalValue = nutritionInputs[key] * multiplier;
    const processedValue = processNutritionValue(key, originalValue);
    const percentValue = calculateDailyValuePercent(key, processedValue, originalValue);
    const emphasis = checkEmphasisEligibility(key, originalValue);

    html += '<tr class="nutrition-row">';
    html += `<td class="nutrition-name${data.indent ? ' nutrition-indent' : ''}">${data.label}</td>`;
    // '미만'이 아닌 경우에만 단위(unit)를 붙임
    const displayValue = processedValue.includes('미만') ? processedValue : `${processedValue}${data.unit}`;
    html += `<td class="nutrition-value">${displayValue}</td>`;
    html += `<td class="nutrition-percent">${percentValue !== null ? `<b>${percentValue}%</b>` : ''}</td>`;
    html += '</tr>';
  });
  
  // 추가 영양성분 표시 (값이 입력된 것만)
  const additionalNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && nutritionInputs[key] !== undefined && !NUTRITION_DATA[key].required)
    .sort((a, b) => a[1].order - b[1].order);

  if (additionalNutrients.length > 0) {
    additionalNutrients.forEach(([key, data]) => {
      const originalValue = nutritionInputs[key] * multiplier;
      const processedValue = processNutritionValue(key, originalValue);
      const percentValue = calculateDailyValuePercent(key, processedValue, originalValue);
      const emphasis = checkEmphasisEligibility(key, originalValue);

      html += '<tr class="nutrition-row">';
      html += `<td class="nutrition-name">${data.label}</td>`;
      // '미만'이 아닌 경우에만 단위(unit)를 붙임
      const displayValue = processedValue.includes('미만') ? processedValue : `${processedValue}${data.unit}`;
      html += `<td class="nutrition-value">${displayValue}</td>`;
      html += `<td class="nutrition-percent">${percentValue !== null ? `<b>${percentValue}%</b>` : ''}</td>`;
      html += '</tr>';
    });
  }
  html += '</tbody>';

  // <tfoot>: 하단 안내 문구
  html += '<tfoot>';
  html += '<tr><td colspan="3" class="nutrition-footer">* 1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td></tr>';
  html += '</tfoot>';

  html += '</table>';
  
  // 강조표시 검토 결과 추가
  html += generateEmphasisReviewHTML(nutritionInputs);
  
  html += '</div>';
  return html;
}

// 병행표시 생성
function generateParallelDisplay(nutritionInputs, baseAmount, servingsPerPackage) {
  const displayType = document.getElementById('parallel_display_type').value;
  let multiplier1 = 1, multiplier2 = 1;
  let headerText1 = '', headerText2 = '';
  
  const totalAmount = parseFloat((baseAmount * servingsPerPackage).toFixed(1));

  switch (displayType) {
    case 'unit_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `1회 제공량당 (${baseAmount}g)`;
      headerText2 = `총 내용량당 (${totalAmount}g)`;
      break;
    case 'unit_100g':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = `1회 제공량당 (${baseAmount}g)`;
      headerText2 = '100g당';
      break;
    case 'serving_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `1회 섭취참고량당 (${baseAmount}g)`;
      headerText2 = `총 내용량당 (${totalAmount}g)`;
      break;
    case 'serving_100ml':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = `1회 섭취참고량당 (${baseAmount}ml)`;
      headerText2 = '100ml당';
      break;
  }

  const calories1 = nutritionInputs['calories'] ? nutritionInputs['calories'] * multiplier1 : 0;
  const calories2 = nutritionInputs['calories'] ? nutritionInputs['calories'] * multiplier2 : 0;
  const processedCalories1 = processNutritionValue('calories', calories1);
  const processedCalories2 = processNutritionValue('calories', calories2);

  let html = '<div class="nutrition-style-parallel">';
  html += '<table class="nutrition-table">';

  // <thead>: 제목과 다단 헤더
  html += '<thead>';
  html += '<tr><th class="nutrition-title" colspan="5">영양정보</th></tr>';
  html += '<tr>';
  html += `<th class="nutrition-subheader" colspan="3">${headerText1} <span class="calories-value">${processedCalories1}kcal</span></th>`;
  html += `<th class="nutrition-subheader subheader-right" colspan="2">${headerText2} <span class="calories-value">${processedCalories2}kcal</span></th>`;
  html += '</tr>';
  html += '<tr class="column-headers">';
  html += '<th class="nutrition-name-header">영양성분</th>';
  html += '<th>함량</th><th class="percent-header">%영양성분기준치</th>';
  html += '<th>함량</th><th class="percent-header">%영양성분기준치</th>';
  html += '</tr>';
  html += '</thead>';

  // <tbody>: 영양성분 목록
  html += '<tbody>';
  
  // 필수 영양성분 먼저 표시
  const requiredNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && nutritionInputs[key] !== undefined && NUTRITION_DATA[key].required)
    .sort((a, b) => a[1].order - b[1].order);

  requiredNutrients.forEach(([key, data]) => {
    const originalValue1 = nutritionInputs[key] * multiplier1;
    const processedValue1 = processNutritionValue(key, originalValue1);
    const percentValue1 = calculateDailyValuePercent(key, processedValue1, originalValue1);
    const emphasis1 = checkEmphasisEligibility(key, originalValue1);

    const originalValue2 = nutritionInputs[key] * multiplier2;
    const processedValue2 = processNutritionValue(key, originalValue2);
    const percentValue2 = calculateDailyValuePercent(key, processedValue2, originalValue2);
    const emphasis2 = checkEmphasisEligibility(key, originalValue2);

    const displayValue1 = processedValue1.includes('미만') ? processedValue1 : `${processedValue1}${data.unit}`;
    const displayValue2 = processedValue2.includes('미만') ? processedValue2 : `${processedValue2}${data.unit}`;

    html += '<tr class="nutrition-row">';
    html += `<td class="nutrition-name${data.indent ? ' nutrition-indent' : ''}">${data.label}</td>`;
    html += `<td class="nutrition-value">${displayValue1}</td><td class="nutrition-percent">${percentValue1 !== null ? `<b>${percentValue1}%</b>` : ''}</td>`;
    html += `<td class="nutrition-value">${displayValue2}</td><td class="nutrition-percent">${percentValue2 !== null ? `<b>${percentValue2}%</b>` : ''}</td>`;
    html += '</tr>';
  });
  
  // 추가 영양성분 표시 (값이 입력된 것만)
  const additionalNutrients = Object.entries(NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && nutritionInputs[key] !== undefined && !NUTRITION_DATA[key].required)
    .sort((a, b) => a[1].order - b[1].order);

  if (additionalNutrients.length > 0) {
    additionalNutrients.forEach(([key, data]) => {
      const originalValue1 = nutritionInputs[key] * multiplier1;
      const processedValue1 = processNutritionValue(key, originalValue1);
      const percentValue1 = calculateDailyValuePercent(key, processedValue1, originalValue1);
      const emphasis1 = checkEmphasisEligibility(key, originalValue1);

      const originalValue2 = nutritionInputs[key] * multiplier2;
      const processedValue2 = processNutritionValue(key, originalValue2);
      const percentValue2 = calculateDailyValuePercent(key, processedValue2, originalValue2);
      const emphasis2 = checkEmphasisEligibility(key, originalValue2);

      const displayValue1 = processedValue1.includes('미만') ? processedValue1 : `${processedValue1}${data.unit}`;
      const displayValue2 = processedValue2.includes('미만') ? processedValue2 : `${processedValue2}${data.unit}`;

      html += '<tr class="nutrition-row">';
      html += `<td class="nutrition-name">${data.label}</td>`;
      html += `<td class="nutrition-value">${displayValue1}</td><td class="nutrition-percent">${percentValue1 !== null ? `<b>${percentValue1}%</b>` : ''}</td>`;
      html += `<td class="nutrition-value">${displayValue2}</td><td class="nutrition-percent">${percentValue2 !== null ? `<b>${percentValue2}%</b>` : ''}</td>`;
      html += '</tr>';
    });
  }
  html += '</tbody>';
  
  // <tfoot>: 하단 안내 문구
  html += '<tfoot>';
  html += '<tr><td colspan="5" class="nutrition-footer">* 1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td></tr>';
  html += '</tfoot>';
  
  html += '</table>';
  
  // 강조표시 검토 결과 추가
  html += generateEmphasisReviewHTML(nutritionInputs);
  
  html += '</div>';
  return html;
}

// 폼 및 부모 창 초기화
function resetFormAndParent() {
  if (confirm('모든 입력 내용을 초기화하시겠습니까?')) {
    // 전역 데이터 먼저 초기화 (검증 방지)
    currentNutritionData = {};
    
    // 영양성분 입력 먼저 초기화 (자동 계산 방지)
    Object.keys(NUTRITION_DATA).forEach(key => {
      const input = document.getElementById(key);
      if (input) {
        input.value = '';
      }
    });
    
    // 기본 설정 초기화 (이제 영양성분이 비어있어서 자동 계산 안됨)
    document.getElementById('base_amount').value = '100';
    document.getElementById('servings_per_package').value = '1';
    document.getElementById('nutrition_style').value = 'basic';
    
    // 스타일 옵션 토글 (이제 안전하게 호출 가능)
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
    
    // 결과 초기화
    document.getElementById('resultDisplay').innerHTML = '';
    
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
  
  // 결과 영역에서 영양성분표만 PDF로 변환
  const resultDisplay = document.getElementById('resultDisplay');
  
  if (!resultDisplay || !resultDisplay.innerHTML.trim() || resultDisplay.innerHTML.trim() === '') {
    alert('영양성분 계산 결과가 없습니다.');
    pdfButton.disabled = false;
    pdfButton.innerHTML = originalText;
    return;
  }
  
  // 영양성분표만 선택 (강조표시 검토결과 제외)
  const nutritionTable = resultDisplay.querySelector('.nutrition-table');
  const nutritionContainer = nutritionTable ? nutritionTable.closest('div') : null;
  
  if (!nutritionContainer) {
    alert('영양성분표를 찾을 수 없습니다.');
    pdfButton.disabled = false;
    pdfButton.innerHTML = originalText;
    return;
  }
  
  // html2canvas로 영양성분표만 이미지로 변환
  html2canvas(nutritionContainer, {
    scale: 2, // 고해상도
    useCORS: true,
    backgroundColor: '#ffffff',
    logging: false,
    allowTaint: true,
    foreignObjectRendering: true,
    ignoreElements: function(element) {
      // 강조표시 검토결과 영역 제외
      return element.classList && (
        element.classList.contains('emphasis-review-section') ||
        element.classList.contains('no-pdf')
      );
    }
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
      
      // 영양성분표 스타일 확인
      const nutritionStyle = document.getElementById('nutrition_style').value;
      let styleText = '';
      switch (nutritionStyle) {
        case 'basic':
          styleText = '기본형';
          break;
        case 'vertical':
          styleText = '세로형';
          break;
        case 'parallel':
          styleText = '병행';
          break;
        default:
          styleText = '기본형';
      }
      
      // 파일명 구성: 영양성분표(스타일)_제품명_연월일
      let fileName = `영양성분표(${styleText})`;
      
      // 제품명 추가 (특수문자 제거)
      if (productName) {
        const cleanProductName = productName.replace(/[<>:"/\\|?*]/g, '').trim();
        if (cleanProductName) {
          fileName += `_${cleanProductName}`;
        }
      }
      fileName += `_${dateStr}`;
      
      // 제목 추가
      pdf.setFontSize(16);
      pdf.text(`영양성분표(${styleText})`, 105, 20, { align: 'center' });
      
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
    
    // 자동 계산 (영양성분 데이터가 실제로 있는 경우에만)
    if (data.base_amount && data.servings_per_package) {
      // 영양성분 데이터가 하나라도 있는지 확인
      const hasNutritionData = Object.keys(NUTRITION_DATA).some(key => {
        const input = document.getElementById(key);
        return input && input.value && input.value.trim() !== '';
      });
      
      if (hasNutritionData) {
        calculateNutrition();
      }
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
