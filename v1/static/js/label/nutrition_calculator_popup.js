// 영양성분 계산기 모듈 - 리팩토링된 버전
(function() {
'use strict';

// 영양성분 상수는 constants.js에서 로드됨
// window.NUTRITION_DATA, window.EMPHASIS_CRITERIA 사용

// 전역 변수
let currentNutritionData = {};

/* 지난번에 물려 저장한 오차(%). **값에 이미 들어 있는 것**이라 다시 물리지
   않는다. 화면에 적어 주고, 새로 물리지 않았으면 저장할 때 그대로 남긴다. */
let savedTolerance = '';

// ===== 유틸리티 함수들 =====

// formatNumberWithCommas / processNutritionValue 는
// **nutrition_display.js 한 곳에만** 둔다.
//
// 같은 규칙이 여기와 label_preview.js 에 따로 있었고 **둘이 서로 달랐다** —
// 계산기에서 확인한 표와 실제로 인쇄되는 표의 숫자가 갈렸다. 이 파일을
// 읽는 화면은 nutrition_display.js 를 먼저 읽는다.

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

/*
 * 입력 기준 -> 100 g(mL) 당 환산 계수.
 *
 * 라벨의 영양성분표는 그 표가 밝힌 기준으로 인쇄돼 있다.
 *
 *     총 내용량 65 g / 65 g 당 309 kcal
 *
 * 그런데 저장 칸(MyLabel.calories 등)은 **언제나 100 g 당**이다. 표를 그릴 때
 * generateBasicDisplayV3 이 `값 x 표시량/100` 으로 되돌리고, 규정 검증도 그
 * 약속 위에서 내용량의 병기 열량과 견준다.
 *
 * 예전에는 그 환산을 사용자가 손으로 해야 했다. 라벨을 옮겨 적는 사람이 그걸
 * 알 리가 없어서 309 를 그대로 넣었고, 화면은 309 x 65/100 = 200 kcal 로 표를
 * 그렸으며, 검증은 "열량이 맞지 않습니다" 를 냈다. **셋 다 자기 규칙에는
 * 맞았고, 사용자만 고칠 데를 못 찾았다.**
 *
 * 사진 판독은 표의 기준을 읽어 이미 이 환산을 한다(ocr_apply.to_per_100).
 * 손으로 넣는 쪽도 같은 일을 하게 한다.
 */
/** 칸에 적힌 글자 그대로. 없으면 빈 문자열 */
function valueOf(id) {
  var el = document.getElementById(id);
  return el ? String(el.value || '').trim() : '';
}

function numberFrom(id, fallback) {
  var el = document.getElementById(id);
  var value = el ? parseFloat(String(el.value || '').replace(/,/g, '')) : NaN;
  return isNaN(value) ? fallback : value;
}

function inputBasisFactor() {
  var basis = document.getElementById('nutrition_input_basis');
  var mode = basis ? basis.value : 'per_100';
  if (mode !== 'total' && mode !== 'unit') return 1;

  var baseAmount = numberFrom('serving_size', 0);
  var count = numberFrom('units_per_package', 1);
  var amount = (mode === 'total') ? baseAmount * count : baseAmount;

  // 기준량을 모르면 환산하지 않는다. 분모를 모르면서 곱하면 모든 수치의 뜻이
  // 바뀐다 — 그건 안 고치느니만 못하다.
  if (!(amount > 0)) return 1;
  return 100 / amount;
}

/* 지금 고른 기준으로 무엇이 저장되는지 그 자리에서 보여 준다.
   환산은 저장할 때 한 번 일어나고, 다시 열면 100 g 당 값이 보인다.
   말해 두지 않으면 "내가 넣은 숫자가 왜 바뀌었지" 가 된다. */
function updateInputBasisNote() {
  var note = document.getElementById('inputBasisNote');
  if (!note) return;
  var basis = document.getElementById('nutrition_input_basis');
  var mode = basis ? basis.value : 'per_100';
  if (mode === 'per_100') {
    note.textContent = '';
    note.style.display = 'none';
    return;
  }
  var factor = inputBasisFactor();
  if (factor === 1) {
    note.textContent = '단위량(과 포장개수)을 먼저 넣어 주세요. 기준량을 모르면 환산할 수 없습니다.';
    note.style.display = 'block';
    return;
  }
  var kcal = numberFrom('calories', NaN);
  var label = (mode === 'total') ? '총 내용량' : '단위량';
  var sample = isNaN(kcal) ? ''
    : ' (예: 열량 ' + kcal + ' → ' + Math.round(kcal * factor) + ')';
  note.textContent = label + '당으로 넣은 값을 100 g(mL) 당으로 환산해 저장합니다'
    + sample + '. 다시 열면 환산된 값이 보입니다.';
  note.style.display = 'block';
}
window.updateInputBasisNote = updateInputBasisNote;

// ===== 데이터 수집 헬퍼 함수 =====
/**
 * @description DOM에서 현재 입력된 모든 영양성분 값을 읽어 객체로 반환합니다.
 * @returns {Object} 영양성분 키와 숫자 값으로 구성된 객체
 */
function getNutritionInputsFromDOM() {
  // **여기서 100 g(mL) 당으로 맞춘다.** 미리보기도 저장도 이 함수를 지나므로,
  // 환산을 한 곳에서 하면 화면에 그린 표와 저장되는 값이 어긋날 수가 없다.
  // (예전에는 환산이 아예 없어서, 라벨의 "65 g 당 309 kcal" 을 그대로 넣으면
  //  표가 309 x 65/100 = 200 kcal 로 그려졌다. 사용자는 단위량을 100 으로
  //  바꿔 표를 맞췄고, 그러면 총 내용량이 100 g 으로 찍혔다.)
  // **저장되는 것은 적용값이다.** 화면의 칸에 적힌 것은 계산값이고, 라벨에
  // 인쇄될 값은 거기에 오차를 물린 것이다. 오차를 안 쓰면 둘이 같다.
  const factor = inputBasisFactor();
  const adjusted = adjustedNutritionValues();
  const nutritionInputs = {};
  Object.keys(adjusted).forEach(key => {
    const numericValue = parseFloat(adjusted[key]);
    if (!isNaN(numericValue) && numericValue >= 0) {
      // 소수점 2자리까지 반올림
      nutritionInputs[key] = Math.round(numericValue * factor * 100) / 100;
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
        <input type="text" inputmode="decimal" id="${key}" name="${key}" placeholder="0" data-nutrition-key="${key}">
        <span class="unit-label">${data.unit}</span>
        <span class="nutrient-derived" data-derived="${key}"></span>
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
        <input type="text" inputmode="decimal" id="${key}" name="${key}" placeholder="0" data-nutrition-key="${key}">
        <span class="unit-label">${data.unit}</span>
        <span class="nutrient-derived" data-derived="${key}"></span>
      `;
      additionalContainer.appendChild(div);
    });
    
  // 모든 영양성분 입력 필드에 3자리 쉼표 이벤트 리스너 추가
  attachCommaFormattingToInputs();

  // 환산 예시("열량 309 -> 475")를 열량 칸에 맞춰 갱신한다
  var caloriesInput = document.getElementById('calories');
  if (caloriesInput) caloriesInput.addEventListener('input', updateInputBasisNote);

  // 계산값을 고치면 적용값·표시될 값이 그 자리에서 따라간다
  Object.keys(NUTRITION_DATA).forEach(function (key) {
    var input = document.getElementById(key);
    if (input) input.addEventListener('input', refreshDerived);
  });
  refreshDerived();
}

// 쉼표 포맷팅 공통 함수
function applyCommaFormatting(e) {
  let value = e.target.value;
  
  // 쉼표 제거
  value = value.replace(/,/g, '');
  
  // 숫자와 소수점만 허용
  value = value.replace(/[^\d.]/g, '');
  
  // 소수점이 여러 개 입력된 경우 첫 번째 것만 유지
  const parts = value.split('.');
  if (parts.length > 2) {
    value = parts[0] + '.' + parts.slice(1).join('');
  }
  
  // 소수점 이하 2자리 제한
  if (parts.length === 2 && parts[1] && parts[1].length > 2) {
    value = parts[0] + '.' + parts[1].substring(0, 2);
  }
  
  // 정수부에 쉼표 추가
  if (value !== '') {
    const updatedParts = value.split('.');
    if (updatedParts[0] !== '') {
      updatedParts[0] = Number(updatedParts[0]).toLocaleString('ko-KR');
    }
    value = updatedParts.join('.');
  }
  
  e.target.value = value;
}

// 3자리 쉼표 포맷팅 기능 추가
function attachCommaFormattingToInputs() {
  // 모든 영양성분 입력 필드 선택
  const nutritionInputs = document.querySelectorAll('input[data-nutrition-key]');
  
  nutritionInputs.forEach(input => {
    // 기존 이벤트 리스너 제거 (중복 방지)
    input.removeEventListener('input', applyCommaFormatting);
    // 새로운 이벤트 리스너 추가
    input.addEventListener('input', applyCommaFormatting);
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
    // 숫자 값을 쉼표 포맷팅
    const formattedValue = parseFloat(result.value).toLocaleString('ko-KR');
    
    html += `<div class="emphasis-item emphasis-eligible">`;
    html += `<div class="emphasis-nutrient-name">${result.label} (${formattedValue} ${result.unit})</div>`;
    
    html += '<div class="emphasis-labels">';
    result.emphasisResult.forEach(emphasis => {
      // 임계값도 쉼표 포맷팅
      const formattedThreshold = parseFloat(emphasis.threshold).toLocaleString('ko-KR');
      html += `<span class="emphasis-badge ${emphasis.type}">${emphasis.label}</span>`;
      html += `<span class="emphasis-threshold">${formattedThreshold} ${result.unit} ${emphasis.type === 'free' ? '미만' : emphasis.type === 'low' ? '이하' : '이상'}</span>`;
    });
    html += '</div>';
    
    html += '</div>';
  });
  
  emphasisContent.innerHTML = html;
  emphasisContainer.style.display = 'block';
}

// 영양성분 계산 메인 함수
function calculateNutrition() {
  const baseAmount = parseFloat(document.getElementById('serving_size').value.replace(/,/g, '')) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('units_per_package').value.replace(/,/g, '')) || 1;
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

  const baseAmount = parseFloat(document.getElementById('serving_size').value.replace(/,/g, '')) || 100;
  const servingsPerPackage = parseFloat(document.getElementById('units_per_package').value.replace(/,/g, '')) || 1;
  const style = document.getElementById('nutrition_display_unit').value;
  // 표를 그리는 쪽(generateBasicDisplayV3)과 같은 이름을 쓴다.
  // 예전 기본값 'per_100g' 는 그쪽 switch 에 없어 조용히 총량당이 됐다.
  const basicDisplayType = normalizeBasicDisplayType(
    document.getElementById('basic_display_type')?.value);
  const parallelDisplayType = document.getElementById('parallel_display_type')?.value || 'per_serving';

  // 입력된 영양성분만 전달 (빈 값 제외)
  const formattedData = {};
  Object.keys(nutritionDataToSave).forEach(key => {
    const nutritionInfo = NUTRITION_DATA[key];
    if (nutritionInfo && nutritionDataToSave[key] !== '' && nutritionDataToSave[key] != null) {
      // 쉼표 제거된 숫자 값으로 저장
      const numericValue = parseFloat(String(nutritionDataToSave[key]).replace(/,/g, ''));
      formattedData[key] = {
        label: nutritionInfo.label,
        value: isNaN(numericValue) ? nutritionDataToSave[key] : numericValue,
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
        /* 화면에 g/ml 고르개가 있는데(html:36) 이 값을 안 보냈다. 부모가
           `|| 'g'` 로 채우므로, ml 로 표시하는 제품이 계산기 저장 한 번에
           g 가 됐다. */
        serving_size_unit: valueOf('serving_size_unit') || 'g',
        units_per_package: servingsPerPackage,
        nutrition_display_unit: style,
        basic_display_type: basicDisplayType,
        parallel_display_type: parallelDisplayType,
        /* 이론치로 만든 표는 그 자체가 감사 대상이다. 무엇으로 어떻게 냈는지가
           값과 함께 남아야 한다. 1회 섭취참고량은 고열량·저영양 판정의 분모다. */
        serving_reference: valueOf('serving_reference'),
        hieng_kind: valueOf('hieng_kind'),
        nutrition_source: valueOf('nutrition_source'),
        nutrition_source_note: valueOf('nutrition_source_note'),
        nutrition_tolerance: (valueOf('nutrition_source') === 'theory')
            ? (toleranceSetting().rate > 0
                ? String(toleranceSetting().rate) : savedTolerance)
            : ''
      },
      html: document.getElementById('resultDisplay').innerHTML
    }
  };

  // 계산기에서 전송할 데이터 정보 (디버그 로그 제거)

  if (window.opener && typeof window.opener.postMessage === 'function') {
    window.opener.postMessage(dataToSend, '*');
    
    // 저장 버튼 피드백
    const saveBtn = document.querySelector('button[onclick="sendNutritionDataToParent()"]');
    if (saveBtn) {
      const originalText = saveBtn.innerHTML;
      const originalClass = saveBtn.className;
      
      saveBtn.className = 'btn btn-success';
      saveBtn.innerHTML = '<i class="fas fa-check me-1"></i>저장완료';
      
      // 1.5초 후 원래 상태로 복구
      setTimeout(() => {
        saveBtn.className = originalClass;
        saveBtn.innerHTML = originalText;
      }, 1500);
    }
  } else {
    // 저장 실패 버튼 피드백
    const saveBtn = document.querySelector('button[onclick="sendNutritionDataToParent()"]');
    if (saveBtn) {
      const originalText = saveBtn.innerHTML;
      const originalClass = saveBtn.className;
      
      saveBtn.className = 'btn btn-danger';
      saveBtn.innerHTML = '<i class="fas fa-times me-1"></i>저장실패';
      
      setTimeout(() => {
        saveBtn.className = originalClass;
        saveBtn.innerHTML = originalText;
      }, 3000);
    }
  }
}

// PDF 내보내기
async function exportToPDF() {
  const nutritionContainer = document.querySelector('#resultDisplay .nutrition-result-table, #resultDisplay .nutrition-style-basic, #resultDisplay .nutrition-style-parallel');
  
  if (!nutritionContainer) {
    alert('먼저 영양성분을 계산해주세요.');
    return;
  }
  
  // PDF 저장 로깅
  const urlParams = new URLSearchParams(window.location.search);
  const labelId = urlParams.get('label_id');
  if (labelId) {
    try {
      await fetch('/label/log-pdf-save/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': typeof getCookie === 'function' ? getCookie('csrftoken') : ''
        },
        body: JSON.stringify({ 
          label_id: labelId,
          source: 'calculator'
        })
      });
    } catch (logError) {
      console.warn('로깅 실패:', logError);
    }
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
    
    // 입력 기준은 **언제나 100 g 당으로 되돌린다.**
    // 저장된 값이 이미 100 g 당이라, 기준이 '총 내용량당' 인 채로 다시 저장하면
    // 같은 값에 환산이 두 번 걸린다(309 -> 475 -> 731).
    const inputBasisEl = document.getElementById('nutrition_input_basis');
    if (inputBasisEl) {
      inputBasisEl.value = 'per_100';
      if (typeof window.updateInputBasisNote === 'function') window.updateInputBasisNote();
    }

    /* 산출 방법·1회 섭취참고량·판정 구분을 되살린다.
     *
     * **오차는 되살리지 않는다.** 저장된 값은 이미 오차를 물린 적용값이라,
     * 그 값에 다시 물리면 열 때마다 부푼다(309 -> 475 -> 731 을 낸 것과 같은
     * 자리다). 지난번에 얼마를 물렸는지는 기억해 두었다가 화면에 적어 주고,
     * 저장할 때 그대로 다시 남긴다. 새로 물리는 것은 사용자가 오차율을 고쳐
     * 넣었을 때뿐이다.
     */
    [['serving_reference', data.serving_reference],
     ['hieng_kind', data.hieng_kind],
     ['nutrition_source', data.nutrition_source],
     ['nutrition_source_note', data.nutrition_source_note]].forEach(function (pair) {
      const el = document.getElementById(pair[0]);
      if (el && pair[1] !== undefined && pair[1] !== null && pair[1] !== '') {
        el.value = pair[1];
      }
    });
    savedTolerance = String(data.nutrition_tolerance || '');
    const toleranceInput = document.getElementById('nutrition_tolerance');
    if (toleranceInput) toleranceInput.value = '0';
    if (typeof window.updateCalcSource === 'function') window.updateCalcSource();

    /* 표시기준 로드.
     *
     * **모르는 이름을 그대로 넣으면 고른 것이 없어진다.** <select> 는 없는
     * 값을 넣으면 value 가 '' 가 되고 아무 항목도 안 눌린 채로 보인다.
     * 저장돼 있는 이름은 'per_100g' / 'per_serving' 인 라벨이 있다 —
     * 그러면 기준 칸이 빈칸으로 열리고, 표는 조용히 총량당으로 그려진다.
     * 사용자에게는 "100g당으로 해 뒀는데 다르게 나온다" 로 보인다.
     *
     * 보내는 쪽은 이미 이름을 맞춰 두었다(sendNutritionDataToParent).
     * 읽는 쪽도 같은 함수를 쓴다 — 모르는 이름은 예전과 같이 총량당이고,
     * 이제는 그것이 화면에 **보인다.**
     */
    if (data.basic_display_type) {
      const basicDisplayElement = document.getElementById('basic_display_type');
      if (basicDisplayElement) {
        basicDisplayElement.value =
          normalizeBasicDisplayType(data.basic_display_type);
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
              console.warn('[Nutrition Calc] 영양성분 값 매핑 중 오류 발생:', popupFieldName, setError);
            }
            
            // 추가 영양성분에 값이 있으면 펼침
            if (NUTRITION_DATA[popupFieldName] && !NUTRITION_DATA[popupFieldName].required) {
              hasAdditionalValue = true;
            }
          } else if (input) {
            input.value = '';
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
              console.warn('[Nutrition Calc] 영양성분 값 설정 중 오류 발생:', popupFieldName, setError);
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
    console.warn('[Nutrition Calc] loadExistingData 처리 중 오류 발생:', error);
  } finally {
    // 3초 후 플래그 해제 (DOM 로드 및 처리 완료 대기)
    setTimeout(() => {
      isLoadingData = false;
    }, 3000);
  }
}

// ===== 이벤트 핸들러들 =====

// 페이지 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
  buildInputForm();
  
  // 단위량, 포장개수 필드에 쉼표 포맷팅 추가
  const servingSizeInput = document.getElementById('serving_size');
  const unitsPerPackageInput = document.getElementById('units_per_package');
  
  [servingSizeInput, unitsPerPackageInput].forEach(input => {
    if (input) {
      // 기존 이벤트 리스너 제거 (중복 방지)
      input.removeEventListener('input', applyCommaFormatting);
      // 공통 함수 사용
      input.addEventListener('input', applyCommaFormatting);
      // 환산 안내는 기준량이 바뀌면 같이 바뀐다
      input.addEventListener('input', updateInputBasisNote);
    }
  });
  
  // buildInputForm이 완료될 때까지 충분히 기다린 후 데이터 로드
  setTimeout(() => {
    
    /* ═══ 이 조건이 영원히 거짓이었다 ══════════════════════════════════
     *
     * `sodium`·`carbohydrate` 라는 id 는 없다. 입력칸 id 는 NUTRITION_DATA
     * 의 키(`natriums`·`carbohydrates`)다 — buildInputForm 이 그렇게 만든다.
     *
     * 그래서 `loadDataAfterFormReady()` 가 **한 번도 불리지 않았다**:
     *   · 부모 폼에서 저장하지 않은 입력이 계산기에 안 실렸다
     *   · URL 로 실어 보낸 값도 전부 버려졌다
     *   · 그리고 100ms 타이머가 창이 닫힐 때까지 끝없이 돌았다
     *
     * 이름을 손으로 적지 않는다 — 표를 만든 그 목록에서 가져온다.
     * 그리고 무한정 기다리지 않는다.
     * ═══════════════════════════════════════════════════════════════════ */
    const REQUIRED_IDS = Object.keys(window.NUTRITION_DATA || {}).slice(0, 3);
    let waited = 0;

    const waitForFormReady = () => {
      const allFieldsReady = REQUIRED_IDS.length > 0
        && REQUIRED_IDS.every(id => document.getElementById(id) !== null);

      if (allFieldsReady) {
        loadDataAfterFormReady();
        return;
      }
      waited += 100;
      if (waited >= 3000) {
        // 3초를 기다려도 표가 없다면 그 자체가 문제다. 조용히 영원히
        // 도는 것보다 한 번 시도하고 남기는 편이 낫다.
        console.warn('[영양성분 계산기] 입력 표가 준비되지 않았습니다', REQUIRED_IDS);
        loadDataAfterFormReady();
        return;
      }
      setTimeout(waitForFormReady, 100);
    };

    waitForFormReady();
  }, 200);

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
    
    /* ═══ 매핑이 **없는 키**를 향하고 있었다 ═══════════════════════════
     *
     * `natriums → sodium`, `carbohydrates → carbohydrate`, `fats → fat` …
     * 로 적어 두었는데 NUTRITION_DATA 에 그런 키는 없다(constants.js:129-).
     * 여기서 만든 값이 표에 들어갈 자리를 못 찾는다.
     *
     * URL 파라미터 이름과 데이터 키가 같으므로 매핑 자체가 필요 없다.
     * 목록을 손으로 적으면 성분이 늘 때마다 또 빠진다 — 표를 만든 그
     * 목록에서 그대로 가져온다.
     * ═══════════════════════════════════════════════════════════════════ */
    const fieldMapping = {};
    Object.keys(window.NUTRITION_DATA || {}).forEach(key => {
        fieldMapping[key] = key;
    });

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
  
  // 표시 기준 확인
  const displayType = window.normalizeBasicDisplayType(
    document.getElementById('basic_display_type')?.value);
  let multiplier;

  // 단위 확인 (g 또는 ml)
  const baseUnit = document.getElementById('serving_size_unit')?.value || 'g';

  /*
   * **표 머리와 표 본문은 서로 다른 것을 말한다.**
   *
   *   머리   "총 내용량 ⃝⃝g / ⃝⃝kcal"  — 언제나 포장 전체다
   *   본문   "총량당 / 단위량당 / 100g당" — 사용자가 고른 기준이다
   *
   * 예전에는 머리도 기준을 따라갔다. 그래서 65 g 짜리 제품에 100g당을 고르면
   * 라벨에 "총 내용량 100g" 이 인쇄됐고, 옆의 열량도 100 g 당 값이 총 열량인
   * 것처럼 찍혔다. 그 숫자를 그대로 내용량 칸에 옮겨 적은 사용자가 규정 검증
   * 에서 "열량이 맞지 않습니다" 를 계속 봤다 — 검증이 아니라 표가 틀렸다.
   *
   * 병행표시(generateParallelDisplayV3)는 처음부터 이렇게 그리고 있었다.
   */
  const totalAmount = baseAmount * servingsPerPackage;
  switch (displayType) {
    case 'unit':
      multiplier = baseAmount / 100;
      break;
    case '100g':
      multiplier = 1;
      break;
    case 'total':
    default:
      multiplier = totalAmount / 100;
      break;
  }

  // 머리의 열량은 **총 내용량 전체의 열량**이다. 내용량 칸에 병기하는 열량도
  // 같은 값이라, 둘이 어긋나면 규정 검증이 운다.
  const calories = window.processNutritionValue(
    'calories', (nutritionInputs['calories'] || 0) * (totalAmount / 100));

  // 표시기준 텍스트 생성
  let displayTypeText = '';
  switch (displayType) {
    case 'unit':  displayTypeText = `단위내용량(${baseAmount.toLocaleString()}${baseUnit})당`; break;
    case '100g':  displayTypeText = `100${baseUnit}당`; break;
    case 'total':
    default:      displayTypeText = '총내용량당'; break;
  }

  // 본문(영양성분) 행 생성 - 가이드라인 순서 준수
  const sortedNutrients = Object.entries(window.NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && (window.NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined))
    .sort((a, b) => a[1].order - b[1].order);

  const rowsHTML = sortedNutrients.map(([key, data]) => {
    const originalValue = (nutritionInputs[key] || 0) * multiplier;
    const processedValue = window.processNutritionValue(key, originalValue);
    const percent = window.calculateDailyValuePercent(key, processedValue, originalValue);

    const displayValue = processedValue.includes('미만')
      ? processedValue
      : `${Number(processedValue.replace(/,/g, '')).toLocaleString()} ${data.unit}`;

    const percentDisplay = percent === null
      ? ''
      : percent.includes('미만') ? percent : `<strong>${percent}</strong>%`;

    const rowClass = key === 'proteins' ? 'nutrition-row major-group-end' : 'nutrition-row';
    const indentClass = data.indent ? 'nutrition-indent' : '';

    return `
      <tr class="${rowClass}">
        <td class="nutrition-name-content ${indentClass}"><strong>${data.label}</strong> ${displayValue}</td>
        <td class="nutrition-daily">${percentDisplay}</td>
      </tr>`;
  }).join('');

  // V3 요구사항에 맞춘 기본형 HTML 구조 (템플릿 리터럴)
  return `<div class="nutrition-facts-container">
  <div class="nutrition-style-basic">
    <div class="nutrition-header">
      <div class="nutrition-title">영양정보</div>
      <div class="nutrition-subtitle">
        <div class="nutrition-total-amount">총 내용량 ${totalAmount.toLocaleString()}${baseUnit}</div>
        <div class="nutrition-calories">${calories}kcal</div>
      </div>
    </div>
    <table class="nutrition-table">
      <thead>
        <tr>
          <th>${displayTypeText}</th>
          <th>1일 영양성분<br>기준치에 대한 비율</th>
        </tr>
      </thead>
      <tbody>${rowsHTML}</tbody>
      <tfoot>
        <tr class="nutrition-footer">
          <td colspan="2">* <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>`;
}

// V3 병행표시 영양정보표 생성
function generateParallelDisplayV3(nutritionInputs, baseAmount, servingsPerPackage) {
  
  // 병행표시 유형 확인
  const parallelType = document.getElementById('parallel_display_type').value;
  const totalAmount = (baseAmount * servingsPerPackage);
  
  // 단위 확인 (g 또는 ml)
  const baseUnit = document.getElementById('serving_size_unit')?.value || 'g';
  
  let multiplier1, multiplier2, headerText1, headerText2, subHeaderText1, subHeaderText2;
  
  switch (parallelType) {
    case 'unit_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `총 내용량 ${totalAmount.toLocaleString()}${baseUnit}(${baseAmount.toLocaleString()}${baseUnit} X ${servingsPerPackage.toLocaleString()})`;
      headerText2 = `1조각(${baseAmount.toLocaleString()}${baseUnit})당 ${window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1)}kcal`;
      subHeaderText1 = '1조각당';
      subHeaderText2 = '총내용량당';
      break;
    case 'unit_100g':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = `총 내용량 ${totalAmount.toLocaleString()}${baseUnit}(${baseAmount.toLocaleString()}${baseUnit} X ${servingsPerPackage.toLocaleString()})`;
      headerText2 = `1조각(${baseAmount.toLocaleString()}${baseUnit})당 ${window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1)}kcal`;
      subHeaderText1 = '1조각당';
      subHeaderText2 = `100${baseUnit}당`;
      break;
    case 'serving_total':
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `총 내용량 ${totalAmount.toLocaleString()}${baseUnit}`;
      headerText2 = `1회량(${baseAmount.toLocaleString()}${baseUnit})당 ${window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1)}kcal`;
      subHeaderText1 = '1회량당';
      subHeaderText2 = '총내용량당';
      break;
    case 'serving_100ml':
      multiplier1 = baseAmount / 100;
      multiplier2 = 1;
      headerText1 = `총 내용량 ${totalAmount.toLocaleString()}${baseUnit}`;
      headerText2 = `1회량(${baseAmount.toLocaleString()}${baseUnit})당 ${window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1)}kcal`;
      subHeaderText1 = '1회량당';
      subHeaderText2 = '100ml당';
      break;
    default:
      multiplier1 = baseAmount / 100;
      multiplier2 = totalAmount / 100;
      headerText1 = `총 내용량 ${totalAmount.toLocaleString()}${baseUnit}(${baseAmount.toLocaleString()}${baseUnit} X ${servingsPerPackage.toLocaleString()})`;
      headerText2 = `1조각(${baseAmount.toLocaleString()}${baseUnit})당 ${window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1)}kcal`;
      subHeaderText1 = '1조각당';
      subHeaderText2 = '총내용량당';
      break;
  }
  
  const calories1 = window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier1);
  const calories2 = window.processNutritionValue('calories', (nutritionInputs['calories'] || 0) * multiplier2);

  // 본문(영양성분) 행 생성
  const sortedNutrients = Object.entries(window.NUTRITION_DATA)
    .filter(([key]) => key !== 'calories' && (window.NUTRITION_DATA[key].required || nutritionInputs[key] !== undefined))
    .sort((a, b) => a[1].order - b[1].order);

  const rowsHTML = sortedNutrients.map(([key, data]) => {
    const originalValue1 = (nutritionInputs[key] || 0) * multiplier1;
    const processedValue1 = window.processNutritionValue(key, originalValue1);
    const percent1 = window.calculateDailyValuePercent(key, processedValue1, originalValue1);

    const displayValue1 = processedValue1.includes('미만')
      ? processedValue1
      : `${Number(processedValue1.replace(/,/g, '')).toLocaleString()} ${data.unit}`;

    const originalValue2 = (nutritionInputs[key] || 0) * multiplier2;
    const processedValue2 = window.processNutritionValue(key, originalValue2);
    const percent2 = window.calculateDailyValuePercent(key, processedValue2, originalValue2);

    const displayValue2 = processedValue2.includes('미만')
      ? processedValue2
      : `${Number(processedValue2.replace(/,/g, '')).toLocaleString()} ${data.unit}`;

    const percentDisplay1 = percent1 === null
      ? ''
      : percent1.includes('미만') ? percent1 : `<strong>${percent1}</strong>%`;

    const percentDisplay2 = percent2 === null
      ? ''
      : percent2.includes('미만') ? percent2 : `<strong>${percent2}</strong>%`;

    const rowClass = key === 'proteins' ? 'nutrition-row major-group-end' : 'nutrition-row';
    const indentClass = data.indent ? 'nutrition-indent' : '';

    return `
      <tr class="${rowClass}">
        <td class="nutrition-name ${indentClass}"><strong>${data.label}</strong> ${displayValue1}</td>
        <td class="nutrition-daily">${percentDisplay1}</td>
        <td class="nutrition-content parallel-section">${displayValue2}</td>
        <td class="nutrition-daily parallel-section">${percentDisplay2}</td>
      </tr>`;
  }).join('');

  // V3 요구사항에 맞춘 병행표시 HTML 구조 (템플릿 리터럴)
  return `<div class="nutrition-facts-container">
  <div class="nutrition-style-parallel">
    <div class="nutrition-header">
      <div class="nutrition-header-left">
        <div class="nutrition-title">영양정보</div>
      </div>
      <div class="nutrition-header-right">
        <div class="nutrition-subtitle">${headerText1}</div>
        <div class="nutrition-calories"><strong>${headerText2}</strong></div>
      </div>
    </div>
    <table class="nutrition-table">
      <thead>
        <tr>
          <th class="left-section" colspan="2">
            <div class="header-flex">
              <span class="header-left">${subHeaderText1}</span>
              <span class="header-right">1일 영양성분 기준치에 대한 비율</span>
            </div>
          </th>
          <th class="right-section parallel-section" colspan="2">
            <div class="header-flex">
              <span class="header-empty"></span>
              <span class="header-right">${subHeaderText2}</span>
            </div>
          </th>
        </tr>
      </thead>
      <tbody>${rowsHTML}</tbody>
      <tfoot>
        <tr class="nutrition-footer">
          <td colspan="4">* <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2,000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>`;
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
/*
 * 기본형 표시기준 값 정규화.
 *
 * 이 값은 두 벌의 이름으로 돌아다녔다. 팝업의 <select> 와 표를 그리는 쪽은
 * 'total' / 'unit' / '100g' 을 쓰는데, 값을 보내는 쪽(sendNutritionDataToParent)
 * 과 표시사항 작성 화면은 'per_100g' / 'per_serving' 을 기본값으로 넣었다.
 * 그 이름들은 switch 에 없어서 **조용히 default(총량당)로 떨어졌다.**
 *
 * 그러니 지금 저장돼 있는 'per_100g' 라벨들은 이미 총량당으로 인쇄돼 왔다.
 * 여기서 100g당으로 "고치면" 이미 승인된 라벨의 표가 말없이 바뀐다. 그래서
 * **모르는 이름은 예전과 같이 총량당으로 본다.** 이름을 통일하는 일은 여기까지고,
 * 뜻을 바꾸지는 않는다.
 */
function normalizeBasicDisplayType(value) {
  var v = String(value || '').trim();
  if (v === 'unit' || v === '100g' || v === 'total') return v;
  return 'total';
}
window.normalizeBasicDisplayType = normalizeBasicDisplayType;


/* ─────────────────────────────────────────────────────────────────────────
   계산값 → 적용값 → 표시될 값

   사람들이 가진 것은 레시피로 뽑은 **계산값**이다. 규정은 실측값이 표시량에서
   얼마나 벌어져도 되는지를 한쪽 방향으로만 정해 두었으므로, 안전한 쪽이 성분
   마다 반대다. 그 방향대로 오차를 물린 것이 **적용값**이고, 표시 단위로
   반올림해 라벨에 인쇄되는 것이 **표시될 값**이다.

   세 값을 한 줄에 나란히 보여 준다. 어느 것이 어디서 왔는지 눈으로 따라갈 수
   있어야 사람이 그 표를 책임질 수 있다. 계산은 nutrition_calc.js 가 하고
   규정 숫자는 서버가 내려준다 — 여기서는 화면에 놓기만 한다.
   ───────────────────────────────────────────────────────────────────────── */

/** 지금 칸에 적힌 계산값들 (환산·오차 전) */
function rawNutritionValues() {
  var out = {};
  Object.keys(NUTRITION_DATA).forEach(function (key) {
    var input = document.getElementById(key);
    if (!input) return;
    var text = String(input.value || '').replace(/,/g, '').trim();
    if (text === '') return;
    var value = parseFloat(text);
    if (!isNaN(value) && value >= 0) out[key] = value;
  });
  return out;
}

/** 지금 고른 오차. 이론치일 때만 물린다 */
function toleranceSetting() {
  var source = document.getElementById('nutrition_source');
  if (!source || source.value !== 'theory') return { rate: 0, mode: 'up' };
  var rate = numberFrom('nutrition_tolerance', 0);
  var mode = document.getElementById('tolerance_mode');
  return { rate: rate, mode: mode ? mode.value : 'up' };
}

/**
 * 계산값에 오차를 물린 값. **늘 계산값에서 출발한다.**
 *
 * 적용값에 다시 물리면 두 번 곱해진다 — 입력 기준 환산이 예전에 그렇게 나서
 * 309 가 475 가 되고 731 이 됐다.
 */
function adjustedNutritionValues() {
  var raw = rawNutritionValues();
  var setting = toleranceSetting();
  var out = (window.nutritionCalc && setting.rate)
      ? window.nutritionCalc.applyTolerance(raw, setting.rate, setting.mode)
      : Object.assign({}, raw);
  /* 열량은 오차를 곱하지 않고 **보정한 탄단지로 다시 계산한다.** 따로 부풀리면
     표 안이 서로 맞지 않는다. 탄단지가 다 있을 때만 손댄다 — 열량만 아는
     사람의 값을 지우면 안 된다. */
  if (window.nutritionCalc && setting.rate) {
    var kcal = window.nutritionCalc.caloriesFromMacros(out);
    if (kcal !== null) out.calories = kcal;
  }
  return out;
}

/** 성분 줄마다 "→ 적용값 → 표시될 값" 을 적는다 */
function refreshDerived() {
  var setting = toleranceSetting();
  var adjusted = adjustedNutritionValues();
  var raw = rawNutritionValues();
  var flow = document.getElementById('cfAdjusted');
  if (flow) flow.classList.toggle('is-on', setting.rate > 0);

  document.querySelectorAll('[data-derived]').forEach(function (slot) {
    var key = slot.getAttribute('data-derived');
    var info = NUTRITION_DATA[key] || {};
    if (raw[key] === undefined && adjusted[key] === undefined) {
      slot.innerHTML = '';
      return;
    }
    var value = adjusted[key];
    var shown = window.processNutritionValue(key, value);
    var moved = setting.rate > 0 && Math.abs((value || 0) - (raw[key] || 0)) > 1e-9;
    var mid = moved
        ? '<b class="nd-adj">' + (Math.round(value * 100) / 100) + '</b>'
        : '';
    slot.innerHTML = (mid ? mid + ' <i class="nd-arrow">→</i> ' : '')
        + '<b class="nd-show">' + shown
        + (String(shown).indexOf('미만') < 0 ? ' ' + (info.unit || '') : '') + '</b>';
    slot.title = moved
        ? '계산값 ' + raw[key] + ' → 오차 반영 ' + value + ' → 표시 ' + shown
        : '표시될 값 ' + shown;
  });

  updateToleranceNote(setting);
  refreshHieng();
}
window.refreshDerived = refreshDerived;

/* 규정이 준 폭은 20% 다. 그보다 크게 잡으면 표시값이 사실에서 멀어진다 —
   허용오차는 표시를 부풀리라고 있는 것이 아니라 측정과 배치의 흔들림을
   감싸는 폭이다. */
function updateToleranceNote(setting) {
  var note = document.getElementById('toleranceNote');
  if (!note) return;
  var limit = (window.NUTRITION_RULES || {}).toleranceLimit || 20;
  if (setting.rate > limit) {
    note.textContent = '규정이 준 폭은 ' + limit + '% 입니다. 그보다 크게 잡으면 '
        + '표시값이 사실에서 멀어집니다.';
    note.className = 'calc-source-note is-warn';
    return;
  }
  if (!setting.rate && savedTolerance) {
    note.textContent = '아래 값에는 지난번에 물린 ' + savedTolerance
        + '% 가 이미 들어 있습니다. 다시 물리지 않습니다 — '
        + '계산값부터 새로 하려면 계산값을 넣고 오차율을 적으세요.';
    note.className = 'calc-source-note';
    return;
  }
  note.textContent = setting.mode === 'both'
      ? '이하 성분은 올리고, 이상 성분(탄수화물·단백질 등)은 낮춥니다.'
      : '당류·지방·포화지방·트랜스지방·콜레스테롤·나트륨만 올립니다. '
        + '열량은 보정한 탄단지로 다시 계산합니다.';
  note.className = 'calc-source-note';
}

/** 산출 방법을 고르면 그에 딸린 칸만 보인다 */
function updateCalcSource() {
  var source = document.getElementById('nutrition_source');
  var theory = source && source.value === 'theory';
  var toleranceRow = document.getElementById('toleranceRow');
  var noteRow = document.getElementById('sourceNoteRow');
  if (toleranceRow) toleranceRow.style.display = theory ? '' : 'none';
  if (noteRow) noteRow.style.display = (source && source.value) ? '' : 'none';
  refreshDerived();
}
window.updateCalcSource = updateCalcSource;

/**
 * 고열량·저영양 판정. **1회 제공량 기준**이라 1회 섭취참고량이 있어야 한다.
 *
 * 모르는 것과 아닌 것은 다르다 — 값이 비면 아니라고 말하지 않는다.
 */
function refreshHieng() {
  var panel = document.getElementById('hiengPanel');
  var box = document.getElementById('hiengResult');
  if (!panel || !box || !window.nutritionCalc) return;
  panel.style.display = '';

  var kindEl = document.getElementById('hieng_kind');
  var kind = kindEl ? kindEl.value : '';
  if (!kind) {
    box.className = 'hieng-result';
    box.textContent = '간식용·식사대용을 고르면 「어린이 식생활안전관리 특별법」 '
        + '기준으로 판정합니다.';
    return;
  }

  var reference = numberFrom('serving_reference', 0);
  if (!(reference > 0)) {
    box.className = 'hieng-result is-unknown';
    box.textContent = '1회 섭취참고량을 넣어 주세요. 이 판정은 1회 제공량 기준이라 '
        + '그 양을 모르면 할 수 없습니다.';
    return;
  }

  /* 칸의 값은 입력 기준(아래 값은 …당)을 따른다. 100 g 당으로 맞춘 뒤
     1회 섭취참고량으로 환산해야 기준과 같은 자리에서 견줄 수 있다. */
  var factor = inputBasisFactor();
  var per100 = {};
  var adjusted = adjustedNutritionValues();
  Object.keys(adjusted).forEach(function (key) {
    per100[key] = adjusted[key] * factor;
  });
  var perServing = window.nutritionCalc.perServing(per100, 100, reference);
  var result = window.nutritionCalc.hiengLntrt(perServing || {}, kind);

  var unit = (document.getElementById('serving_size_unit') || {}).value || 'g';
  var head = '1회 섭취참고량 ' + reference + unit + ' 기준 · ' + (result.kind || '');
  if (result.verdict === true) {
    box.className = 'hieng-result is-hit';
    box.innerHTML = '<b>고열량·저영양 식품에 해당합니다.</b><br>' + head
        + '<ul><li>' + result.hits.join('</li><li>') + '</li></ul>';
  } else if (result.verdict === false) {
    box.className = 'hieng-result is-ok';
    box.innerHTML = '<b>고열량·저영양 식품이 아닙니다.</b><br>' + head;
  } else {
    box.className = 'hieng-result is-unknown';
    box.textContent = result.why || '판정할 수 없습니다.';
  }
}
window.refreshHieng = refreshHieng;

/* 오차율·기준량을 고치면 그 자리에서 다시 그린다 */
document.addEventListener('DOMContentLoaded', function () {
  ['nutrition_tolerance', 'serving_reference', 'serving_size',
   'units_per_package'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('input', refreshDerived);
  });
  var basis = document.getElementById('nutrition_input_basis');
  if (basis) basis.addEventListener('change', refreshDerived);
  var unit = document.getElementById('serving_size_unit');
  if (unit) {
    unit.addEventListener('change', function () {
      var label = document.getElementById('servingReferenceUnit');
      if (label) label.textContent = unit.value || 'g';
    });
  }
});

window.calculateDailyValuePercent = calculateDailyValuePercent;
window.displayEmphasisValidation = displayEmphasisValidation;
// V3 함수들도 전역으로 노출
window.generateBasicDisplayV3 = generateBasicDisplayV3;
window.generateParallelDisplayV3 = generateParallelDisplayV3;

})(); // IIFE 종료