const nutrients = [
  { id: 'calorie', label: '열량', unit: ['kcal', 'cal'], step: 5 },
  { id: 'natrium', label: '나트륨', unit: ['mg', 'g'], step: 5, limit: 2000 },
  { id: 'carbohydrate', label: '탄수화물', unit: ['g', 'mg'], step: 0.5, limit: 324 },
  { id: 'sugar', label: '당류', unit: ['g', 'mg'], step: 0.5, limit: 100 },
  { id: 'afat', label: '지방', unit: ['g', 'mg'], step: 0.1, limit: 54 },
  { id: 'transfat', label: '트랜스지방', unit: ['g', 'mg'], step: 0.1 },
  { id: 'satufat', label: '포화지방', unit: ['g', 'mg'], step: 0.1, limit: 15 },
  { id: 'cholesterol', label: '콜레스테롤', unit: ['mg', 'g'], step: 5, limit: 300 },
  { id: 'protein', label: '단백질', unit: ['g', 'mg'], step: 0.5, limit: 55 }
];

function buildInputForm() {
  const container = document.getElementById('nutrient-inputs');
  nutrients.forEach(n => {
    const row = document.createElement('div');
    row.className = 'nutrient-row';
    row.innerHTML = `
      <label class="input-label">${n.label}</label>
      <input type="number" class="form-control" id="input_${n.id}" placeholder="${n.label} (100g 기준)">
      <select class="form-select input-unit" id="unit_${n.id}">
        ${n.unit.map(u => `<option value="${u}" ${u === n.unit[0] ? 'selected' : ''}>${u}</option>`).join('')}
      </select>
    `;
    container.appendChild(row);
  });
}

function round(value, step) {
  const remainder = value % step;
  const rounded = remainder <= step / 2 ? value - remainder : value - remainder + step;
  return step >= 1 ? parseInt(rounded) : parseFloat(rounded.toFixed(1));
}

