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

// 전역 데이터 초기화
let phrasesData = {};
let regulations = {};
let lastFocusedFieldName = null;
let phraseInsertMode = 'append';

// ------------------ 체크박스 필드 매핑 (전역) ------------------
const fieldMappings = {
  // updateCheckboxesByFoodType에서 사용하는 id 매핑
  prdlst_dcnm: 'chk_prdlst_dcnm',
  rawmtrl_nm: 'chk_rawmtrl_nm_display',
  nutritions: 'chk_calories',
  prdlst_nm: 'chk_prdlst_nm',
  ingredients_info: 'chk_ingredients_info',
  content_weight: 'chk_content_weight',
  weight_calorie: 'chk_weight_calorie',
  prdlst_report_no: 'chk_prdlst_report_no',
  country_of_origin: 'chk_country_of_origin',
  storage_method: 'chk_storage_method',
  frmlc_mtrqlt: 'chk_frmlc_mtrqlt',
  manufacturer_info: 'chk_manufacturer_info',
  distributor_address: 'chk_distributor_address',
  repacker_address: 'chk_repacker_address',
  importer_address: 'chk_importer_address',
  date_info: 'chk_date_info',
  cautions: 'chk_cautions',
  additional_info: 'chk_additional_info',
  // initCheckboxFieldToggle에서 사용하는 필드 매핑 (배열 형태)
  label_nm: ['input[name="my_label_name"]'],
  prdlst_dcnm_arr: ['input[name="prdlst_dcnm"]'],
  prdlst_nm_arr: ['input[name="prdlst_nm"]'],
  ingredients_info_arr: ['input[name="ingredient_info"]'],  content_weight_arr: ['input[name="content_weight"]', 'input[name="weight_calorie"]'],
  weight_calorie_arr: ['input[name="weight_calorie"]'],
  prdlst_report_no_arr: ['input[name="prdlst_report_no"]'],
  country_of_origin_arr: ['select[name="country_of_origin"]'],
  storage_method_arr: ['input[name="storage_method"]'],
  frmlc_mtrqlt_arr: ['input[name="frmlc_mtrqlt"]'],
  manufacturer_info_arr: ['input[name="bssh_nm"]'],
  distributor_address_arr: ['input[name="distributor_address"]'],
  repacker_address_arr: ['input[name="repacker_address"]'],
  importer_address_arr: ['input[name="importer_address"]'],
  date_info_arr: ['input[name="pog_daycnt"]', 'select[name="date_option"]'],
  rawmtrl_nm_display_arr: ['textarea[name="rawmtrl_nm_display"]'],
  rawmtrl_nm_arr: ['textarea[name="rawmtrl_nm"]'],
  cautions_arr: ['textarea[name="cautions"]'],
  additional_info_arr: ['textarea[name="additional_info"]'],
  calories_arr: ['textarea[name="nutrition_text"]']
};

// DOMContentLoaded 이벤트로 초기화 보장
document.addEventListener('DOMContentLoaded', function () {
  // 데이터 초기화
  try {
    phrasesData = JSON.parse(document.getElementById('phrases-data')?.textContent || '{}');
    regulations = JSON.parse(document.getElementById('regulations-data')?.textContent || '{}');
  } catch (e) {
    console.error('데이터 파싱 오류:', e);
  }
  
  // 🎯 성능 최적화된 textarea 자동 높이 조절 초기화 함수
  function initializeAllTextareas() {
    // 중복 실행 방지
    if (window.textareaInitializedInJS) {
      console.log('⚠️ JS파일의 textarea 초기화 이미 완료 - 중복 실행 방지');
      return;
    }
    window.textareaInitializedInJS = true;
    console.log('🎯 성능 최적화된 textarea 자동 높이 조절 초기화');
    
    // 🚫 팝업 전용 필드들 (자동 높이 조절 제외)
    const popupOnlyFields = [
      'textarea[name="rawmtrl_nm"]',     // 원재료명(참고) - 팝업 전용
      'textarea[name="nutrition_text"]'  // 영양성분 - 팝업 전용
    ];
    
    // 일반 처리 필드들
    const regularTextareas = [
      'textarea[name="rawmtrl_nm_display"]',
      'textarea[name="caution"]',
      'textarea[name="etc_info"]'
    ];
    
    // 모든 textarea에 이벤트 리스너 및 초기 높이 설정
    document.querySelectorAll('textarea').forEach(textarea => {
      // 이미 처리된 요소는 건너뛰기
      if (textarea.dataset.heightInitialized) return;
      
      // 팝업 전용 필드는 자동 높이 조절에서 제외
      const isPopupOnly = popupOnlyFields.some(selector => textarea.matches(selector));
      if (isPopupOnly) {
        console.log(`🚫 팝업 전용 필드 제외: ${textarea.name}`);
        textarea.dataset.heightInitialized = 'popup-only';
        return;
      }
      
      // 높이 초기화
      adjustHeight(textarea);
      
      // 이벤트 리스너 등록
      textarea.addEventListener('input', () => adjustHeight(textarea));
      textarea.addEventListener('paste', () => setTimeout(() => adjustHeight(textarea), 10));
      textarea.addEventListener('focus', () => adjustHeight(textarea));
      
      // 처리 표시
      textarea.dataset.heightInitialized = 'true';
      
      // 특별 관심 요소는 추가 처리
      if (regularTextareas.some(selector => textarea.matches(selector))) {
        // 강제로 인라인 스타일 적용
        const currentScrollHeight = textarea.scrollHeight;
        const styleText = `
          height: ${Math.max(48, currentScrollHeight)}px !important; 
          min-height: 48px !important; 
          max-height: none !important; 
          overflow-y: hidden !important;
          box-sizing: content-box !important;
          display: block !important;
        `;
        textarea.style.cssText = styleText;
        
        // 컨테이너도 조정
        const containers = [
          textarea.closest('.input-container-modern'),
          textarea.closest('.field-input-section'),
          textarea.closest('.field-row-modern')
        ];
        
        containers.forEach((container, index) => {
          if (container) {
            container.style.cssText = `
              height: auto !important;
              min-height: auto !important;
              max-height: none !important;
              overflow: visible !important;
              display: flex !important;
              align-items: flex-start !important;
            `;
          }
        });
      }
    });
    
    console.log('✅ 모든 textarea 자동 높이 조절 초기화 완료');
  }
  
  // 🚫 성능 최적화: 중복 실행 방지를 위해 전역 초기화 체크 추가
  if (!window.textareaSystemGloballyInitialized) {
    window.textareaSystemGloballyInitialized = true;
    console.log('🎯 전역 textarea 시스템 한 번만 초기화');
    initializeAllTextareas();
  } else {
    console.log('⚠️ Textarea 시스템이 이미 전역 초기화됨 - 중복 실행 방지');
  }
  
  // 🚫 성능 최적화: setInterval 제거 (과도한 서버 부하 방지)
  // setInterval(initializeAllTextareas, 1000);
  
  // 🚫 성능 최적화: MutationObserver 제거 (과도한 DOM 감시로 인한 성능 저하 방지)
  // const observer = new MutationObserver(() => {
  //   setTimeout(initializeAllTextareas, 100);
  // });
  // observer.observe(document.body, { childList: true, subtree: true });
  
  console.log('✅ 성능 최적화 완료: 중복 실행 및 과도한 DOM 감시 제거');

  // ------------------ 공통 유틸리티 함수 ------------------
  // CSRF 토큰 쿠키값을 얻는 함수 (Django 공식)
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

  // 강화된 textarea 높이 조절 함수 - 인라인 스타일 우선순위 최대화
  function adjustHeight(element, maxHeight = Infinity) {
    if (!element) return;
    
    // 계산을 위해 모든 스타일 속성 초기화
    element.setAttribute('style', '');
    element.style.cssText = 'height: 1px !important; min-height: 0 !important; max-height: none !important; overflow: hidden !important;';
    
    // 실제 필요한 높이 계산
    const scrollHeight = element.scrollHeight;
    const minHeight = 48; // 기본 2줄 높이
    
    // 최종 높이 결정
    let newHeight = Math.max(minHeight, scrollHeight);
    if (newHeight > maxHeight) {
      newHeight = maxHeight;
      element.style.overflowY = 'auto';
    } else {
      element.style.overflowY = 'hidden';
    }
    
    // 높이 강제 적용 - 최우선 인라인 스타일
    const styleText = `
      height: ${newHeight}px !important; 
      min-height: ${minHeight}px !important; 
      max-height: none !important; 
      overflow-y: ${newHeight > maxHeight ? 'auto' : 'hidden'} !important;
      box-sizing: content-box !important;
      display: block !important;
      position: relative !important;
      z-index: 100 !important;
    `;
    
    element.style.cssText = styleText;
    
    // 🚨 컨테이너들도 함께 강제 조정
    const containers = [
      element.closest('.input-container-modern'),
      element.closest('.field-input-section'),
      element.closest('.field-row-modern')
    ];
    
    containers.forEach((container, index) => {
      if (container) {
        const containerStyle = `
          height: auto !important;
          min-height: auto !important;
          max-height: none !important;
          overflow: visible !important;
          display: flex !important;
          align-items: flex-start !important;
          position: relative !important;
          z-index: ${90 - index} !important;
        `;
        container.style.cssText = containerStyle;
      }
    });
    
    console.log(`📏 ${element.name || 'textarea'}: ${scrollHeight}px → ${newHeight}px + 컨테이너 강제 조정`);
  }

  function adjustRegulationBoxHeight(textarea) {
    const container = document.getElementById('regulation-content');
    if (!container || !textarea) return;
    textarea.style.height = 'auto';
    const tabContent = container.closest('.tab-content');
    const maxHeight = tabContent ? tabContent.clientHeight * 0.9 : window.innerHeight * 0.6;
    const scrollHeight = textarea.scrollHeight + 10;
    container.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
    container.style.overflowY = scrollHeight > maxHeight ? 'auto' : 'hidden';
    textarea.style.height = '100%';
    textarea.style.resize = 'none';
  }

  window.updateTextareaHeight = function (textarea) {
    if (!textarea) {
      console.warn('⚠️ updateTextareaHeight: textarea 요소가 없습니다');
      return;
    }
    
    const name = textarea.name || textarea.id || 'unnamed';
    console.log(`📏 textarea 높이 조절 시작: ${name}`);
    
    const isRegulation = textarea.name === 'related_regulations';
    const maxHeight = Infinity; // 모든 textarea 높이 제한 제거
    
    adjustHeight(textarea, maxHeight);
    
    if (isRegulation) {
      adjustRegulationBoxHeight(textarea);
    }
    
    console.log(`✅ textarea 높이 조절 완료: ${name}`);
  };
  
  // 디버깅용 전역 함수
  window.testTextareaResize = function() {
    console.log('🧪 모든 textarea 강제 리사이즈 테스트');
    document.querySelectorAll('textarea').forEach((textarea, index) => {
      console.log(`${index + 1}. ${textarea.name || textarea.id || 'unnamed'}`);
      window.updateTextareaHeight(textarea);
    });
  };

  // 🚫 성능 최적화된 auto-expand 초기화 (중복 실행 방지)
  function initAutoExpand() {
    // 중복 실행 방지
    if (window.autoExpandInitialized) {
      console.log('⚠️ Auto-expand 이미 초기화됨 - 중복 실행 방지');
      return;
    }
    window.autoExpandInitialized = true;
    console.log('🎯 성능 최적화된 Auto-expand 초기화');
    
    function setupAllTextareas() {
      const textareas = document.querySelectorAll('textarea');
      console.log(`📊 textarea 개수: ${textareas.length}`);
      
      textareas.forEach(textarea => {
        // 팝업 전용 필드는 자동 높이 조절에서 제외
        const isPopupOnly = textarea.matches('textarea[name="rawmtrl_nm"], textarea[name="nutrition_text"]');
        if (isPopupOnly) {
          console.log(`🚫 Auto-expand 제외: ${textarea.name} (팝업 전용)`);
          return;
        }
        
        if (!textarea.hasAttribute('data-auto-expand')) {
          textarea.setAttribute('data-auto-expand', 'true');
          
          // 초기 높이 설정
          adjustHeight(textarea);
          
          // 이벤트 리스너 추가
          textarea.addEventListener('input', function() {
            adjustHeight(this);
          });
          
          textarea.addEventListener('paste', function() {
            setTimeout(() => adjustHeight(this), 0);
          });
          
          console.log(`✅ ${textarea.name || textarea.id || 'textarea'} 설정 완료`);
        }
      });
    }
    
    // 즉시 실행
    setupAllTextareas();
    
    // 🚫 성능 최적화: DOM 변경 감지 제거 (과도한 감시로 인한 성능 저하 방지)
    // const observer = new MutationObserver(() => {
    //   setupAllTextareas();
    // });
    // observer.observe(document.body, { childList: true, subtree: true });
    
    console.log('✅ 성능 최적화된 Auto-expand 초기화 완료');
  }

  // 팝업 전용 필드 높이 조절 함수 (팝업에서 데이터 반환 시 실행)
  window.adjustPopupFieldHeight = function(fieldName) {
    const textarea = document.querySelector(`textarea[name="${fieldName}"]`);
    if (textarea && (fieldName === 'rawmtrl_nm' || fieldName === 'nutrition_text')) {
      console.log(`📐 팝업 데이터 반환 후 높이 조절: ${fieldName}`);
      adjustHeight(textarea);
    }
  };

  // ------------------ 라벨 관리 기능 ------------------
  window.copyLabel = function (labelId) {
    if (!labelId) return alert('복사할 라벨이 없습니다.');
    if (confirm('현재 라벨을 복사하시겠습니까?')) {
      window.location.href = `/label/duplicate/${labelId}/`;
    }
  };

  window.deleteLabel = function (labelId) {
    if (!labelId) return alert('삭제할 라벨이 없습니다.');
    if (confirm('정말로 이 라벨을 삭제하시겠습니까? 복구할 수 없습니다.')) {
      window.location.href = `/label/delete/${labelId}/`;
    }
  };

  // ------------------ 팝업 로직 ------------------
  window.openPopup = function (url, name, width = 1100, height = 900) {
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    const popup = window.open(url, name, `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`);
    if (!popup) {
      alert('팝업이 차단되었습니다. 브라우저의 팝업 차단 설정을 확인해 주세요.');
    }
    return popup;
  };

  window.handleIngredientPopup = function () {
    const labelId = document.getElementById('label_id')?.value || '';
    openPopup(`/label/ingredient-popup/?label_id=${labelId}`, 'IngredientPopup', 1400, 900);
    const rawmtrlSection = document.getElementById('rawmtrl_nm_section');
    if (rawmtrlSection?.classList.contains('collapse')) {
      rawmtrlSection.classList.add('show');
    }
  };

  window.openNutritionCalculator = function () {
    const labelId = document.getElementById('label_id')?.value || '';
    openPopup(`/label/nutrition-calculator-popup/?label_id=${labelId}`, 'NutritionCalculator', 1100, 900);
  };

  // DOMContentLoaded 이벤트 리스너 추가
  document.addEventListener('DOMContentLoaded', function() {
    // 페이지 로드 시 영양성분 필드 상태 확인
    checkNutritionFieldStatus();
  });

  window.addEventListener('message', function(event) {
    // 보안 검증 (필요시 도메인 체크)
    // if (event.origin !== 'https://yourdomain.com') return;
    
    if (event.data && event.data.type === 'nutritionData') {
      console.log('팝업에서 영양성분 데이터 수신:', event.data);
      
      // 팝업 데이터를 부모창이 기대하는 형식으로 변환
      const popupData = event.data.data;
      const convertedData = convertPopupDataToParentFormat(popupData);
      
      // 기존 handleNutritionDataUpdate 함수 호출
      handleNutritionDataUpdate(convertedData);
    }
    else if (event.data && event.data.type === 'nutritionReset') {
      console.log('팝업에서 영양성분 초기화 요청 수신');
      // 기존 handleNutritionDataReset 함수 호출
      handleNutritionDataReset();
    }
  });



  // 팝업에서 부모창의 기존 영양성분 데이터를 받아갈 수 있도록 함수 추가
  window.getNutritionDataForPopup = function() {
    // 기존 영양성분 데이터 수집 함수 활용
    const data = collectExistingNutritionData();
    
    console.log('getNutritionDataForPopup - 원본 수집 데이터:', data);
    
    // 모든 영양성분 필드에서 값이 '0'이면 빈 값으로 처리
    const allNutritionFields = [
      // 9대 영양성분
      'calories', 'natriums', 'carbohydrates', 'sugars', 'fats',
      'trans_fats', 'saturated_fats', 'cholesterols', 'proteins',
      // 추가 영양성분
      'dietary_fiber', 'calcium', 'iron', 'potassium', 'magnesium', 
      'zinc', 'phosphorus', 'vitamin_a', 'vitamin_d', 'vitamin_e',
      'vitamin_c', 'thiamine', 'riboflavin', 'niacin', 'vitamin_b6',
      'folic_acid', 'vitamin_b12', 'selenium', 'pantothenic_acid', 'biotin', 'iodine',
      'vitamin_k', 'copper', 'manganese', 'chromium', 'molybdenum'
    ];
    
    allNutritionFields.forEach(field => {
      if (data[field] === '0' || data[field] === 0) {
        data[field] = '';
      }
    });
    
    // 부모창 필드명을 팝업 필드명으로 변환
    const convertedData = {};
    
    // 기본 설정값들
    convertedData.serving_size = data.serving_size;
    convertedData.serving_size_unit = data.serving_size_unit;
    convertedData.units_per_package = data.units_per_package;
    convertedData.nutrition_display_unit = data.nutrition_display_unit;
    
    // 영양성분 필드명 변환 (부모창 → 팝업)
    const fieldNameMapping = {
      'calories': 'calories',
      'natriums': 'sodium',  // 중요: natriums → sodium
      'carbohydrates': 'carbohydrate',
      'sugars': 'sugars',
      'fats': 'fat',
      'trans_fats': 'trans_fat',
      'saturated_fats': 'saturated_fat',
      'cholesterols': 'cholesterol',
      'proteins': 'protein',
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
      'thiamine': 'thiamine',      // vitamin_b1 → thiamine
      'riboflavin': 'riboflavin',  // vitamin_b2 → riboflavin
      'niacin': 'niacin',
      'vitamin_b6': 'vitamin_b6',
      'folic_acid': 'folic_acid',
      'vitamin_b12': 'vitamin_b12',
      'selenium': 'selenium',
      'pantothenic_acid': 'pantothenic_acid',
      'biotin': 'biotin',
      'iodine': 'iodine',
      'vitamin_k': 'vitamin_k',
      'copper': 'copper',
      'manganese': 'manganese',
      'chromium': 'chromium',
      'molybdenum': 'molybdenum'
    };
    
    // 필드명 변환하여 데이터 복사
    Object.keys(fieldNameMapping).forEach(parentField => {
      const popupField = fieldNameMapping[parentField];
      if (data[parentField] !== undefined && data[parentField] !== null && data[parentField] !== '') {
        convertedData[popupField] = data[parentField];
      }
    });
    
    // 추가적으로 필요한 데이터가 있으면 여기에 포함
    convertedData.product_name = document.querySelector('input[name="prdlst_nm"]')?.value || '';
    
    console.log('🔍 getNutritionDataForPopup - 원본 데이터:', JSON.stringify(data, null, 2));
    console.log('🔍 getNutritionDataForPopup - 변환된 데이터:', JSON.stringify(convertedData, null, 2));
    console.log('🔍 변환된 데이터 키들:', Object.keys(convertedData));
    console.log('🔍 변환된 calories:', convertedData.calories);
    console.log('🔍 변환된 sodium:', convertedData.sodium);
    
    // 팝업에서 필요한 형식에 맞게 반환
    return convertedData;
  };

  // 팝업 데이터를 부모창 형식으로 변환하는 함수
  function convertPopupDataToParentFormat(popupData) {
    const convertedData = {};
    
    // 기본 설정 데이터 변환
    convertedData.settings = {
      base_amount: popupData.baseAmount,
      base_amount_unit: 'g', // 기본값
      servings_per_package: popupData.servingsPerPackage,
      nutrition_style: popupData.style,
      display_type: 'basic' // 기본값
    };
    
    // 영양성분 데이터 변환
    if (popupData.nutritionInputs) {
      convertedData.formattedData = {};
      
      Object.entries(popupData.nutritionInputs).forEach(([key, item]) => {
        // NUTRITION_DATA에서 order 정보 가져오기 (팝업의 NUTRITION_DATA 참조)
        const nutritionOrder = {
          'calories': 1, 'sodium': 2, 'carbohydrate': 3, 'sugars': 4,
          'fat': 5, 'saturated_fat': 6, 'trans_fat': 7, 'cholesterol': 8, 'protein': 9,
          // 추가 영양성분
          'dietary_fiber': 10, 'calcium': 11, 'iron': 12, 'potassium': 13, 'magnesium': 14,
          'zinc': 15, 'phosphorus': 16, 'vitamin_a': 17, 'vitamin_d': 18, 'vitamin_e': 19,
          'vitamin_c': 20, 'vitamin_b1': 21, 'vitamin_b2': 22, 'vitamin_b6': 23, 'vitamin_b12': 24,
          'folic_acid': 25, 'niacin': 26, 'pantothenic_acid': 27, 'biotin': 28, 'selenium': 29, 'iodine': 30
        };
        
        convertedData.formattedData[key] = {
          label: item.label,
          value: item.value,
          unit: item.unit,
          order: nutritionOrder[key] || 99
        };
      });
    }
    
    // HTML 결과 추가
    if (popupData.html) {
      convertedData.resultHTML = popupData.html;
    }
    
    console.log('변환된 데이터:', convertedData);
    return convertedData;
  }           

  // 영양성분 계산기 중복 실행 방지 플래그
  let nutritionPopupProcessing = false;
  
  window.handleNutritionTablePopup = function () {
    // 중복 실행 방지
    if (nutritionPopupProcessing) {
      console.log('영양성분 계산기가 이미 처리 중입니다.');
      return;
    }
    
    nutritionPopupProcessing = true;
    
    try {
      const labelId = document.getElementById('label_id')?.value || '';
      
      // 기존 영양성분 데이터 수집
      const existingData = collectExistingNutritionData();
    
    // 제품명 추가
    const productNameField = document.querySelector('input[name="prdlst_nm"]');
    if (productNameField && productNameField.value.trim()) {
      existingData.product_name = productNameField.value.trim();
    }
    
    // 팝업 URL에 기존 데이터 파라미터 추가
    let url = `/label/nutrition-calculator-popup/?label_id=${labelId}`;
    if (existingData && Object.keys(existingData).length > 0) {
      const params = new URLSearchParams();
      Object.keys(existingData).forEach(key => {
        if (existingData[key]) {
          params.append(key, existingData[key]);
        }
      });
      url += '&' + params.toString();
    }
    
    openPopup(url, 'NutritionCalculator', 1100, 900);
    
    } catch (error) {
      console.error('영양성분 계산기 열기 오류:', error);
    } finally {
      // 2초 후 플래그 해제 (팝업 열기 완료 대기)
      setTimeout(() => {
        nutritionPopupProcessing = false;
      }, 2000);
    }
  };

  // 기존 영양성분 데이터 수집
  function collectExistingNutritionData() {
    const data = {};
    
    // hidden 필드에서 기존 데이터 수집
    const fieldMapping = {
      // 기본 설정값
      'serving_size': 'serving_size',
      'serving_size_unit': 'serving_size_unit', 
      'units_per_package': 'units_per_package',
      'nutrition_style': 'nutrition_style',
      'nutrition_display_type': 'nutrition_display_type',
      'nutrition_base_amount': 'nutrition_base_amount',
      'nutrition_base_amount_unit': 'nutrition_base_amount_unit',
      // 9대 영양성분 (메인 페이지 필드명 -> URL 파라미터명)
      'calories': 'calories',
      'natriums': 'natriums',
      'carbohydrates': 'carbohydrates',
      'sugars': 'sugars',
      'fats': 'fats',
      'trans_fats': 'trans_fats',
      'saturated_fats': 'saturated_fats',
      'cholesterols': 'cholesterols',
      'proteins': 'proteins',
      // 추가 영양성분들
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
      'vitamin_b1': 'thiamine',  // 실제 필드명은 vitamin_b1이지만 팝업에서는 thiamine으로 사용
      'vitamin_b2': 'riboflavin', // 실제 필드명은 vitamin_b2이지만 팝업에서는 riboflavin으로 사용
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
    
    Object.keys(fieldMapping).forEach(fieldName => {
      // 다양한 선택자로 필드 검색
      let field = document.querySelector(`input[name="${fieldName}"]`);
      
      // name 속성으로 찾지 못했으면 id로 시도
      if (!field) {
        field = document.getElementById(fieldName);
      }
      
      // 여전히 못 찾았으면 data 속성으로 시도
      if (!field) {
        field = document.querySelector(`input[data-field="${fieldName}"]`);
      }
      
      if (field && field.value && field.value.trim() !== '' && field.value.trim() !== '0') {
        data[fieldMapping[fieldName]] = field.value.trim();
      }
      
      // 단위 필드도 함께 수집 (영양성분들만)
      const isNutrient = !['serving_size', 'serving_size_unit', 'units_per_package', 'nutrition_style', 'nutrition_display_type', 'nutrition_base_amount', 'nutrition_base_amount_unit'].includes(fieldName);
      if (isNutrient) {
        let unitField = document.querySelector(`input[name="${fieldName}_unit"]`);
        if (!unitField) {
          unitField = document.getElementById(`${fieldName}_unit`);
        }
        if (unitField && unitField.value && unitField.value.trim() !== '') {
          data[fieldMapping[fieldName] + '_unit'] = unitField.value.trim();
        }
      }
    });
    
    return data;
  }

  // 영양성분 데이터 업데이트 처리
  function handleNutritionDataUpdate(data) {
    console.log('영양성분 데이터 수신:', data);
    
    // 기본 설정 데이터 저장
    if (data.settings) {
      console.log('기본 설정 데이터 처리:', data.settings);
      // 기본 정보 필드 업데이트
      const servingSizeField = document.querySelector('input[name="serving_size"]');
      const servingSizeUnitField = document.querySelector('input[name="serving_size_unit"]');
      const unitsPerPackageField = document.querySelector('input[name="units_per_package"]');
      const nutritionStyleField = document.querySelector('input[name="nutrition_style"]');
      const nutritionDisplayTypeField = document.querySelector('input[name="nutrition_display_type"]');
      const nutritionBaseAmountField = document.querySelector('input[name="nutrition_base_amount"]');
      const nutritionBaseAmountUnitField = document.querySelector('input[name="nutrition_base_amount_unit"]');
      
      console.log('필드 찾기 결과:', {
        servingSizeField, servingSizeUnitField, unitsPerPackageField,
        nutritionStyleField, nutritionDisplayTypeField, nutritionBaseAmountField, nutritionBaseAmountUnitField
      });
      
      if (servingSizeField) servingSizeField.value = data.settings.base_amount || '';
      if (servingSizeUnitField) servingSizeUnitField.value = data.settings.base_amount_unit || 'g';
      if (unitsPerPackageField) unitsPerPackageField.value = data.settings.servings_per_package || '1';
      if (nutritionStyleField) nutritionStyleField.value = data.settings.nutrition_style || '';
      if (nutritionDisplayTypeField) nutritionDisplayTypeField.value = data.settings.display_type || '';
      if (nutritionBaseAmountField) nutritionBaseAmountField.value = data.settings.base_amount || '';
      if (nutritionBaseAmountUnitField) nutritionBaseAmountUnitField.value = data.settings.base_amount_unit || 'g';
    }
    
    // 포맷된 영양성분 데이터를 hidden 필드에 저장
    if (data.formattedData) {
      console.log('포맷된 영양성분 데이터 처리:', data.formattedData);
      const nutritionMapping = {
        'calories': 'calories',
        'sodium': 'natriums',
        'carbohydrate': 'carbohydrates',
        'sugars': 'sugars',
        'fat': 'fats',
        'trans_fat': 'trans_fats',
        'saturated_fat': 'saturated_fats',
        'cholesterol': 'cholesterols',
        'protein': 'proteins',
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
        'vitamin_b1': 'vitamin_b1',
        'vitamin_b2': 'vitamin_b2',
        'vitamin_b6': 'vitamin_b6',
        'vitamin_b12': 'vitamin_b12',
        'folic_acid': 'folic_acid',
        'niacin': 'niacin',
        'pantothenic_acid': 'pantothenic_acid',
        'biotin': 'biotin',
        'selenium': 'selenium',
        'iodine': 'iodine'
      };
      
      Object.keys(nutritionMapping).forEach(key => {
        if (data.formattedData[key]) {
          const fieldName = nutritionMapping[key];
          const valueField = document.querySelector(`input[name="${fieldName}"]`);
          const unitField = document.querySelector(`input[name="${fieldName}_unit"]`);
          
          console.log(`${key} -> ${fieldName}:`, { valueField, unitField, value: data.formattedData[key] });
          
          if (valueField) valueField.value = data.formattedData[key].value || '';
          if (unitField) unitField.value = data.formattedData[key].unit || '';
        }
      });
    }
    
    // 영양성분 텍스트 필드에 결과 HTML을 텍스트로 변환하여 저장
    if (data.resultHTML) {
      console.log('영양성분 텍스트 처리:', data.resultHTML);
      const nutritionTextField = document.querySelector('textarea[name="nutrition_text"]');
      console.log('영양성분 텍스트 필드:', nutritionTextField);
      
      if (nutritionTextField) {
        // 포맷된 데이터를 쉼표로 구분된 형태로 변환
        const nutritionItems = [];
        
        // 기준 정보 추가
        if (data.settings && data.settings.base_amount) {
          const baseInfo = `기준: ${data.settings.base_amount}${data.settings.base_amount_unit || 'g'}당`;
          if (data.settings.servings_per_package && data.settings.servings_per_package !== '1') {
            nutritionItems.push(`${baseInfo} (총 ${data.settings.servings_per_package}회분)`);
          } else {
            nutritionItems.push(baseInfo);
          }
        }
        
        if (data.formattedData) {
          // 순서대로 정렬
          const orderedKeys = Object.keys(data.formattedData).sort((a, b) => {
            return data.formattedData[a].order - data.formattedData[b].order;
          });
          
          orderedKeys.forEach(key => {
            const item = data.formattedData[key];
            if (item.value !== undefined && item.value !== null && item.value !== '') {
              const valueStr = typeof item.value === 'number' ? item.value.toString() : item.value;
              nutritionItems.push(`${item.label} ${valueStr}${item.unit || ''}`);
            }
          });
        }
        
        const nutritionText = nutritionItems.join(', ');
        nutritionTextField.value = nutritionText;
        console.log('쉼표로 구분된 영양성분 텍스트:', nutritionText);
        
        // 텍스트 필드를 읽기 전용으로 설정
        nutritionTextField.readOnly = true;
        nutritionTextField.style.backgroundColor = '#f8f9fa';
        nutritionTextField.style.cursor = 'not-allowed';
        
        // 팝업 전용 필드 높이 조절
        if (window.adjustPopupFieldHeight) {
          adjustPopupFieldHeight('nutrition_text');
        }
        
        // 영양성분 체크박스 자동 체크
        const nutritionCheckbox = document.querySelector('input[name="chk_nutrition_text"]');
        if (nutritionCheckbox) {
          nutritionCheckbox.checked = true;
          console.log('영양성분 체크박스 체크됨');
        }
        
        // 계산기 버튼 텍스트 변경
        const nutritionButton = document.querySelector('button[onclick="handleNutritionTablePopup()"]');
        if (nutritionButton) {
          nutritionButton.innerHTML = '<i class="fas fa-edit me-1"></i>영양성분 수정';
          nutritionButton.title = '영양성분 수정';
        }
      }
    }
    
    console.log('영양성분 데이터가 성공적으로 저장되었습니다.');
  }
  
  // 영양성분 데이터 초기화 처리
  function handleNutritionDataReset() {
    console.log('영양성분 데이터 초기화');
    
    // 영양성분 텍스트 필드 초기화 및 읽기 전용 해제
    const nutritionTextField = document.querySelector('textarea[name="nutrition_text"]');
    if (nutritionTextField) {
      nutritionTextField.value = '';
      nutritionTextField.readOnly = false;
      nutritionTextField.style.backgroundColor = '';
      nutritionTextField.style.cursor = '';
      
      // 팝업 전용 필드 높이 조절
      if (window.adjustPopupFieldHeight) {
        adjustPopupFieldHeight('nutrition_text');
      }
    }
    
    // hidden 필드들 초기화
    const fieldNames = [
      'serving_size', 'serving_size_unit', 'units_per_package',
      'nutrition_style', 'nutrition_display_type', 'nutrition_base_amount', 'nutrition_base_amount_unit',
      'calories', 'calories_unit', 'natriums', 'natriums_unit',
      'carbohydrates', 'carbohydrates_unit', 'sugars', 'sugars_unit',
      'fats', 'fats_unit', 'trans_fats', 'trans_fats_unit',
      'saturated_fats', 'saturated_fats_unit', 'cholesterols', 'cholesterols_unit',
      'proteins', 'proteins_unit',
      // 추가 영양성분 초기화
      'dietary_fiber', 'dietary_fiber_unit', 'calcium', 'calcium_unit', 'iron', 'iron_unit',
      'potassium', 'potassium_unit', 'magnesium', 'magnesium_unit', 'zinc', 'zinc_unit',
      'phosphorus', 'phosphorus_unit', 'vitamin_a', 'vitamin_a_unit', 'vitamin_d', 'vitamin_d_unit',
      'vitamin_e', 'vitamin_e_unit', 'vitamin_c', 'vitamin_c_unit', 'vitamin_b1', 'vitamin_b1_unit',
      'vitamin_b2', 'vitamin_b2_unit', 'vitamin_b6', 'vitamin_b6_unit', 'vitamin_b12', 'vitamin_b12_unit',
      'folic_acid', 'folic_acid_unit', 'niacin', 'niacin_unit', 'pantothenic_acid', 'pantothenic_acid_unit',
      'biotin', 'biotin_unit', 'selenium', 'selenium_unit', 'iodine', 'iodine_unit'
    ];
    
    fieldNames.forEach(fieldName => {
      const field = document.querySelector(`input[name="${fieldName}"]`);
      if (field) field.value = '';
    });
    
    // 계산기 버튼 텍스트 원래대로 변경
    const nutritionButton = document.querySelector('button[onclick="handleNutritionTablePopup()"]');
    if (nutritionButton) {
      nutritionButton.innerHTML = '<i class="fas fa-table me-1"></i>영양성분표';
      nutritionButton.title = '영양성분표';
    }
    
    // 영양성분 체크박스 해제
    const nutritionCheckbox = document.querySelector('input[name="chk_nutrition_text"]');
    if (nutritionCheckbox) {
      nutritionCheckbox.checked = false;
    }
  }
  
  // HTML에서 영양성분 텍스트 추출
  function extractNutritionText(htmlElement) {
    const tables = htmlElement.querySelectorAll('table');
    let result = '';
    
    tables.forEach(table => {
      const rows = table.querySelectorAll('tr');
      rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length > 0) {
          const rowText = Array.from(cells).map(cell => cell.textContent.trim()).join(' ');
          if (rowText) {
            result += rowText + '\n';
          }
        }
      });
    });
    
    return result.trim();
  }

  window.openPhrasePopup = function () {
    openPopup('/label/phrases/', 'phrasePopup', 1100, 900);
  };

  window.openPreviewPopup = function() {
    const form = document.getElementById("labelForm");
    if (!form) {
        return;
    }
    let labelId = null;
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('label_id')) {
        labelId = urlParams.get('label_id');
    } else {
        labelId = document.getElementById('label_id')?.value;
    }
    if (!labelId) {
        alert('라벨을 먼저 저장해주세요.');
        return;
    }
    const url = `/label/preview/?label_id=${labelId}`;
    const width = 1100;
    const height = 900;
    const left = (window.innerWidth - width) / 2;
    const top = (window.innerHeight - height) / 2;
    const popup = window.open(
        url, 
        "previewPopup",
        `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
    );
    if (!popup) {
        alert("팝업이 차단되었습니다. 팝업 차단을 해제해주세요.");
        return;
    }
    // 체크된 필드만 값과 함께 postMessage로 전달
    setTimeout(() => {
        const checked = {};
        document.querySelectorAll('input[type="checkbox"][id^="chk_"]').forEach(cb => {
            if (cb.checked) {
                // 필드명 추출 (예: chk_prdlst_nm → prdlst_nm)
                const field = cb.id.replace('chk_', '');
                // 값은 입력/textarea/select에서 가져옴
                const input = document.querySelector(`[name="${field}"]`);
                if (input) checked[field] = input.value;
            }
        });
        popup.postMessage({ type: 'previewCheckedFields', checked }, '*');
    }, 500);
  };

  window.addEventListener('message', function (e) {
    console.log('메시지 수신됨:', e.data);
    
    // 영양성분 데이터 처리
    if (e.data.type === 'nutrition-data-updated') {
      console.log('영양성분 데이터 업데이트 처리');
      handleNutritionDataUpdate(e.data);
      return;
    }
    
    // 영양성분 초기화 처리
    if (e.data.type === 'nutrition-data-reset') {
      console.log('영양성분 데이터 초기화 처리');
      handleNutritionDataReset();
      return;
    }
    
    // 기존 문구 적용 처리
    if (e.data.type !== 'applyPhrases') return;
    const phrases = e.data.phrases;
    const categoryMapping = {
      storage: 'storage_method',
      package: 'frmlc_mtrqlt',
      manufacturer: 'bssh_nm',
      distributor: 'distributor_address',
      repacker: 'repacker_address',
      importer: 'importer_address',
      expiry: 'pog_daycnt',
      cautions: 'cautions',
      additional: 'additional_info'
    };

    Object.keys(phrases).forEach(category => {
      const mappedCategory = categoryMapping[category] || category;
      const textarea = document.querySelector(`textarea[name="${mappedCategory}"]`);
      if (textarea && phrases[category]?.length) {
        textarea.value = phrases[category].map(p => p.content).join('\n');
        updateTextareaHeight(textarea);
      }
    });
  });

  // ------------------ 체크박스 그룹 초기화 ------------------
  function initCheckBoxGroups() {
    $('.grp-long-shelf').on('change', function () {
      if (this.checked) {
        $('.grp-long-shelf').not(this).prop('checked', false).data('alreadyChecked', false);
        $(this).data('alreadyChecked', true);
        $('#hidden_preservation_type').val(this.value);
      } else {
        $(this).data('alreadyChecked', false);
        $('#hidden_preservation_type').val('');
      }
      updateSummary();
    });

    $('.grp-sterilization').on('change', function () {
      if (this.id === 'chk_sterilization_other') return;
      if (this.checked) {
        $('.grp-sterilization').not('#chk_sterilization_other').not(this)
          .prop('checked', false).data('alreadyChecked', false);
        $(this).data('alreadyChecked', true);
        $('#hidden_processing_method').val(this.value);
      } else {
        $(this).data('alreadyChecked', false);
        $('#hidden_processing_method').val('');
      }
      updateSterilizationOther();
      updateSummary();
    });

    $('#chk_sterilization_other').on('change', function () {
      updateSummary();
      const conditionInput = $('input[name="processing_condition"]');
      conditionInput.prop('disabled', !this.checked);
      if (!this.checked) {
        conditionInput.val('');
        $('#hidden_processing_condition').val('');
      }
      updateSummary();
    });

    $('input[name="processing_condition"]').on('input change', function () {
      const value = this.value.trim();
      $('#hidden_processing_condition').val(value);
      if ($('#chk_sterilization_other').is(':checked')) {
        updateSummary();
      }
    });

    function updateSterilizationOther() {
      const isActive = $('#chk_sanitized').is(':checked') || $('#chk_aseptic').is(':checked');
      $('#chk_sterilization_other').prop('disabled', !isActive).prop('checked', isActive ? $('#chk_sterilization_other').prop('checked') : false);
      if (!isActive) {
        $('input[name="processing_condition"], #hidden_processing_condition').val('');
        updateSummary();
      }
    }
  }

  // ------------------ 식품유형 요약 업데이트 (적용 버튼에서만 동작) ------------------
  function updateSummary() {
    // 기존 요약 로직 실행
    const summaries = [];
    const foodSmall = $('#food_type option:selected').text();
    if (foodSmall && foodSmall !== '소분류') {
      summaries.push(foodSmall);
    }

    const longShelfId = $('.grp-long-shelf:checked').attr('id');
    let isFrozenHeated = false;
    
    // 새로운 복합 요약 시스템도 함께 실행
    updateFoodTypeSummary();
    if (longShelfId === 'chk_frozen_heated') {
      summaries.push('가열하여 섭취하는 냉동식품');
      isFrozenHeated = true;
    } else if (longShelfId === 'chk_frozen_nonheated') {
      summaries.push('가열하지 않고 섭취하는 냉동식품');
    } else if (longShelfId === 'chk_canned') {
      summaries.push('통.병조림');
    } else if (longShelfId === 'chk_retort') {
      summaries.push('레토르트식품');
    }

    const methodLabels = {
      chk_sanitized: '살균제품',
      chk_aseptic: '멸균제품',
      chk_yutang: '유탕.유처리제품'
    };
    let methodChecked = false;
    $('.grp-sterilization:checked').each(function () {
      const methodId = $(this).attr('id');
      if (methodLabels[methodId]) {
        summaries.push(methodLabels[methodId]);
        methodChecked = true;
      }
    });

    if ($('#chk_sterilization_other').is(':checked')) {
      const conditionValue = $('input[name="processing_condition"]').val()?.trim();
      if (conditionValue) {
        summaries.push(conditionValue);
        methodChecked = true;
      }
    }

    if (isFrozenHeated && !methodChecked) {
      summaries.push('비살균제품');
    }

    const summaryText = '식품유형 자동 입력 : ' + (summaries.length ? summaries.join(' | ') : '');
    // 아래쪽 요약 표시 비활성화 - 헤더의 배지로만 표시
    // $('#summary-step1').text(summaryText).attr('title', summaryText);
  }

  // ------------------ 토글 버튼 초기화 ------------------
  function initToggleButtons() {
    const toggles = [
      {
        btn: 'toggleFoodTypeBtn',
        section: 'food-type-section',
        showText: '∧',
        hideText: '∨',
        showTitle: '접기',
        hideTitle: '펼치기',
        toggleFn: (section, isHidden) => (section.style.display = isHidden ? 'block' : 'none')
      },
      {
        btn: 'toggleRegulationBtn',
        section: 'regulationPanel',
        showText: '❮',
        hideText: '❯',
        showTitle: '펼치기',
        hideTitle: '접기',
        toggleFn: (section, isHidden) => section.classList.toggle('collapsed', !isHidden)
      },
      {
        btn: 'toggleManufacturerBtn',
        section: 'other-manufacturers',
        showText: '∧',
        hideText: '∨',
        showTitle: '접기',
        hideTitle: '펼치기',
        toggleFn: null // Bootstrap collapse 사용
      }
    ];

    toggles.forEach(({ btn, section, showText, hideText, showTitle, hideTitle, toggleFn }) => {
      const btnEl = document.getElementById(btn);
      const sectionEl = document.getElementById(section);
      if (!btnEl || !sectionEl) return;

      // other-manufacturers 섹션의 경우 체크박스 상태에 따라 초기 표시 상태 결정
      if (section === 'other-manufacturers') {
        const distributorCheckbox = document.getElementById('chk_distributor_address');
        const repackerCheckbox = document.getElementById('chk_repacker_address');
        const importerCheckbox = document.getElementById('chk_importer_address');
        
        const shouldExpand = (distributorCheckbox && distributorCheckbox.checked) ||
                            (repackerCheckbox && repackerCheckbox.checked) ||
                            (importerCheckbox && importerCheckbox.checked);
        
        if (shouldExpand) {
          // Bootstrap collapse로 펼치기
          sectionEl.classList.add('show');
          btnEl.innerText = showText;
          btnEl.setAttribute('title', showTitle);
        }
      }

      if (toggleFn) {
        btnEl.addEventListener('click', () => {
          const isHidden = sectionEl.style.display === 'none' || sectionEl.classList.contains('collapsed');
          toggleFn(sectionEl, isHidden);
          btnEl.innerText = isHidden ? showText : hideText;
          btnEl.setAttribute('title', isHidden ? showTitle : hideTitle);
        });
      } else {
        sectionEl.addEventListener('shown.bs.collapse', () => {
          btnEl.innerText = showText;
          btnEl.setAttribute('title', showTitle);
        });
        sectionEl.addEventListener('hidden.bs.collapse', () => {
          btnEl.innerText = hideText;
          btnEl.setAttribute('title', hideTitle);
        });
      }
    });
  }

  // ------------------ 식품유형 대분류-소분류 연동 ------------------
  function updateCheckboxesByFoodType(foodType) {
    if (!foodType) return;
    
    console.log('updateCheckboxesByFoodType called with:', foodType);
    
    return fetch(`/label/food-type-settings/?food_type=${encodeURIComponent(foodType)}`)
      .then(response => response.json())
      .then(data => {
        console.log('API response:', data);
        
        if (!data.success || !data.settings) {
          console.error('API error:', data.error || 'No settings returned');
          return;
        }
        
        const settings = data.settings;
        
        // 규정 정보 업데이트 - 여러 가능한 선택자로 시도
        if (settings.relevant_regulations !== undefined) {
          const textarea = document.querySelector('textarea[name="related_regulations"]') || 
                          document.querySelector('#regulation-content textarea') ||
                          document.querySelector('#regulationPanel textarea');
          
          if (textarea) {
            console.log('Found regulations textarea, updating with:', settings.relevant_regulations);
            textarea.value = settings.relevant_regulations || '해당 식품유형에 관련된 규정이 없습니다.';
            if (typeof updateTextareaHeight === 'function') {
              updateTextareaHeight(textarea);
            }
          } else {
            console.warn('Regulations textarea not found');
          }
        }
        
        // 날짜 옵션 업데이트
        if (settings.pog_daycnt_options !== undefined) {
          console.log('Updating date options:', settings.pog_daycnt_options);
          updateDateDropdownOptions(settings.pog_daycnt_options);
        }
        
        // 체크박스 업데이트 항상 실행
        Object.keys(settings).forEach(field => {
          if (field === 'relevant_regulations' || field === 'pog_daycnt_options') return;
          
          const value = settings[field];
          const checkboxId = fieldMappings[field] || `chk_${field}`;
          const checkbox = document.getElementById(checkboxId);
          
          if (checkbox) {
            console.log(`Updating checkbox ${checkboxId}: ${value}`);
            checkbox.checked = value === 'Y';
            checkbox.disabled = value === 'D';
            checkbox.dataset.forcedDisabled = value === 'D' ? 'true' : 'false';
            checkbox.dispatchEvent(new Event('change'));
          }
          
          if (field === 'pog_daycnt') {
            updateDateDropdown(settings.pog_daycnt);
          }
          
          // 내용량 타입 자동 선택 로직
          if (field === 'weight_calorie') {
            updateContentTypeByFoodType(value);
          }
        });
      })
      .catch(error => {
        console.error('Error updating checkboxes:', error);
      });
  }  // 식품유형에 따른 내용량 타입 자동 설정
  function updateContentTypeByFoodType(weightCalorieValue) {
    const contentTypeDisplay = document.getElementById('content_type_display');
    const contentTypeValue = document.getElementById('content_type_value');
    if (!contentTypeDisplay || !contentTypeValue) return;

    // weight_calorie 값에 따라 표시 텍스트와 값 설정
    // Y: 내용량(열량) 표시, N/D: 내용량 표시
    // 모든 데이터는 content_weight 필드에만 저장
    if (weightCalorieValue === 'Y') {
      contentTypeDisplay.textContent = '내용량(열량)';
      contentTypeValue.value = 'weight_calorie';
    } else if (weightCalorieValue === 'N' || weightCalorieValue === 'D') {
      contentTypeDisplay.textContent = '내용량';
      contentTypeValue.value = 'content_weight';
    }

    // 체크박스 상태에 따른 표시 업데이트 (disabled 상태일 때는 회색으로)
    updateContentTypeVisibility();
  }
  
  // 내용량 타입 표시 상태 업데이트
  function updateContentTypeVisibility() {
    const checkbox = document.getElementById('chk_content_weight');
    const contentTypeDisplay = document.getElementById('content_type_display');
    
    if (checkbox && contentTypeDisplay) {
      if (checkbox.checked) {
        contentTypeDisplay.style.color = '#495057';
        contentTypeDisplay.style.opacity = '1';
      } else {
        contentTypeDisplay.style.color = '#6c757d';
        contentTypeDisplay.style.opacity = '0.6';
      }
    }
  }
  
  function initFoodTypeFiltering() {
    const foodGroup = $('#food_group');
    const foodType = $('#food_type');
    const hiddenFoodGroup = $('#hidden_food_group');
    const hiddenFoodType = $('#hidden_food_type');
    let pendingFoodType = null; // 적용 대기 중인 소분류 값

    // Select2 초기화
    if (foodGroup.length && !foodGroup.hasClass('select2-hidden-accessible')) {
      foodGroup.select2({
        placeholder: '대분류 선택',
        allowClear: true,
        width: '100%'
      });
    }

    if (foodType.length && !foodType.hasClass('select2-hidden-accessible')) {
      foodType.select2({
        placeholder: '소분류 선택',
        allowClear: true,
        width: '100%'
      });
    }

    function updateHiddenFields() {
      hiddenFoodGroup.val(foodGroup.val());
      hiddenFoodType.val(foodType.val());
    }

    function updateFoodTypes(group, currentType) {
      foodType.empty().append('<option value="">소분류</option>');
      // 대분류가 비어있어도 전체 식품유형 데이터를 불러옴
      const url = `/label/food-types-by-group/?group=${encodeURIComponent(group || '')}`;
      
      fetch(url)
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          return response.json();
        })
        .then(data => {
          console.log('Food types loaded:', data);
          if (data.success && data.food_types && Array.isArray(data.food_types)) {
            data.food_types.forEach(item => {
              const option = new Option(item.food_type, item.food_type);
              option.dataset.group = item.food_group;
              foodType.append(option);
            });
            if (currentType && data.food_types.some(t => t.food_type === currentType)) {
              foodType.val(currentType);
            }
            // Select2 재초기화
            if (foodType.hasClass('select2-hidden-accessible')) {
              foodType.select2('destroy');
            }
            foodType.select2({
              placeholder: '소분류 선택',
              allowClear: true,
              width: '100%'
            });
          } else {
            console.error('Failed to load food types:', data.error || 'Invalid response format');
            // 기본 옵션만 유지
            foodType.empty().append('<option value="">소분류 선택</option>');
          }
        })
        .catch(error => {
          console.error('Error fetching food types:', error);
          // 네트워크 에러 시에도 기본 옵션 유지
          foodType.empty().append('<option value="">소분류 선택</option>');
        });
    }

    foodGroup.on('change', function () {
      const group = this.value;
      updateHiddenFields();
      // 대분류가 선택되지 않았어도 모든 소분류를 보여줌
      updateFoodTypes(group || '', foodType.val());
      updateSummary();
    });

    // 소분류 변경 시 체크박스 즉시 변경 X, pendingFoodType에만 저장
    foodType.on('change', function () {
      const selectedOption = this.options[this.selectedIndex];
      const foodTypeValue = selectedOption?.value;
      updateHiddenFields();
      if (foodTypeValue) {
        const group = selectedOption.dataset.group;
        if (group && foodGroup.val() !== group) {
          foodGroup.val(group).trigger('change.select2');
          hiddenFoodGroup.val(group);
        } else if (!group) {
          fetch(`/label/get-food-group/?food_type=${encodeURIComponent(foodTypeValue)}`)
            .then(response => response.json())
            .then(data => {
              if (data.success && data.food_group) {
                foodGroup.val(data.food_group).trigger('change.select2');
                hiddenFoodGroup.val(data.food_group);
                selectedOption.dataset.group = data.food_group;
              }
            });
        }
        pendingFoodType = foodTypeValue; // 적용 대기
      } else {
        pendingFoodType = null;
      }
      updateSummary();
    });

    updateHiddenFields();
    const initialFoodType = foodType.val();
    const initialFoodGroup = foodGroup.val();
    
    if (initialFoodType) {
      const group = foodType.find('option:selected').data('group');
      if (group) {
        foodGroup.val(group).trigger('change.select2');
        hiddenFoodGroup.val(group);
        if (window.checkboxesLoadedFromDB === undefined) {
          window.checkboxesLoadedFromDB = true;
        }
        pendingFoodType = initialFoodType;
      } else {
        fetch(`/label/get-food-group/?food_type=${encodeURIComponent(initialFoodType)}`)
          .then(response => response.json())
          .then(data => {
            if (data.success && data.food_group) {
              foodGroup.val(data.food_group).trigger('change.select2');
              hiddenFoodGroup.val(data.food_group);
              pendingFoodType = initialFoodType;
            }
          });
      }
    } else {
      // 초기 로딩 시 대분류에 상관없이 모든 소분류를 로딩
      updateFoodTypes('', initialFoodType);
    }
    
    // 페이지 로딩 완료 후 소분류 재로딩 (대분류 선택과 무관하게)
    setTimeout(() => {
      console.log('식품유형 재로딩 시작...');
      updateFoodTypes('', foodType.val());
    }, 500);
    
    // 추가 안전장치 - DOM이 완전히 안정된 후 다시 한번 시도
    setTimeout(() => {
      if (foodType.children().length <= 1) { // 기본 옵션만 있는 경우
        console.log('소분류 옵션이 비어있음, 재시도...');
        updateFoodTypes('', foodType.val());
      }
    }, 2000);

    // 전역 함수로 노출하여 적용 버튼에서 호출할 수 있도록 함
    window.applyStep1FoodType = function() {
      if (pendingFoodType) {
        updateCheckboxesByFoodType(pendingFoodType);
      }
    };
  }

  // ------------------ 날짜 드롭다운 업데이트 ------------------
  function updateDateDropdown(value) {
    const dateOptions = document.querySelector('select[name="date_option"]');
    if (!dateOptions) {
      console.warn('Date options select not found in updateDateDropdown');
      return;
    }
    
    console.log('updateDateDropdown called with value:', value);
    
    dateOptions.disabled = value === 'D';
    Array.from(dateOptions.options).forEach(option => (option.disabled = value === 'D'));
    if (value === 'D') {
      dateOptions.value = '';
    }
    
    console.log('Date dropdown state updated - disabled:', dateOptions.disabled);
  }

  function updateDateDropdownOptions(options) {
    const dateOptions = document.querySelector('select[name="date_option"]');
    if (!dateOptions) {
      console.warn('Date options select not found');
      return;
    }
    
    console.log('Updating date dropdown with options:', options);
    
    const currentValue = dateOptions.value;
    if (!dateOptions.dataset.originalOptions) {
      dateOptions.dataset.originalOptions = dateOptions.innerHTML;
    }

    dateOptions.innerHTML = '';
    if (options?.length) {
      options.forEach(option => {
        if (option) {
          const optionElement = new Option(option, option);
          if (currentValue === option) optionElement.selected = true;
          dateOptions.append(optionElement);
        }
      });
      if (!options.includes(currentValue) && options[0]) {
        dateOptions.value = options[0];
      }
    } else {
      dateOptions.innerHTML = dateOptions.dataset.originalOptions || '';
    }
    dateOptions.disabled = false;
    console.log('Date dropdown updated successfully');
  }
  // ------------------ 체크박스 필드 토글 ------------------
  function initCheckboxFieldToggle() {
    document.querySelectorAll('input[type="checkbox"][id^="chk_"]').forEach(checkbox => {
      if (checkbox.dataset.initialized === 'true') return;
      checkbox.dataset.initialized = 'true';
      const fieldName = checkbox.id.replace('chk_', '');
      
      // [수정] 원재료명(참고) 필드는 항상 비활성화하고 체크박스는 숨김
      if (fieldName === 'rawmtrl_nm') {
        checkbox.style.display = 'none'; // 체크박스를 화면에 보이지 않게 처리
        checkbox.disabled = true; // 기능적으로도 비활성화 상태 유지
        const textarea = document.querySelector('textarea[name="rawmtrl_nm"]');
        if (textarea) {
          textarea.disabled = true;
          textarea.classList.add('disabled-textarea');
        }
        return;
      }        // 내용량 필드는 특별 처리 (텍스트 표시와 입력 필드)
      if (fieldName === 'content_weight') {
        const contentTypeDisplay = document.getElementById('content_type_display');
        const contentWeightInput = document.getElementById('content_weight_input');
        
        function updateContentFields() {
          const isDisabled = !checkbox.checked;
          if (contentWeightInput) {
            contentWeightInput.disabled = isDisabled;
            contentWeightInput.classList.toggle('disabled-textarea', isDisabled);
          }
          // 텍스트 표시 상태도 업데이트
          updateContentTypeVisibility();
        }
        
        checkbox.addEventListener('change', function() {
          updateContentFields();
        });
        
        updateContentFields();
        return;
      }
      
      const relatedFields = fieldMappings[`${fieldName}_arr`]?.map(sel => document.querySelector(sel)).filter(Boolean) || [];
      if (!relatedFields.length) {
        return;
      }
      function updateFields() {
        relatedFields.forEach(field => {
          field.disabled = !checkbox.checked || checkbox.dataset.forcedDisabled === 'true';
          field.classList.toggle('disabled-textarea', field.disabled);
        });
      }
      checkbox.addEventListener('change', function() {
        updateFields();
        const hiddenFieldName = `chckd_${fieldName}`;
        let hiddenField = document.querySelector(`input[type="hidden"][name="${hiddenFieldName}"]`);
        if (hiddenField) {
          hiddenField.value = this.checked ? 'Y' : 'N';
        }
      });
      updateFields();
    });
    
    // DB에 저장된 체크박스 상태 로드
    window.checkboxesLoadedFromDB = true;
  }

  function prepareFormData() {
    document.querySelectorAll('input[type="checkbox"][id^="chk_"]').forEach(function(checkbox) {
      const id = checkbox.id;
      if (id?.startsWith('chk_')) {
        const fieldName = id.replace('chk_', '');
        const hiddenFieldName = `chckd_${fieldName}`;
        let hiddenField = document.querySelector(`input[type="hidden"][name="${hiddenFieldName}"]`);
        if (!hiddenField) {
          hiddenField = document.createElement('input');
          hiddenField.type = 'hidden';
          hiddenField.name = hiddenFieldName;
          checkbox.parentNode.appendChild(hiddenField);
        }
        hiddenField.value = checkbox.checked ? 'Y' : 'N';
      }
    });

    $('#hidden_preservation_type').val($('.grp-long-shelf:checked').val() || '');
    $('#hidden_processing_method').val($('.grp-sterilization:checked').not('#chk_sterilization_other').val() || '');
    $('#hidden_processing_condition').val($('input[name="processing_condition"]').val() || '');
  }

  function saveCheckboxStates() {
    const checkboxStates = {};
    document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkboxStates[checkbox.id] = {
            checked: checkbox.checked,
            name: checkbox.name,
            value: checkbox.value || ''
        };
    });
    try {
        const labelId = document.getElementById('label_id')?.value;
        if (labelId) {
            localStorage.setItem(`checkboxStates_${labelId}`, JSON.stringify(checkboxStates));
        }
    } catch (e) {
        console.error('체크박스 상태 저장 실패:', e);
    }
  }

  // ------------------ Select2 초기화 ------------------
  function initSelect2Components() {
    $('#food_group').select2({ placeholder: '대분류 선택', allowClear: true, width: '100%' });
    $('#food_type').select2({ placeholder: '소분류 선택', allowClear: true, width: '100%' });
    $('select[name="country_of_origin"]').select2({ placeholder: '대외무역법에 따른 가공국을 선택하세요.', allowClear: true, width: '100%' });
    // 소비기한/품질유지기한 드롭다운(select[name="date_option"])에는 select2를 적용하지 않음 (검색 기능 제거)
  }

  // ------------------ 내문구 탭 기능 ------------------
  function getCategoryFromFieldName(fieldName) {
    const mapping = {
      my_label_name: 'label_name',          // 라벨명
      prdlst_dcnm: 'food_type',            // 식품유형
      prdlst_nm: 'product_name',           // 제품명
      ingredient_info: 'ingredient_info',   // 특정성분 함량
      content_weight: 'content_weight',     // 내용량
      weight_calorie: 'weight_calorie',     // 내용량(열량)
      prdlst_report_no: 'report_no',       // 품목보고번호
      storage_method: 'storage',            // 보관방법
      frmlc_mtrqlt: 'package',             // 용기.포장재질
      bssh_nm: 'manufacturer',             // 제조원 소재지
      distributor_address: 'distributor',   // 유통전문판매원
      repacker_address: 'repacker',        // 소분원
      importer_address: 'importer',         // 수입원
      pog_daycnt: 'expiry',                // 소비기한
      cautions: 'cautions',                // 주의사항
      additional_info: 'additional'         // 기타표시사항
    };
    return mapping[fieldName] || null;
  }
  
  function renderMyPhrasesForFocusedField() {
    const fieldName = lastFocusedFieldName || 'prdlst_nm';
    const category = getCategoryFromFieldName(fieldName);
    const listContainer = document.getElementById('myPhraseList');
    if (!listContainer || !category || !phrasesData) {
      console.warn('Missing required elements:', { listContainer, category, phrasesData }); // Debugging
      if (listContainer) listContainer.innerHTML = '<div class="text-muted" style="font-size: 0.8rem;">문구 데이터를 로드할 수 없습니다.</div>';
      return;
    }
  
    listContainer.innerHTML = '';
    const isMultiSelect = ['cautions', 'additional'].includes(category);
    const textarea = document.querySelector(`textarea[name="${fieldName}"], input[name="${fieldName}"]`);
    const currentValues = textarea ? textarea.value.split('\n').map(v => v.trim()).filter(Boolean) : [];
  
    const phraseList = phrasesData[category] || [];
    if (!phraseList.length) {
      listContainer.innerHTML = '<div class="text-muted" style="font-size: 0.8rem;">저장된 문구가 없습니다. 문구 관리에서 추가하세요.</div>';
      return;
    }
  
    const sortedPhrases = [...phraseList].sort((a, b) => (b.note?.includes('★') ? 1 : 0) - (a.note?.includes('★') ? 1 : 0));
  
    sortedPhrases.forEach(p => {
      const div = document.createElement('div');
      div.className = 'phrase-item';
      div.textContent = p.content;
      Object.assign(div.style, {
        padding: '6px 8px',
        border: '1px solid #ccc',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '0.8rem',
        transition: 'background-color 0.2s',
        marginBottom: '4px'
      });
  
      div.addEventListener('click', () => {
        if (!textarea) return;
        if (isMultiSelect) {
          const values = textarea.value.split(' | ').map(v => v.trim()).filter(Boolean);
          const index = values.indexOf(p.content);
          if (index === -1) {
            values.push(p.content);
            div.style.backgroundColor = '#d0ebff';
          } else {
            values.splice(index, 1);
            div.style.backgroundColor = '#fff';
          }
          textarea.value = values.join(' | ');
        } else {
          const isSelected = textarea.value === p.content;
          textarea.value = isSelected ? '' : p.content;
          listContainer.querySelectorAll('.phrase-item').forEach(item => {
            item.style.backgroundColor = item.textContent === textarea.value ? '#d0ebff' : '#fff';
          });
        }
        updateTextareaHeight(textarea);
      });
  
      div.style.backgroundColor = currentValues.includes(p.content) ? '#d0ebff' : '#fff';
      if (p.note) div.title = p.note;
      listContainer.appendChild(div);
    });
  }

  function showRegulationInfo(fieldName) {
    const container = document.getElementById('myPhraseContainer');
    if (!container) return;
  
    container.querySelectorAll('.text-muted, .regulation-info').forEach(el => el.remove());
  
    const fieldMapping = {
      my_label_name: 'label_nm',
      prdlst_dcnm: 'prdlst_dcnm',
      prdlst_nm: 'prdlst_nm',
      ingredient_info: 'ingredients_info',
      content_weight: 'content_weight',
      prdlst_report_no: 'report_no',  
      storage_method: 'storage',
      frmlc_mtrqlt: 'package',
      bssh_nm: 'manufacturer',
      distributor_address: 'distributor',
      pog_daycnt: 'expiry',
      weight_calorie: 'weight_calorie',
      rawmtrl_nm_display: 'rawmtrl_nm',
      cautions: 'cautions',
      additional_info: 'additional'
    };
  
    const regulationInfo = regulations[fieldMapping[fieldName] || fieldName];
    if (regulationInfo) {
      const infoContainer = document.createElement('div');
      infoContainer.className = 'regulation-info';
      infoContainer.innerHTML = regulationInfo
        .split('\n')
        .map(line => (line.trim() ? `<p class="mb-1">${line}</p>` : '<br>'))
        .join('');
      container.appendChild(infoContainer);
    }
  }
  function applyDbCheckboxStates() {
    document.querySelectorAll('input[type="hidden"][name^="chckd_"]').forEach(hiddenField => {
      const fieldName = hiddenField.name.replace('chckd_', '');
      const checkboxId = `chk_${fieldName}`;
      const checkbox = document.getElementById(checkboxId);
      if (checkbox) {
        checkbox.checked = hiddenField.value === 'Y';
        // change 이벤트를 발생시키지 않음 (이벤트 미발생 방식)
      }
    });
  }

  function handlePhraseTabActivation() {
    if (lastFocusedFieldName) {
      renderMyPhrasesForFocusedField();
      showRegulationInfo(lastFocusedFieldName);
    }
  }

  function setPhraseTabNavStyles() {
    document.querySelectorAll('#phraseTab .nav-link').forEach(btn => {
      btn.style.fontSize = '0.8rem';
      btn.style.color = btn.classList.contains('active') ? '#0d6efd' : '';
      btn.addEventListener('shown.bs.tab', () => {
        document.querySelectorAll('#phraseTab .nav-link').forEach(b => (b.style.color = ''));
        btn.style.color = '#0d6efd';
      });
    });
  }

  function bindSaveCheckboxOnTabShow() {
    document.querySelectorAll('.nav-link').forEach(tab => {
      tab.addEventListener('show.bs.tab', function() {
        saveCheckboxStates();
      });
    });
  }

  // 내문구 탭 강제 새로고침 함수
  function reloadPhraseTab() {
    // 문구 데이터 새로고침 (AJAX)
    fetch('/label/phrases-data/', {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      },
      credentials: 'same-origin'
    })
      .then(res => res.json())
      .then(data => {
        if (data.success && data.phrases) {
          phrasesData = data.phrases;
          renderMyPhrasesForFocusedField();
        } else {
          const listContainer = document.getElementById('myPhraseList');
          if (listContainer) {
            listContainer.innerHTML = '<div class="text-danger" style="font-size:0.8rem;">문구 데이터를 불러오지 못했습니다.</div>';
          }
        }
      })
      .catch(() => {
        const listContainer = document.getElementById('myPhraseList');
        if (listContainer) {
          listContainer.innerHTML = '<div class="text-danger" style="font-size:0.8rem;">문구 데이터를 불러오지 못했습니다.</div>';
        }
      });
  }

  // ------------------ 초기화 및 이벤트 바인딩 ------------------
  $(document).ready(function () {
    initSelect2Components();
    initCheckBoxGroups();
    initToggleButtons();
    initCheckboxFieldToggle();
    initFoodTypeFiltering();
    
    // 🎯 성능 최적화: 조건부 초기화
    if (!window.mainSystemInitialized) {
      window.mainSystemInitialized = true;
      initAutoExpand();
    } else {
      console.log('⚠️ 메인 시스템 이미 초기화됨 - 중복 실행 방지');
    }

    //applyDbCheckboxStates();

    $('#labelForm').on('submit', function (event) {
      const urlParams = new URLSearchParams(window.location.search);
      const autoSubmit = urlParams.get('autoSubmit');
      
      if (autoSubmit !== 'true') {
        // 최종 동기화
        const topInput = document.getElementById('my_label_name_top');
        const hiddenInput = document.getElementById('my_label_name_hidden');
        if (topInput && hiddenInput) {
          hiddenInput.value = topInput.value;
        }
        
        $('#hidden_food_group').val($('#food_group').val());
        $('#hidden_food_type').val($('#food_type').val());
        prepareFormData();
      }
      return autoSubmit !== 'true';
    });

    $('.select2-food-type, input[type="checkbox"], input[name="processing_condition"]').on('change input', updateSummary);

    document.querySelectorAll('textarea, input[type="text"]').forEach(el => {
      el.addEventListener('focus', function () {
        clearTimeout(window.focusTimeout);
        window.focusTimeout = setTimeout(() => {
          lastFocusedFieldName = this.getAttribute('name');
          if (document.querySelector('#myphrases-tab.active')) {
            handlePhraseTabActivation();
          }
        }, 100);
      });
    });

    const myPhrasesTab = document.getElementById('myphrases-tab');
    if (myPhrasesTab) {
      myPhrasesTab.addEventListener('shown.bs.tab', reloadPhraseTab);
      myPhrasesTab.addEventListener('click', reloadPhraseTab);
    }

    setPhraseTabNavStyles();
    bindSaveCheckboxOnTabShow();

    $('.preview-btn').on('click', function() {
      window.openPreviewPopup();
    });

    document.querySelector('button[type="submit"]').addEventListener('click', function() {
      saveCheckboxStates();
    });

    const linkedBtn = document.getElementById('linkedLabelsBtn');
    if (linkedBtn) {
      linkedBtn.onclick = function() {
        var labelId = document.getElementById('label_id')?.value;
        if (labelId) {
          fetch('/label/linked-ingredient-count/' + encodeURIComponent(labelId) + '/')
            .then(res => {
              if (!res.ok) throw new Error('Network response was not ok');
              return res.json();
            })
            .then(data => {
              // count가 0이면 얼럿, 1 이상이면 이동
              if (typeof data.count === 'number') {
                if (data.count > 0) {
                  window.location.href = '/label/my-ingredient-list-combined/?label_id=' + encodeURIComponent(labelId);
                } else {
                  alert('연결된 원료가 없습니다.');
                }
              } else {
                alert('연결된 원료 정보를 확인할 수 없습니다.');
              }
            })
            .catch(() => alert('연결된 원료 정보를 확인할 수 없습니다.'));
        }
      };
    }

    updateSummary();
  });

  // 저장/미리보기 버튼 비활성화 및 스피너 표시
  const saveBtn = document.getElementById('saveBtn');
  const previewBtn = document.getElementById('previewBtn');
  const savingSpinner = document.getElementById('savingSpinner');
  const form = document.getElementById('labelForm') || document.querySelector('form');

  if (form && saveBtn && previewBtn && savingSpinner) {
    form.addEventListener('submit', function() {
      saveBtn.disabled = true;
      previewBtn.disabled = true;
      savingSpinner.style.display = '';
    });

    // 저장 완료 후(redirect 없이 ajax라면) 아래 코드로 복구 필요
    // 예시: 저장 ajax 콜백에서
    // saveBtn.disabled = false;
    // previewBtn.disabled = false;
    // savingSpinner.style.display = 'none';
  }

  function step1Apply() {
    // 적용 버튼 클릭 시에만 요약 표시
    updateSummary();
    document.getElementById('step1-body').style.display = 'none';
    // 버튼 토글 - 동시에 보이지 않도록 확실히 처리
    const applyBtn = document.getElementById('applyStep1Btn');
    const expandBtn = document.getElementById('expandStep1Btn');
    if (applyBtn) {
      applyBtn.style.display = 'none';
      applyBtn.style.visibility = 'hidden';
    }
    if (expandBtn) {
      expandBtn.style.display = 'inline-flex';
      expandBtn.style.visibility = 'visible';
    }
  }

  function step1Expand() {
    document.getElementById('step1-body').style.display = '';
    // 버튼 토글 - 동시에 보이지 않도록 확실히 처리
    const applyBtn = document.getElementById('applyStep1Btn');
    const expandBtn = document.getElementById('expandStep1Btn');
    if (applyBtn) {
      applyBtn.style.display = 'inline-flex';
      applyBtn.style.visibility = 'visible';
    }
    if (expandBtn) {
      expandBtn.style.display = 'none';
      expandBtn.style.visibility = 'hidden';
    }
    // 펼치기 시 요약 숨김 코드 제거 (summary-step1 텍스트를 지우지 않음)
  }

  // Step1 적용/펼치기 버튼 이벤트 바인딩
  const applyBtn = document.getElementById('applyStep1Btn');
  const expandBtn = document.getElementById('expandStep1Btn');
  if (applyBtn) applyBtn.onclick = function() {
    // 적용 버튼 클릭 시 체크박스 업데이트 실행
    if (typeof window.applyStep1FoodType === 'function') {
      window.applyStep1FoodType();
    }
    step1Apply();
  };
  if (expandBtn) expandBtn.onclick = step1Expand;

  // 최초 로드시 step1-body는 펼쳐짐, 요약은 빈 값
  document.getElementById('step1-body').style.display = '';
  // 초기 상태에서 버튼 토글 확실히 설정
  const initialApplyBtn = document.getElementById('applyStep1Btn');
  const initialExpandBtn = document.getElementById('expandStep1Btn');
  if (initialApplyBtn) {
    initialApplyBtn.style.display = 'inline-flex';
    initialApplyBtn.style.visibility = 'visible';
  }
  if (initialExpandBtn) {
    initialExpandBtn.style.display = 'none';
    initialExpandBtn.style.visibility = 'hidden';
  }
  const summaryEl = document.getElementById('summary-step1');
  if (summaryEl) {
    summaryEl.innerText = '';
    summaryEl.title = '';
  }

  // 식품유형 요약 버튼 클릭 시 스텝2의 식품유형 필드(아래 input[name="prdlst_dcnm"])에 요약 결과 입력
  const summaryBtn = document.getElementById('summary-step1');
  if (summaryBtn) {
    summaryBtn.addEventListener('click', function () {
      // 버튼 텍스트에서 "식품유형 자동 입력 :" 또는 "식품유형 :" 접두어 제거
      let summaryText = summaryBtn.textContent.trim();
      summaryText = summaryText.replace(/^식품유형( 자동 입력)?\s*:/, '').trim();

      // | 앞뒤 공백만 정리 (중복 공백은 그대로 두고, | 기준으로만 트림)
      summaryText = summaryText
        .split('|')
        .map(s => s.trim())
        .join(' | ');

      // 아래 필드에 입력
      const foodTypeFields = document.querySelectorAll('input[name="prdlst_dcnm"].form-control.auto-expand');
      foodTypeFields.forEach(field => {
        field.value = summaryText;
        field.focus();
      });
    });
  }

  // ------------------ 품목보고번호 검증 기능 ------------------
  window.verifyReportNo = function(labelId) {
    const btn = document.getElementById('verifyReportNoBtn');
    if (!btn) return;
    
    // 상태 복구: 검증완료/검증실패 상태에서 클릭 시 초기화
    if (btn.innerHTML.includes('검증완료') || btn.innerHTML.includes('검증실패')) {
      btn.innerHTML = '<i class="fas fa-search me-1"></i>중복검증';
      btn.className = 'btn btn-outline-info action-btn-modern';
      return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>저장 중...';
    btn.className = 'btn btn-secondary action-btn-modern';
    
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    let reportNo = reportNoInput?.value?.trim();
    
    if (!reportNo) {
      alert('품목보고번호를 입력하세요.');
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-search me-1"></i>중복검증';
      btn.className = 'btn btn-outline-info action-btn-modern';
      return;
    }

    // 검증용 번호: 하이픈(-)을 제거한 값
    const verifyReportNo = reportNo.replace(/-/g, '');

    // 1. 먼저 품목보고번호 저장 및 검증여부 N으로 초기화 (원본 값으로 저장)
    fetch('/label/update-report-no/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ label_id: labelId, prdlst_report_no: reportNo })
    })
    .then(res => res.json())
    .then(data => {
      if (!data.success) throw new Error(data.error || '저장 실패');
      // 2. 저장 성공 시 검증 진행 (하이픈 제거된 값으로 검증)
      btn.innerHTML = '<i class="fas fa-shield-alt fa-pulse me-1"></i>중복 검증 중...';
      return fetch('/label/verify-report-no/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ label_id: labelId, prdlst_report_no: verifyReportNo })
      });
    })
    .then(res => res.json())
    .then(data => {
      if (data.verified) {
        btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>검증완료';
        btn.className = 'btn btn-success action-btn-modern';
        btn.title = 'API 중복 검사 및 번호 규칙 검증 완료';
      } else {
        btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>검증실패';
        btn.className = 'btn btn-danger action-btn-modern';
        btn.title = 'API 중복 또는 번호 규칙 오류 발견';
        
        // 실패 원인에 따른 상세 메시지
        let message = '검증에 실패했습니다.';
        if (data.error_type === 'duplicate') {
          message = '이미 사용 중인 품목보고번호입니다.';
        } else if (data.error_type === 'format') {
          message = '품목보고번호 형식이 올바르지 않습니다.';
        } else if (data.message) {
          message = data.message;
        }
        
        // 비침입적인 방식으로 오류 표시
        setTimeout(() => {
          if (confirm(message + '\n\n다시 검증하시겠습니까?')) {
            // 사용자가 재검증을 원하면 버튼 상태 초기화
            btn.innerHTML = '<i class="fas fa-search me-1"></i>중복검증';
            btn.className = 'btn btn-outline-info action-btn-modern';
          }
        }, 100);
      }
    })
    .catch(err => {
      btn.innerHTML = '<i class="fas fa-times-circle me-1"></i>오류발생';
      btn.className = 'btn btn-warning action-btn-modern';
      btn.title = '네트워크 오류 또는 서버 오류';
      
      setTimeout(() => {
        alert('검증 중 오류가 발생했습니다. ' + (err.message || ''));
        btn.innerHTML = '<i class="fas fa-search me-1"></i>중복검증';
        btn.className = 'btn btn-outline-info action-btn-modern';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
      }, 100);
    })
    .finally(() => {
      btn.disabled = false;
    });
  };
  
  // 식품유형 요약 표시 기능 추가 (복합 요약 방식)
  function updateFoodTypeSummary() {
    const summaries = [];
    
    // 1. 식품유형 (소분류)
    const foodSmall = $('#food_type option:selected').text();
    if (foodSmall && foodSmall !== '소분류 선택' && foodSmall !== '') {
      summaries.push(foodSmall);
    }

    // 2. 장기보존식품
    const longShelfId = $('.grp-long-shelf:checked, input[name="preservation_type"]:checked').attr('id');
    let isFrozenHeated = false;
    if (longShelfId === 'chk_frozen_heated') {
      summaries.push('가열하여 섭취하는 냉동식품');
      isFrozenHeated = true;
    } else if (longShelfId === 'chk_frozen_nonheated') {
      summaries.push('가열하지 않고 섭취하는 냉동식품');
    } else if (longShelfId === 'chk_canned') {
      summaries.push('통.병조림');
    } else if (longShelfId === 'chk_retort') {
      summaries.push('레토르트식품');
    }

    // 3. 제조방법
    const methodLabels = {
      chk_sanitized: '살균제품',
      chk_aseptic: '멸균제품',
      chk_yutang: '유탕.유처리제품'
    };
    let methodChecked = false;
    $('.grp-sterilization:checked, input[name="processing_method"]:checked').each(function () {
      const methodId = $(this).attr('id');
      if (methodLabels[methodId]) {
        summaries.push(methodLabels[methodId]);
        methodChecked = true;
      }
    });

    // 4. 기타 조건
    if ($('#chk_sterilization_other').is(':checked')) {
      const conditionValue = $('input[name="processing_condition"]').val()?.trim();
      if (conditionValue) {
        summaries.push(conditionValue);
        methodChecked = true;
      }
    }

    // 5. 냉동(가열)이지만 제조방법이 없으면 비살균제품 추가
    if (isFrozenHeated && !methodChecked) {
      summaries.push('비살균제품');
    }

    // UI 업데이트
    const summaryDisplay = document.getElementById('food-type-summary-display');
    const summaryText = document.getElementById('selected-food-type');
    
    if (summaryDisplay && summaryText) {
      if (summaries.length > 0) {
        const summaryContent = summaries.join(' | ');
        summaryText.innerHTML = `<i class="fas fa-tag me-1"></i>${summaryContent}`;
        summaryText.setAttribute('data-food-type-text', summaryContent);
        summaryDisplay.style.display = 'block';
      } else {
        summaryDisplay.style.display = 'none';
      }
    }
  }
  
  // 식품유형 요약 클릭 시 아래 필드에 입력
  function setupFoodTypeSummaryClick() {
    const summaryText = document.getElementById('selected-food-type');
    if (summaryText) {
      summaryText.addEventListener('click', function() {
        const foodTypeText = this.getAttribute('data-food-type-text');
        if (foodTypeText) {
          // 상세 입력 섹션의 식품유형 필드에 입력
          const foodTypeField = document.querySelector('input[name="prdlst_dcnm"]');
          if (foodTypeField) {
            foodTypeField.value = foodTypeText;
            foodTypeField.focus();
            
            // 시각적 피드백
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
              this.style.transform = 'scale(1)';
            }, 150);
            
            // 입력 완료 알림
            const tempTooltip = document.createElement('div');
            tempTooltip.textContent = '식품유형 필드에 입력되었습니다';
            tempTooltip.style.cssText = `
              position: absolute;
              background: #198754;
              color: white;
              padding: 0.25rem 0.5rem;
              border-radius: 4px;
              font-size: 0.75rem;
              top: -30px;
              left: 50%;
              transform: translateX(-50%);
              z-index: 1000;
              pointer-events: none;
            `;
            this.style.position = 'relative';
            this.appendChild(tempTooltip);
            
            setTimeout(() => {
              if (tempTooltip.parentNode) {
                tempTooltip.parentNode.removeChild(tempTooltip);
              }
            }, 2000);
          }
        }
      });
    }
  }
  
  // 식품유형 변경 이벤트 리스너 추가 (복합 요약용)
  const foodGroupSelect = document.getElementById('food_group');
  const foodTypeSelect = document.getElementById('food_type');
  
  if (foodGroupSelect) {
    foodGroupSelect.addEventListener('change', updateFoodTypeSummary);
  }
  if (foodTypeSelect) {
    foodTypeSelect.addEventListener('change', updateFoodTypeSummary);
  }
  
  // 체크박스 변경 시에도 요약 업데이트
  document.querySelectorAll('input[name="preservation_type"], input[name="processing_method"], #chk_sterilization_other').forEach(checkbox => {
    checkbox.addEventListener('change', updateFoodTypeSummary);
  });
  
  // 조건 상세 입력 시에도 요약 업데이트
  const conditionInput = document.querySelector('input[name="processing_condition"]');
  if (conditionInput) {
    conditionInput.addEventListener('input', updateFoodTypeSummary);
  }
  
  // 초기 로드 시 요약 표시
  updateFoodTypeSummary();
  
  // 식품유형 요약 클릭 이벤트 설정
  setupFoodTypeSummaryClick();
  
  // 체크박스 단일 선택 처리 (라디오 버튼처럼 동작)
  function initSingleCheckboxGroups() {
    // 장기보존식품 체크박스 그룹
    const preservationCheckboxes = document.querySelectorAll('input[name="preservation_type"]');
    preservationCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        if (this.checked) {
          preservationCheckboxes.forEach(other => {
            if (other !== this) {
              other.checked = false;
            }
          });
        }
        updateFoodTypeSummary(); // 요약 업데이트
      });
    });
    
    // 제조방법 체크박스 그룹
    const processingCheckboxes = document.querySelectorAll('input[name="processing_method"]');
    processingCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        if (this.checked) {
          processingCheckboxes.forEach(other => {
            if (other !== this) {
              other.checked = false;
            }
          });
        }
        updateFoodTypeSummary(); // 요약 업데이트
      });
    });
  }
  
  // 3개 플로팅 모달 시스템 초기화
  function initRightPanel() {
    // 이미 초기화되었는지 확인
    if (window.floatingModalsInitialized) {
        console.log('플로팅 모달 시스템이 이미 초기화되었습니다.');
        return;
    }
    
    console.log('🚀 3개 플로팅 모달 시스템 초기화 중...');
    
    // 모든 토글 버튼과 모달 찾기
    const toggleButtons = document.querySelectorAll('.floating-toggle-btn');
    const modals = document.querySelectorAll('.floating-modal');
    const closeButtons = document.querySelectorAll('.floating-modal-close');
    
    if (toggleButtons.length === 0 || modals.length === 0) {
        return;
    }
    
    // 각 토글 버튼과 모달 정보 출력
    toggleButtons.forEach((btn, i) => {
        console.log(`   토글 버튼 ${i+1}: data-modal="${btn.getAttribute('data-modal')}"`);
    });
    
    modals.forEach((modal, i) => {
        console.log(`   모달 ${i+1}: id="${modal.id}"`);
    });
    
    // 모달 열기 함수
    function openModal(modalId) {
        console.log(`🚀 openModal 함수 실행: ${modalId}`);
        
        // 지정된 모달 찾기
        const targetModal = document.getElementById(modalId + '-modal');
        console.log(`🎯 대상 모달 찾기: ${modalId}-modal`, targetModal);
        
        if (targetModal) {
            // 모달이 이미 열려있는지 확인
            if (targetModal.classList.contains('show')) {
                console.log(`⚠️ ${modalId} 모달이 이미 열려있음`);
                return;
            }
            
            // 모달 표시
            targetModal.style.display = 'block';
            
            // 강제 리플로우 후 애니메이션 시작
            targetModal.offsetHeight;
            
            setTimeout(() => {
                targetModal.classList.add('show');
                console.log(`✅ ${modalId} 모달 열림 완료`);
                
                // 드래그 기능 초기화
                initModalDrag(targetModal);
            }, 50);
        } else {
            console.error(`❌ 모달을 찾을 수 없음: ${modalId}-modal`);
        }
    }
    
    // 모달 닫기 함수
    function closeModal(modalId) {
        const targetModal = document.getElementById(modalId + '-modal');
        if (targetModal) {
            targetModal.classList.remove('show');
            setTimeout(() => {
                targetModal.style.display = 'none';
            }, 300);
            console.log(`${modalId} 모달 닫힘`);
        }
    }
    
    // 모든 모달 닫기 함수
    function closeAllModals() {
        modals.forEach(modal => {
            modal.classList.remove('show');
            setTimeout(() => {
                modal.style.display = 'none';
            }, 300);
        });
    }
    
    // 토글 버튼 이벤트 리스너
    toggleButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const modalType = this.getAttribute('data-modal');
            console.log(`${modalType} 버튼 클릭`);
            
            const targetModal = document.getElementById(modalType + '-modal');
            if (targetModal && targetModal.classList.contains('show')) {
                closeModal(modalType);
            } else {
                openModal(modalType);
            }
        });
    });
    
    // 모달 드래그 기능 초기화
    function initModalDrag(modal) {
        const header = modal.querySelector('.floating-modal-header');
        if (!header) return;
        
        let isDragging = false;
        let currentX;
        let currentY;
        let initialX;
        let initialY;
        let xOffset = 0;
        let yOffset = 0;
        
        // 현재 모달의 초기 위치 저장
        const rect = modal.getBoundingClientRect();
        const computedStyle = window.getComputedStyle(modal);
        
        header.addEventListener('mousedown', dragStart);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', dragEnd);
        
        function dragStart(e) {
            if (e.target === header || header.contains(e.target)) {
                // 닫기 버튼 클릭은 드래그하지 않음
                if (e.target.closest('.floating-modal-close')) {
                    return;
                }
                
                isDragging = true;
                
                // 현재 모달의 위치를 기준으로 드래그 시작점 계산
                const rect = modal.getBoundingClientRect();
                initialX = e.clientX - rect.left;
                initialY = e.clientY - rect.top;
                
                modal.style.transition = 'none';
                header.style.cursor = 'grabbing';
                console.log('🖱️ 드래그 시작');
                e.preventDefault();
            }
        }
        
        function drag(e) {
            if (isDragging) {
                e.preventDefault();
                
                // 마우스 현재 위치에서 초기 클릭 오프셋을 빼서 모달의 새 위치 계산
                currentX = e.clientX - offsetX;
                currentY = e.clientY - offsetY;
                
                // 화면 경계 제한
                const maxX = window.innerWidth - modal.offsetWidth;
                const maxY = window.innerHeight - modal.offsetHeight;
                
                currentX = Math.max(0, Math.min(maxX, currentX));
                currentY = Math.max(0, Math.min(maxY, currentY));
                
                // position을 fixed로 설정하고 left, top으로 위치 설정
                modal.style.position = 'fixed';
                modal.style.left = currentX + 'px';
                modal.style.top = currentY + 'px';
                modal.style.right = 'auto';
                modal.style.transform = 'none';
            }
        }
        
        function dragEnd(e) {
            if (isDragging) {
                isDragging = false;
                modal.style.transition = 'transform 0.3s ease';
                header.style.cursor = 'move';
                console.log('🖱️ 드래그 종료');
            }
        }
    }
    
    // 닫기 버튼 이벤트 리스너
    closeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const modalType = this.getAttribute('data-close');
            closeModal(modalType);
        });
    });
    
    // 모달 배경 클릭 시 닫기 제거 (사이드 패널은 클릭해도 닫히지 않음)
    // 대신 ESC 키로만 닫기 가능
    
    // ESC 키로 모든 모달 닫기
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAllModals();
        }
    });
    
    // 초기화 완료 표시
    window.floatingModalsInitialized = true;
    console.log('✅ 3개 플로팅 모달 시스템 초기화 완료');
    
    // 모달 데이터 초기화
    initModalData();
    
    // 테스트 함수 전역으로 등록
    window.testModal = function(modalId) {
        console.log(`🧪 테스트: ${modalId} 모달 열기`);
        openModal(modalId);
    };
  }
  
  // 모달 데이터 초기화 함수
  function initModalData() {
    console.log('📊 모달 데이터 초기화 시작');
    
    // 관련규정 데이터 로드
    initRegulationModal();
    
    // 내 문구 데이터 로드
    initMyPhrasesModal();
    
    console.log('📊 모달 데이터 초기화 완료');
  }
  
  // 관련규정 모달 초기화
  function initRegulationModal() {
    try {
        const regulationsScript = document.getElementById('regulations-data');
        if (regulationsScript) {
            const regulationsData = JSON.parse(regulationsScript.textContent);
            const textarea = document.querySelector('#regulation-modal textarea[name="related_regulations"]');
            
            if (textarea && regulationsData) {
                // 규정 데이터를 보기 좋게 포맷팅
                let regulationText = '=== 식품유형별 관련 규정 ===\n\n';
                
                if (typeof regulationsData === 'object') {
                    Object.entries(regulationsData).forEach(([key, value]) => {
                        // 키를 한글 제목으로 변환
                        const keyMapping = {
                            'prdlst_dcnm': '제품명상세',
                            'prdlst_nm': '제품명',
                            'ingredients_info': '성분명 및 함량',
                            'content_weight': '내용량',
                            'report_no': '품목보고번호',
                            'storage': '보관방법',
                            'package': '포장재질',
                            'manufacturer': '제조원 소재지'
                        };
                        
                        const title = keyMapping[key] || key;
                        regulationText += `📋 ${title}\n`;
                        regulationText += `${'='.repeat(30)}\n`;
                        
                        // 값을 줄바꿈으로 정리
                        if (typeof value === 'string') {
                            const cleanValue = value.trim()
                                .replace(/\n\s*\n/g, '\n')  // 중복 줄바꿈 제거
                                .replace(/^\s+/gm, '')     // 앞쪽 공백 제거
                                .replace(/\s+$/gm, '');    // 뒤쪽 공백 제거
                            regulationText += `${cleanValue}\n\n`;
                        } else {
                            regulationText += `${value}\n\n`;
                        }
                    });
                } else if (typeof regulationsData === 'string') {
                    regulationText += regulationsData;
                }
                
                textarea.value = regulationText;
                textarea.style.height = 'auto';
                textarea.style.height = Math.min(textarea.scrollHeight, 500) + 'px';
                console.log('✅ 관련규정 데이터 로드 완료');
            }
        }
    } catch (error) {
        console.error('❌ 관련규정 데이터 로드 실패:', error);
        const textarea = document.querySelector('#regulation-modal textarea[name="related_regulations"]');
        if (textarea) {
            textarea.value = '관련 규정 데이터를 불러오는 중 오류가 발생했습니다.\n\n다시 시도해주세요.';
        }
    }
  }
  
  // 내 문구 모달 초기화
  function initMyPhrasesModal() {
    try {
        const phrasesScript = document.getElementById('phrases-data');
        const modalBody = document.querySelector('#phrases-modal .modal-body');
        
        if (!modalBody) {
            console.error('❌ 내 문구 모달 컨테이너를 찾을 수 없습니다');
            return;
        }

        // 기본 컨테이너 생성
        modalBody.innerHTML = `
            <div class="phrases-container">
                <div class="phrases-header mb-3 d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">저장된 문구 목록</h5>
                    <button type="button" class="btn btn-primary btn-sm" onclick="addNewPhrase()">
                        ➕ 새 문구 추가
                    </button>
                </div>
                <div class="phrases-list" id="phrases-list">
                    <!-- 문구 목록이 여기에 동적으로 추가됩니다 -->
                </div>
                <div class="new-phrase-form" id="new-phrase-form" style="display: none;">
                    <div class="mt-3 p-3 border rounded bg-light">
                        <h6>새 문구 추가</h6>
                        <div class="mb-2">
                            <label class="form-label">문구 이름:</label>
                            <input type="text" class="form-control" id="new-phrase-name" placeholder="예: 보관방법 기본">
                        </div>
                        <div class="mb-2">
                            <label class="form-label">문구 내용:</label>
                            <textarea class="form-control" id="new-phrase-content" rows="3" placeholder="문구 내용을 입력하세요"></textarea>
                        </div>
                        <div class="mb-2">
                            <label class="form-label">카테고리:</label>
                            <select class="form-control" id="new-phrase-category">
                                <option value="보관방법">보관방법</option>
                                <option value="주의사항">주의사항</option>
                                <option value="성분정보">성분정보</option>
                                <option value="기타">기타</option>
                            </select>
                        </div>
                        <div class="text-end">
                            <button type="button" class="btn btn-secondary btn-sm me-2" onclick="cancelNewPhrase()">취소</button>
                            <button type="button" class="btn btn-success btn-sm" onclick="saveNewPhrase()">저장</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 문구 데이터 로드
        let phrasesData = [];
        if (phrasesScript) {
            try {
                const rawData = JSON.parse(phrasesScript.textContent);
                
                // 데이터 구조 정규화
                if (Array.isArray(rawData)) {
                    phrasesData = rawData.map((item, index) => {
                        if (typeof item === 'string') {
                            return { name: `문구 ${index + 1}`, content: item, category: '기타' };
                        }
                        return item;
                    });
                } else if (typeof rawData === 'object') {
                    // 카테고리별 데이터 처리
                    Object.entries(rawData).forEach(([category, phrases]) => {
                        if (Array.isArray(phrases)) {
                            phrases.forEach((phrase, index) => {
                                if (typeof phrase === 'string') {
                                    phrasesData.push({ 
                                        name: `${category} ${index + 1}`, 
                                        content: phrase, 
                                        category: category 
                                    });
                                } else {
                                    phrasesData.push({ ...phrase, category: category });
                                }
                            });
                        }
                    });
                }
            } catch (error) {
                console.warn('기존 문구 데이터 파싱 실패, 기본 데이터로 초기화');
                phrasesData = getDefaultPhrases();
            }
        } else {
            phrasesData = getDefaultPhrases();
        }

        // localStorage에서 추가 문구 로드
        const savedPhrases = localStorage.getItem('userPhrases');
        if (savedPhrases) {
            try {
                const userPhrases = JSON.parse(savedPhrases);
                phrasesData = [...phrasesData, ...userPhrases];
            } catch (error) {
                console.warn('사용자 저장 문구 로드 실패');
            }
        }

        displayPhrases(phrasesData);
        console.log('✅ 내 문구 모달 초기화 완료');
        
    } catch (error) {
        console.error('❌ 내 문구 모달 초기화 실패:', error);
        const modalBody = document.querySelector('#phrases-modal .modal-body');
        if (modalBody) {
            modalBody.innerHTML = `
                <div class="alert alert-danger">
                    내 문구 데이터를 불러오는 중 오류가 발생했습니다.<br>
                    페이지를 새로고침 후 다시 시도해주세요.
                </div>
            `;
        }
    }
  }
  
  // 문구 적용 함수
  window.applyPhrase = function(phrase) {
    // 현재 포커스된 필드에 문구 적용
    const activeElement = document.activeElement;
    if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
        activeElement.value = phrase;
        activeElement.dispatchEvent(new Event('change', { bubbles: true }));
        console.log(`✅ 문구 적용: "${phrase}"`);
        
        // 모달 닫기
        closeModal('phrases');
    } else {
        alert('먼저 적용할 입력 필드를 클릭해주세요.');
    }
  };

  // 기본 문구 데이터
  function getDefaultPhrases() {
    return [
        { name: "냉장보관 기본", content: "냉장보관(0~10℃)", category: "보관방법" },
        { name: "실온보관 기본", content: "직사광선을 피하고 서늘한 곳에 보관하세요", category: "보관방법" },
        { name: "냉동보관", content: "냉동보관(-18℃ 이하)", category: "보관방법" },
        { name: "어린이 주의사항", content: "어린이의 손이 닿지 않는 곳에 보관하세요", category: "주의사항" },
        { name: "개봉 후 주의", content: "개봉 후에는 냉장보관하시고 빠른 시일 내에 드세요", category: "주의사항" },
        { name: "알레르기 정보", content: "본 제품은 우유, 대두를 함유하고 있습니다", category: "성분정보" },
        { name: "제조원 표시", content: "제조원: (주)식품회사 / 소재지: 서울특별시", category: "기타" }
    ];
  }

  // 문구 목록 표시
  function displayPhrases(phrases) {
    const phrasesList = document.getElementById('phrases-list');
    if (!phrasesList) return;

    if (!phrases || phrases.length === 0) {
        phrasesList.innerHTML = '<div class="text-muted text-center py-3">저장된 문구가 없습니다.</div>';
        return;
    }

    // 카테고리별로 그룹화
    const groupedPhrases = {};
    phrases.forEach((phrase, globalIndex) => {
        const category = phrase.category || '기타';
        if (!groupedPhrases[category]) {
            groupedPhrases[category] = [];
        }
        groupedPhrases[category].push({ ...phrase, globalIndex });
    });

    let html = '';
    Object.entries(groupedPhrases).forEach(([category, categoryPhrases]) => {
        html += `
            <div class="category-group mb-4">
                <h6 class="category-title text-primary border-bottom pb-1">${category}</h6>
                <div class="phrases-in-category">
        `;
        
        categoryPhrases.forEach((phrase) => {
            html += `
                <div class="phrase-item border rounded p-3 mb-2 hover-shadow">
                    <div class="phrase-header d-flex justify-content-between align-items-start mb-2">
                        <strong class="phrase-name text-dark">${phrase.name}</strong>
                        <div class="phrase-actions">
                            <button type="button" class="btn btn-sm btn-primary me-1" 
                                    onclick="applyPhrase('${phrase.content.replace(/'/g, "\\'")}')">
                                ✓ 적용
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary me-1" 
                                    onclick="editPhrase(${phrase.globalIndex})">
                                ✏️ 수정
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger" 
                                    onclick="deletePhrase(${phrase.globalIndex})">
                                🗑️ 삭제
                            </button>
                        </div>
                    </div>
                    <div class="phrase-content text-muted small bg-light p-2 rounded">${phrase.content}</div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });

    phrasesList.innerHTML = html;
  }

  // 새 문구 추가 폼 표시
  window.addNewPhrase = function() {
    document.getElementById('new-phrase-form').style.display = 'block';
    document.getElementById('new-phrase-name').focus();
  };

  // 새 문구 추가 취소
  window.cancelNewPhrase = function() {
    document.getElementById('new-phrase-form').style.display = 'none';
    document.getElementById('new-phrase-name').value = '';
    document.getElementById('new-phrase-content').value = '';
    document.getElementById('new-phrase-category').value = '보관방법';
  };

  // 새 문구 저장
  window.saveNewPhrase = function() {
    const name = document.getElementById('new-phrase-name').value.trim();
    const content = document.getElementById('new-phrase-content').value.trim();
    const category = document.getElementById('new-phrase-category').value;

    if (!name || !content) {
        alert('문구 이름과 내용을 모두 입력해주세요.');
        return;
    }

    // 사용자 저장 문구 가져오기
    let userPhrases = [];
    try {
        const saved = localStorage.getItem('userPhrases');
        if (saved) {
            userPhrases = JSON.parse(saved);
        }
    } catch (error) {
        console.warn('기존 사용자 문구 로드 실패');
    }

    // 새 문구 추가
    const newPhrase = { name, content, category };
    userPhrases.push(newPhrase);

    // localStorage에 저장
    try {
        localStorage.setItem('userPhrases', JSON.stringify(userPhrases));
        console.log('✅ 새 문구 저장 완료:', newPhrase);
        
        // 화면 새로고침
        initMyPhrasesModal();
        cancelNewPhrase();
        
    } catch (error) {
        console.error('❌ 문구 저장 실패:', error);
        alert('문구 저장에 실패했습니다.');
    }
  };

  // 문구 수정
  window.editPhrase = function(globalIndex) {
    // TODO: 문구 수정 기능 구현
    alert('문구 수정 기능은 개발 중입니다.');
  };

  // 문구 삭제
  window.deletePhrase = function(globalIndex) {
    if (!confirm('이 문구를 삭제하시겠습니까?')) {
        return;
    }

    try {
        // 사용자 저장 문구만 삭제 가능
        let userPhrases = [];
        const saved = localStorage.getItem('userPhrases');
        if (saved) {
            userPhrases = JSON.parse(saved);
        }

        // 기본 문구 개수 계산
        const defaultCount = getDefaultPhrases().length;
        
        if (globalIndex >= defaultCount) {
            // 사용자 문구 삭제
            const userIndex = globalIndex - defaultCount;
            userPhrases.splice(userIndex, 1);
            localStorage.setItem('userPhrases', JSON.stringify(userPhrases));
            
            console.log('✅ 문구 삭제 완료');
            initMyPhrasesModal(); // 화면 새로고침
        } else {
            alert('기본 제공 문구는 삭제할 수 없습니다.');
        }
        
    } catch (error) {
        console.error('❌ 문구 삭제 실패:', error);
        alert('문구 삭제에 실패했습니다.');
    }
  };

  // 스마트 추천 모달 초기화는 통합 시스템에서 처리됨 (comprehensive_recommendation.js)
  
  // 기존 추천 시스템 열기
  window.openExistingRecommendation = function() {
    // 다양한 방법으로 기존 추천 모달 찾기 및 열기
    try {
        // 방법 1: 기존 함수 호출
        if (typeof openRecommendationModal === 'function') {
            openRecommendationModal();
            return;
        }
        
        // 방법 2: Bootstrap 모달 찾기
        const modalIds = ['recommendationModal', 'smartRecommendationModal', 'autoFillModal'];
        for (const modalId of modalIds) {
            const modalElement = document.getElementById(modalId);
            if (modalElement) {
                if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();
                    return;
                } else if (typeof $ !== 'undefined') {
                    $(modalElement).modal('show');
                    return;
                }
            }
        }
        
        // 방법 3: 기존 스마트 추천 시스템 직접 호출
        if (window.smartRecommendationModal) {
            if (typeof window.smartRecommendationModal.openModal === 'function') {
                window.smartRecommendationModal.openModal();
                return;
            }
            if (typeof window.smartRecommendationModal.showRecommendations === 'function') {
                window.smartRecommendationModal.showRecommendations();
                return;
            }
        }
        
        // 방법 4: comprehensive recommendation 시스템 호출
        if (window.comprehensiveRecommendation) {
            if (typeof window.comprehensiveRecommendation.showModal === 'function') {
                window.comprehensiveRecommendation.showModal();
                return;
            }
        }
        
        // 모든 방법이 실패하면 현재 모달에서 추천 생성
        generateRecommendation();
        
    } catch (error) {
        console.error('기존 추천 시스템 열기 실패:', error);
        alert('기존 추천 시스템을 찾을 수 없습니다. 새로운 추천을 생성합니다.');
        generateRecommendation();
    }
  };

  // 전체 추천 불러오기
  window.loadComprehensiveRecommendation = function() {
    try {
        // 기존 comprehensive recommendation 시스템 호출
        if (window.comprehensiveRecommendation && typeof window.comprehensiveRecommendation.loadAllRecommendations === 'function') {
            window.comprehensiveRecommendation.loadAllRecommendations();
            return;
        }
        
        // 기존 시스템이 없으면 전체 추천 생성
        document.getElementById('recommendation-type').value = 'all';
        generateRecommendation();
        
    } catch (error) {
        console.error('전체 추천 불러오기 실패:', error);
        console.warn('전체 추천 시스템을 찾을 수 없습니다. 새로운 전체 추천을 생성합니다.');
        document.getElementById('recommendation-type').value = 'all';
        generateRecommendation();
    }
  };

  // AI 추천 생성 함수 (기존 시스템과 연동)
  window.generateRecommendation = function() {
    const loadingDiv = document.getElementById('recommendation-loading');
    const resultsDiv = document.getElementById('recommendation-results');
    const recommendationType = document.getElementById('recommendation-type').value;
    
    // 로딩 표시
    loadingDiv.style.display = 'block';
    resultsDiv.style.display = 'none';
    
    // 폼 데이터 수집
    const formData = collectFormData();
    
    // 기존 스마트 추천 시스템 호출
    if (window.smartRecommendationModal && typeof window.smartRecommendationModal.generateRecommendations === 'function') {
        // 기존 시스템과 연동
        window.smartRecommendationModal.generateRecommendations(recommendationType, formData)
            .then(recommendations => {
                displayRecommendations(recommendations);
                loadingDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
            })
            .catch(error => {
                console.error('AI 추천 생성 실패:', error);
                // 실패 시 모의 데이터로 대체
                const mockRecommendations = generateMockRecommendations(recommendationType, formData);
                displayRecommendations(mockRecommendations);
                loadingDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
            });
    } else {
        // 기존 시스템이 없으면 모의 추천 생성
        setTimeout(() => {
            const recommendations = generateMockRecommendations(recommendationType, formData);
            displayRecommendations(recommendations);
            
            loadingDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
        }, 2000);
    }
  };

  // 폼 데이터 수집
  function collectFormData() {
    const data = {};
    
    // 기본 제품 정보
    data.productName = document.querySelector('input[name="prdlst_dcnm"]')?.value || '';
    data.foodType = document.querySelector('input[name="bar_cd"]:checked')?.closest('.form-check')?.querySelector('label')?.textContent || '';
    data.ingredients = document.querySelector('textarea[name="rawmtrl_nm"]')?.value || '';
    data.packaging = document.querySelector('input[name="pkg_fom_nm"]')?.value || '';
    data.manufacturer = document.querySelector('input[name="manufacture"]')?.value || '';
    
    // 추가 정보
    data.weight = document.querySelector('input[name="cntnts_cn"]')?.value || '';
    data.storage = document.querySelector('textarea[name="srvng_method"]')?.value || '';
    data.shelfLife = document.querySelector('input[name="expiry_date"]')?.value || '';
    
    return data;
  }

  // 모의 AI 추천 생성
  function generateMockRecommendations(type, formData) {
    const recommendations = {
        storage: [
            {
                title: "보관방법 추천",
                content: "직사광선을 피하고 서늘하고 건조한 곳에 보관하세요.",
                confidence: 95,
                reason: "일반적인 가공식품의 표준 보관방법입니다."
            },
            {
                title: "개봉 후 보관",
                content: "개봉 후에는 냉장보관하시고 가능한 빨리 드세요.",
                confidence: 88,
                reason: "제품의 신선도 유지를 위한 권장사항입니다."
            }
        ],
        ingredients: [
            {
                title: "주요 성분 표시",
                content: "밀가루, 설탕, 식용유지, 소금 (함량 순)",
                confidence: 92,
                reason: "입력된 원재료명을 기준으로 생성되었습니다."
            },
            {
                title: "알레르기 정보",
                content: "본 제품은 밀, 대두를 함유하고 있습니다.",
                confidence: 85,
                reason: "주요 알레르기 유발 성분을 식별했습니다."
            }
        ],
        warnings: [
            {
                title: "일반 주의사항",
                content: "어린이의 손이 닿지 않는 곳에 보관하세요.",
                confidence: 90,
                reason: "식품 안전을 위한 기본 주의사항입니다."
            },
            {
                title: "섭취 시 주의",
                content: "과다 섭취 시 복통이나 설사를 일으킬 수 있습니다.",
                confidence: 75,
                reason: "일반적인 가공식품 섭취 주의사항입니다."
            }
        ]
    };

    return type === 'all' ? 
        [...recommendations.storage, ...recommendations.ingredients, ...recommendations.warnings] :
        recommendations[type] || [];
  }

  // 추천 결과 표시
  function displayRecommendations(recommendations) {
    const resultsDiv = document.getElementById('recommendation-results');
    
    if (!recommendations || recommendations.length === 0) {
        resultsDiv.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-exclamation-circle fa-2x mb-2 opacity-50"></i>
                <p>추천할 수 있는 내용이 없습니다.<br>제품 정보를 더 입력해주세요.</p>
            </div>
        `;
        return;
    }

    let html = '<div class="recommendations-list">';
    
    recommendations.forEach((rec, index) => {
        const confidenceColor = rec.confidence >= 90 ? 'success' : rec.confidence >= 80 ? 'warning' : 'secondary';
        
        html += `
            <div class="recommendation-item border rounded p-3 mb-3">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="recommendation-title mb-1">${rec.title}</h6>
                    <span class="badge bg-${confidenceColor}">${rec.confidence}%</span>
                </div>
                <div class="recommendation-content bg-light p-2 rounded mb-2">
                    ${rec.content}
                </div>
                <div class="recommendation-reason small text-muted mb-2">
                    💡 ${rec.reason}
                </div>
                <div class="recommendation-actions">
                    <button type="button" class="btn btn-sm btn-primary me-2" 
                            onclick="applyRecommendation('${rec.content.replace(/'/g, "\\'")}')">
                        ✓ 적용
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" 
                            onclick="customizeRecommendation(${index})">
                        ✏️ 수정 후 적용
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    resultsDiv.innerHTML = html;
  }

  // 추천 내용 적용
  window.applyRecommendation = function(content) {
    const activeElement = document.activeElement;
    if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
        activeElement.value = content;
        activeElement.dispatchEvent(new Event('change', { bubbles: true }));
        console.log(`✅ AI 추천 적용: "${content}"`);
        
        // 모달 닫기
        closeModal('smart-recommendation');
    } else {
        alert('추천 내용을 적용할 입력 필드를 먼저 클릭해주세요.');
    }
  };

  // 추천 내용 커스터마이징
  window.customizeRecommendation = function(index) {
    alert('추천 내용 커스터마이징 기능은 개발 중입니다.');
  };

  // 스마트 추천 모달 초기화
  initSingleCheckboxGroups();
  
  // DOM 로드 완료 후 모달 시스템 초기화
  document.addEventListener('DOMContentLoaded', function() {
    console.log('🔄 DOM 로드 완료 - 모달 시스템 초기화 시작');
    
    // 데이터 스크립트 확인
    const phrasesScript = document.getElementById('phrases-data');
    const regulationsScript = document.getElementById('regulations-data');
    const smartScript = document.getElementById('smart-recommendation-data');
    
    console.log('📄 데이터 스크립트 상태 확인:');
    console.log('  - phrases-data:', phrasesScript ? '✅ 존재' : '❌ 없음');
    console.log('  - regulations-data:', regulationsScript ? '✅ 존재' : '❌ 없음');
    console.log('  - smart-recommendation-data:', smartScript ? '✅ 존재' : '❌ 없음');
    
    if (phrasesScript) {
        try {
            const data = JSON.parse(phrasesScript.textContent);
            console.log('  - phrases 데이터 타입:', typeof data, '길이:', Array.isArray(data) ? data.length : Object.keys(data).length);
        } catch (e) {
            console.error('  - phrases 데이터 파싱 오류:', e);
        }
    }
    
    if (regulationsScript) {
        try {
            const data = JSON.parse(regulationsScript.textContent);
            console.log('  - regulations 데이터 타입:', typeof data, '키 개수:', Object.keys(data).length);
        } catch (e) {
            console.error('  - regulations 데이터 파싱 오류:', e);
        }
    }
    
    // 모든 모달 초기화 (스마트 추천은 통합 시스템에서 처리)
    setTimeout(() => {
        initRegulationModal(); 
        initMyPhrasesModal();
        initRightPanel();
    }, 100);
  });
  
  // 페이지 완전 로드 후에도 한 번 더 시도
  window.addEventListener('load', function() {
    console.log('🔄 페이지 완전 로드 완료 - 모달 시스템 재확인');
    if (!window.floatingModalsInitialized) {
      initRightPanel();
    }
  });
  
  // '항목별 문구 및 규정' 탭 클릭 시 강제 새로고침
  document.addEventListener('DOMContentLoaded', function () {
    var myPhrasesTab = document.getElementById('myphrases-tab');
    if (myPhrasesTab) {
      myPhrasesTab.addEventListener('click', function () {
        reloadPhraseTab();
      });
    }
  });

  // 라벨명 동기화 함수
  function initializeLabelNameSync() {
    const form = document.getElementById('labelForm');
    const topInput = document.getElementById('my_label_name_top');
    const hiddenInput = document.getElementById('my_label_name_hidden');
    
    if (form && topInput && hiddenInput) {
      // 상단 입력 필드 변경 시 숨겨진 필드도 동기화
      topInput.addEventListener('input', function() {
        hiddenInput.value = topInput.value;
      });
      
      // 폼 제출 전 최종 동기화
      form.addEventListener('submit', function(e) {
        // 폼 제출 직전에 라벨명 동기화
        hiddenInput.value = topInput.value;
      });
      
      // 초기값 동기화 - 양방향
      if (topInput.value && !hiddenInput.value) {
        hiddenInput.value = topInput.value;
      } else if (hiddenInput.value && !topInput.value) {
        topInput.value = hiddenInput.value;
      }
      
      // 페이지 로드 시 값이 모두 있는 경우 상단 필드 우선
      if (topInput.value) {
        hiddenInput.value = topInput.value;
      }
    }
  }

  // 내용량 필드 초기화 및 설정
  function initializeContentWeightFields() {
    const contentWeightInput = document.getElementById('content_weight_input');
    const contentWeightCheckbox = document.getElementById('chk_content_weight');
    const contentTypeDisplay = document.getElementById('content_type_display');
    
    // 초기 상태 설정
    function updateContentFieldsState() {
      if (contentWeightCheckbox && contentWeightInput) {
        const isChecked = contentWeightCheckbox.checked;
        contentWeightInput.disabled = !isChecked;
        contentWeightInput.classList.toggle('disabled-textarea', !isChecked);
        
        // 텍스트 표시 상태 업데이트
        if (contentTypeDisplay) {
          if (isChecked) {
            contentTypeDisplay.style.color = '#495057';
            contentTypeDisplay.style.opacity = '1';
          } else {
            contentTypeDisplay.style.color = '#6c757d';
            contentTypeDisplay.style.opacity = '0.6';
          }
        }
        
        // hidden 필드 값 설정 - 모든 데이터는 content_weight 필드에만 저장
        const hiddenContentWeight = document.querySelector('input[name="chckd_content_weight"]');
        const hiddenWeightCalorie = document.querySelector('input[name="chckd_weight_calorie"]');
        if (hiddenContentWeight) hiddenContentWeight.value = isChecked ? 'Y' : 'N';
        if (hiddenWeightCalorie) hiddenWeightCalorie.value = 'N'; // 항상 N으로 설정
      }
    }
    
    // 체크박스 변경 이벤트
    if (contentWeightCheckbox) {
      contentWeightCheckbox.addEventListener('change', function() {
        updateContentFieldsState();
      });
    }
    
    // 초기 상태 설정
    updateContentFieldsState();
    
    // 페이지 로드 시 식품유형에 따른 내용량 타입 초기 설정
    const foodTypeSelect = document.getElementById('food_type');
    if (foodTypeSelect && foodTypeSelect.value) {
      // 선택된 식품유형의 weight_calorie 값 확인
      const selectedOption = foodTypeSelect.options[foodTypeSelect.selectedIndex];
      if (selectedOption && selectedOption.dataset.weightCalorie) {
        const weightCalorieValue = selectedOption.dataset.weightCalorie;
        // JavaScript 함수 호출하여 내용량 타입 설정
        if (typeof updateContentTypeByFoodType === 'function') {
          updateContentTypeByFoodType(weightCalorieValue);
        }
      }
    }
  }

  // DOM 로드 완료 시 초기화 함수들 실행
  document.addEventListener('DOMContentLoaded', function() {
    initializeLabelNameSync();
    initializeContentWeightFields();
  });
  
  // 플로팅 모달 드래그 기능 강화
  function ensureModalDrag() {
    const modals = ['smart-recommendation-modal', 'regulation-modal', 'phrases-modal'];
    modals.forEach(modalId => {
      const modal = document.getElementById(modalId);
      if (modal && !modal.dataset.dragInitialized) {
        initModalDrag(modal);
        modal.dataset.dragInitialized = 'true';
        console.log(`✅ ${modalId} 드래그 초기화 완료`);
      }
    });
  }
  
  // 모달 열기 시 드래그 재초기화
  window.addEventListener('load', function() {
    setTimeout(ensureModalDrag, 500);
  });
  
  // MutationObserver로 동적 모달 감지
  if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(function(node) {
            if (node.nodeType === 1 && node.classList && node.classList.contains('floating-modal')) {
              setTimeout(() => ensureModalDrag(), 100);
            }
          });
        }
      });
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }
});

// 원재료명(참고) 원재료 표로 입력 팝업 함수
window.openIngredientTablePopup = function() {
  console.log('🔧 openIngredientTablePopup 함수 호출됨');
  
  try {
    const labelId = document.getElementById('label_id')?.value || '';
    console.log('📝 Label ID:', labelId);
    
    // 기존 원재료명(참고) 데이터 수집
    const rawMaterialField = document.getElementById('rawmtrl_nm');
    const existingData = {};
    
    if (rawMaterialField && rawMaterialField.value.trim()) {
      existingData.existing_ingredients = rawMaterialField.value.trim();
      console.log('📋 기존 원재료 데이터:', existingData.existing_ingredients);
    }
    
    // 제품명 추가 (참고용)
    const productNameField = document.querySelector('input[name="prdlst_nm"]');
    if (productNameField && productNameField.value.trim()) {
      existingData.product_name = productNameField.value.trim();
      console.log('🏷️ 제품명:', existingData.product_name);
    }
    
    // 원재료 팝업 URL 구성
    let url = `/label/ingredient-popup/?label_id=${labelId}`;
    if (existingData && Object.keys(existingData).length > 0) {
      const params = new URLSearchParams();
      Object.keys(existingData).forEach(key => {
        if (existingData[key]) {
          params.append(key, existingData[key]);
        }
      });
      url += '&' + params.toString();
    }
    
    console.log('🌐 팝업 URL:', url);
    
    // openPopup 함수 존재 확인
    if (typeof window.openPopup === 'function') {
      console.log('✅ openPopup 함수 발견, 팝업 열기 시도');
      // 원재료 팝업 창 열기
      openPopup(url, 'IngredientPopup', 1000, 800);
    } else {
      console.error('❌ openPopup 함수를 찾을 수 없습니다');
      alert('팝업 함수를 찾을 수 없습니다. 페이지를 새로고침해주세요.');
    }
    
  } catch (error) {
    console.error('💥 원재료 표로 입력 팝업 열기 오류:', error);
    alert('원재료 표로 입력 기능을 열 수 없습니다. 잠시 후 다시 시도해주세요.');
  }
};