function comma(x) {
  return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function getKcalValue() {
  const val = parseFloat(document.getElementById('input_calorie')?.value || "0");
  return isNaN(val) ? 0 : round((val * parseFloat(document.getElementById('base_amount').value)) / 100, 5);
}

function calculateNutrition() {
  const baseAmount = parseFloat(document.getElementById('base_amount').value);
  const baseUnit = document.getElementById('base_amount_unit').value;
  const servings = parseInt(document.getElementById('servings_per_package').value);
  if (!baseAmount || !servings) {
    alert("1회 제공량과 포장 갯수를 입력해주세요.");
    return;
  }
  const totalWeight = baseAmount * servings;
  const kcal = getKcalValue();

  const totalHeader = `<div class="summary-header">
    총 내용량 ${comma(totalWeight)}${baseUnit}<br>${comma(kcal)} kcal
  </div>`;

  const unitHeader = `<div class="summary-header">
    총 내용량 ${comma(totalWeight)}${baseUnit} (${comma(baseAmount)}${baseUnit} × ${comma(servings)}조각)<br>
    1조각(${baseAmount}${baseUnit})당 ${comma(kcal)} kcal
  </div>`;

  const g100Header = `<div class="summary-header">
    총 내용량 ${comma(totalWeight)}${baseUnit}<br>100${baseUnit}당 ${comma(kcal)} kcal
  </div>`;

  const footer = `<div class="summary-footer">※ 1일 영양성분 기준치에 대한 비율(%)은 2,000 kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.</div>`;

  const resultBoxes = {
    total: totalHeader + `<table class="table table-sm table-bordered text-center align-middle mt-2"><thead class="table-light"><tr><th>항목</th><th>총 내용량당</th></tr></thead><tbody>`,
    unit: unitHeader + `<table class="table table-sm table-bordered text-center align-middle mt-2"><thead class="table-light"><tr><th>항목</th><th>단위내용량당</th></tr></thead><tbody>`,
    '100g': g100Header + `<table class="table table-sm table-bordered text-center align-middle mt-2"><thead class="table-light"><tr><th>항목</th><th>100${baseUnit}당</th></tr></thead><tbody>`
  };

  let summaryText = [`총 내용량: ${comma(totalWeight)}${baseUnit}`, `열량: ${comma(kcal)}kcal`];

  nutrients.forEach(n => {
    if (n.id === 'calorie') return;
    const val = parseFloat(document.getElementById(`input_${n.id}`).value);
    const unit = document.getElementById(`unit_${n.id}`).value;
    if (isNaN(val)) return;
    const perUnit = round((val * baseAmount) / 100, n.step);
    const total = round(perUnit * servings, n.step);
    const percentUnit = n.limit ? ` (${Math.round(perUnit / n.limit * 100)}%)` : '';
    const percentTotal = n.limit ? ` (${Math.round(total / n.limit * 100)}%)` : '';
    const percent100g = n.limit ? ` (${Math.round(val / n.limit * 100)}%)` : '';

    resultBoxes.total += `<tr><td>${n.label}</td><td>${comma(total)}${unit}${percentTotal}</td></tr>`;
    resultBoxes.unit += `<tr><td>${n.label}</td><td>${comma(perUnit)}${unit}${percentUnit}</td></tr>`;
    resultBoxes['100g'] += `<tr><td>${n.label}</td><td>${comma(val)}${unit}${percent100g}</td></tr>`;

    summaryText.push(`${n.label}: ${comma(val)}${unit}`);
  });

  document.getElementById('resultBoxTotal').innerHTML = resultBoxes.total + '</tbody></table>' + footer;
  document.getElementById('resultBoxUnit').innerHTML = resultBoxes.unit + '</tbody></table>' + footer;
  document.getElementById('resultBox100g').innerHTML = resultBoxes['100g'] + '</tbody></table>' + footer;

  window.nutritionSummaryValue = summaryText.join(', ');
  updateNutritionSummaryText();
}

function updateNutritionSummaryText() {
  const selected = document.getElementById("tabSelector").value;
  const labelMap = { total: '총 내용량 기준', unit: '단위내용량 기준', '100g': '100g(ml) 기준' };
  window.nutritionText = `(${labelMap[selected]}) ` + (window.nutritionSummaryValue || '');
}

// sendNutritionDataToParent 함수 수정
function sendNutritionDataToParent() {
  // 계산 결과가 있는지 확인
  if (!window.nutritionText || !window.nutritionSummaryValue) {
    alert("영양성분 계산을 먼저 실행해주세요.");
    return;
  }

  if (window.opener) {
    try {
      // 1. 부모 창의 텍스트 영역 업데이트
      const textarea = window.opener.document.getElementById("nutritions");
      if (textarea) {
        textarea.value = window.nutritionText;
      }
      
      // 2. 현재 선택된 영양성분 표시 단위
      const displayUnit = document.getElementById('tabSelector').value;
      
      // 3. 영양성분 데이터 수집
      const baseAmount = document.getElementById('base_amount').value;
      const baseUnit = document.getElementById('base_amount_unit').value;
      const servings = document.getElementById('servings_per_package').value;
      
      // 4. 각 영양소 값과 단위 데이터 수집
      const nutritionValues = {};
      nutrients.forEach(n => {
        const val = document.getElementById(`input_${n.id}`)?.value;
        const unit = document.getElementById(`unit_${n.id}`)?.value;
        if (val && !isNaN(parseFloat(val))) {
          nutritionValues[n.id] = {
            value: val,
            unit: unit
          };
        }
      });
      
      // 5. 부모 창의 hidden 필드에 영양성분 값 설정
      const fieldMapping = {
        'base_amount': 'serving_size',
        'base_amount_unit': 'serving_size_unit',
        'servings_per_package': 'units_per_package',
        'tabSelector': 'nutrition_display_unit',
        'calorie': 'calories',
        'natrium': 'natriums',
        'carbohydrate': 'carbohydrates',
        'sugar': 'sugars',
        'afat': 'fats',
        'transfat': 'trans_fats',
        'satufat': 'saturated_fats',
        'cholesterol': 'cholesterols',
        'protein': 'proteins'
      };
      
      // 기본 필드 설정
      window.opener.document.querySelector('input[name="serving_size"]').value = baseAmount;
      window.opener.document.querySelector('input[name="serving_size_unit"]').value = baseUnit;
      window.opener.document.querySelector('input[name="units_per_package"]').value = servings;
      window.opener.document.querySelector('input[name="nutrition_display_unit"]').value = displayUnit;
      
      // 각 영양소 필드 설정
      Object.keys(nutritionValues).forEach(key => {
        const formFieldName = fieldMapping[key];
        if (formFieldName) {
          const valueField = window.opener.document.querySelector(`input[name="${formFieldName}"]`);
          const unitField = window.opener.document.querySelector(`input[name="${formFieldName}_unit"]`);
          
          if (valueField) {
            valueField.value = nutritionValues[key].value;
          }
          
          if (unitField) {
            unitField.value = nutritionValues[key].unit;
          }
        }
      });
      
      // 7. AJAX 요청을 통해 DB에 저장
      const labelId = window.opener.document.getElementById('label_id')?.value;
      if (labelId) {
        // 서버로 전송할 데이터 준비
        const nutritionData = {
          label_id: labelId,
          serving_size: baseAmount,
          serving_size_unit: baseUnit,
          units_per_package: servings,
          nutrition_display_unit: displayUnit,
          nutritions: window.nutritionText,  // 이 값이 nutrition_text 필드에 저장됨
        };
        
        // 각 영양소 데이터 추가
        Object.keys(nutritionValues).forEach(key => {
          const formFieldName = fieldMapping[key];
          if (formFieldName) {
            nutritionData[formFieldName] = nutritionValues[key].value;
            nutritionData[`${formFieldName}_unit`] = nutritionValues[key].unit;
          }
        });
        
        // AJAX 요청으로 DB에 저장
        fetch('/label/save-nutrition/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify(nutritionData)
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            alert("영양성분 데이터가 저장되었습니다.");
            window.close();
          } else {
            alert("영양성분 데이터 저장 중 오류가 발생했습니다: " + data.error);
          }
        })
        .catch(error => {
          console.error("영양성분 데이터 저장 중 오류:", error);
          alert("영양성분 데이터 저장 중 오류가 발생했습니다.");
        });
      } else {
        alert("영양성분 데이터가 적용되었습니다. 라벨을 저장해주세요.");
        window.close();
      }
    } catch (e) {
      console.error("부모 창에 영양성분 데이터 전달 중 오류:", e);
      alert("영양성분 데이터 전달 중 오류가 발생했습니다.");
      return;
    }
  } else {
    alert("영양성분 데이터가 적용되었습니다.");
    window.close();
  }
}

// CSRF 토큰을 가져오는 함수 추가
function getCsrfToken() {
  // 1. cookie에서 csrftoken 값 가져오기
  const cookies = document.cookie.split(';');
  for (let i = 0; i < cookies.length; i++) {
    const cookie = cookies[i].trim();
    if (cookie.startsWith('csrftoken=')) {
      return cookie.substring('csrftoken='.length, cookie.length);
    }
  }
  
  // 2. 부모 창의 form에서 csrftoken input 찾기
  if (window.opener) {
    const csrfInput = window.opener.document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfInput) {
      return csrfInput.value;
    }
  }
  
  return '';
}

function switchResultTab(type) {
  document.querySelectorAll('.nutrition-tab-content').forEach(tab => tab.classList.remove('active'));
  document.getElementById('result-' + type).classList.add('active');
  document.querySelectorAll('#resultTab .nav-link').forEach(btn => btn.classList.remove('active'));
  document.querySelector(`#resultTab .nav-link[data-target="#result-${type}"]`).classList.add('active');
  document.getElementById('tabSelector').value = type;
  updateNutritionSummaryText();
}

function resetForm() {
  document.querySelectorAll('input[type="number"]').forEach(el => el.value = '');
  document.querySelectorAll('select').forEach(el => el.selectedIndex = 0);
  document.getElementById('resultBoxTotal').innerHTML = '';
  document.getElementById('resultBoxUnit').innerHTML = '';
  document.getElementById('resultBox100g').innerHTML = '';
  window.nutritionText = '';
  window.nutritionSummaryValue = '';
}

// 페이지 초기화 함수
function initNutritionCalculator() {
  // 영양성분 입력 폼 구성
  buildInputForm();
  
  // 기본 이벤트 리스너 설정
  document.getElementById('tabSelector').addEventListener('change', updateNutritionSummaryText);
  
  // 탭 전환 초기화
  switchResultTab('total');
  
  // 초기화 완료 이벤트 발생
  const event = new CustomEvent('nutrition-calculator-ready');
  document.dispatchEvent(event);
}

// 페이지 로드 시 기존 데이터 로드 함수 수정
function loadExistingData(data) {
  // 데이터가 없으면 종료
  if (!data || Object.keys(data).length === 0) return;
  
  console.log("로드할 영양성분 데이터:", data);
  
  // 기본 필드 설정
  if (data.serving_size) {
    const baseAmountElement = document.getElementById('base_amount');
    if (baseAmountElement) baseAmountElement.value = data.serving_size;
  }
  
  if (data.serving_size_unit) {
    const unitElement = document.getElementById('base_amount_unit');
    if (unitElement) unitElement.value = data.serving_size_unit;
  }
  
  if (data.units_per_package) {
    const servingsElement = document.getElementById('servings_per_package');
    if (servingsElement) servingsElement.value = data.units_per_package;
  }
  
  if (data.display_unit && ['total', 'unit', '100g'].includes(data.display_unit)) {
    const tabElement = document.getElementById('tabSelector');
    if (tabElement) {
      tabElement.value = data.display_unit;
      switchResultTab(data.display_unit);
    }
  }

  // 영양소 값 설정
  if (data.nutrients) {
    // 각 영양소 필드 설정
    nutrients.forEach(nutrient => {
      const nutrientData = data.nutrients[nutrient.id];
      if (nutrientData) {
        const inputElement = document.getElementById(`input_${nutrient.id}`);
        const unitElement = document.getElementById(`unit_${nutrient.id}`);
        
        if (nutrientData.value && inputElement) {
          inputElement.value = nutrientData.value;
        }
        
        if (nutrientData.unit && unitElement && nutrient.unit.includes(nutrientData.unit)) {
          unitElement.value = nutrientData.unit;
        }
      }
    });

    // 데이터가 로드되었고 필수 필드가 채워져 있으면 계산 실행
    const baseAmountElement = document.getElementById('base_amount');
    const servingsElement = document.getElementById('servings_per_package');
    
    if (baseAmountElement && baseAmountElement.value && 
        servingsElement && servingsElement.value) {
      calculateNutrition();
    }
  }
}

// DOM이 로드되면 초기화 함수 실행
document.addEventListener('DOMContentLoaded', initNutritionCalculator);