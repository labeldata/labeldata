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

// 한국 식품표시기준 반올림 규정 적용 함수 (열량은 1회 제공량 기준으로만 구간 반올림)
function roundKoreanNutrition(value, type, context) {
  if (type === 'kcal') {
    if (context && context.isKcalPerServing) {
      if (value < 5) return 0;
      if (value <= 50) return Math.round(value / 5) * 5; // 2.5 → 5
      return Math.round(value / 10) * 10; // 55 → 60
    } else {
      return Math.floor(value);
    }
  }
  if (type === 'mg') {
    if (value < 5) return 0;
    if (value <= 140) return Math.round(value / 5) * 5;
    return Math.round(value / 10) * 10;
  }
  if (type === 'g') {
    if (value < 0.5) return 0;
    if (value <= 5) return Math.round(value * 10) / 10; // 2.55 → 2.6
    return Math.round(value); // 5.5 → 6
  }
  return value;
}

function getKcalValue(type, baseAmount, servings, val) {
  // type: 'total', 'unit', '100g'
  // val: 100g(ml)당 열량
  if (isNaN(val) || isNaN(baseAmount)) return 0;
  let raw = 0;
  let context = {};
  if (type === 'total') {
    raw = (val * baseAmount * servings) / 100;
    context.isKcalPerServing = true;
    return roundKoreanNutrition(raw, 'kcal', context);
  } else if (type === 'unit') {
    raw = (val * baseAmount) / 100;
    context.isKcalPerServing = true;
    return roundKoreanNutrition(raw, 'kcal', context);
  } else {
    // 100g(ml)당
    raw = val;
    context.isKcalPerServing = false;
    return roundKoreanNutrition(raw, 'kcal', context);
  }
}

function calculateNutrition(tabType) {
  const baseAmount = parseFloat(document.getElementById('base_amount').value);
  const servings = parseInt(document.getElementById('servings_per_package').value);
  if (!baseAmount || baseAmount <= 0 || !servings || servings <= 0) {
    document.getElementById('resultBoxTotal').innerHTML = '';
    document.getElementById('resultBoxUnit').innerHTML = '';
    document.getElementById('resultBox100g').innerHTML = '';
    return;
  }
  document.getElementById('resultBoxTotal').innerHTML = '';
  document.getElementById('resultBoxUnit').innerHTML = '';
  document.getElementById('resultBox100g').innerHTML = '';

  const baseUnit = document.getElementById('base_amount_unit').value;
  const totalWeight = baseAmount * servings;
  const kcalPer100g = parseFloat(document.getElementById('input_calorie')?.value || "0");

  // 탭별 총내용량 텍스트
  const tabMap = {
    total: `총 내용량 ${comma(totalWeight)}${baseUnit}`,
    unit: `단위내용량 ${comma(baseAmount)}${baseUnit}`,
    '100g': `100${baseUnit}당`
  };

  // 현재 탭
  const currentTab = tabType || document.getElementById('tabSelector').value;

  // 열량 계산 (반올림 규정에 맞게)
  let kcal = 0;
  if (currentTab === 'total') {
    kcal = getKcalValue('total', baseAmount, servings, kcalPer100g);
  } else if (currentTab === 'unit') {
    kcal = getKcalValue('unit', baseAmount, servings, kcalPer100g);
  } else {
    kcal = getKcalValue('100g', baseAmount, servings, kcalPer100g);
  }

  // 상단(검정) 미리보기 박스: 한 줄, 총 내용량(작게) + 열량(크게) 오른쪽 정렬, "영양정보" 크게
  const previewBox = `
    <div class="nutrition-preview-box" style="margin-bottom:0;display:flex;align-items:center;justify-content:space-between;">
      <div class="nutrition-preview-title" style="margin-bottom:0;font-size:2rem;">영양정보</div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;">
        <span class="nutrition-preview-total-small" style="font-size:0.95rem;font-weight:500;color:#fff;">${tabMap[currentTab]}</span>
        <span class="nutrition-preview-kcal" style="font-size:1.15rem;font-weight:700;color:#fff;line-height:1;">${comma(kcal)}kcal</span>
      </div>
    </div>
  `;

  // 하단(흰색) 표 스타일
  const tableStyle = 'background:#fff;color:#222;border-radius:0 0 6px 6px;width:320px;margin:0 auto 16px auto;';
  const thSmall = 'class="nutrition-preview-small" style="font-size:0.95rem;font-weight:500;background:#fff;padding:8px 0 6px 0;color:#222;border-bottom:2.5px solid #222;text-align:left;"';
  const thRightSmall = 'class="nutrition-preview-small" style="font-size:0.95rem;font-weight:500;background:#fff;padding:8px 0 6px 0;color:#222;border-bottom:2.5px solid #222;text-align:right;"';
  const tdLabelClass = 'style="font-weight:700;text-align:left;padding:6px 0 6px 0;"';
  const tdLabelIndentClass = 'style="font-weight:700;text-align:left;padding:6px 0 6px 24px;"';
  const tdValueClass = 'style="font-weight:400;text-align:left;padding:6px 0 6px 0;"';
  const tdPercentClass = 'style="font-weight:700;text-align:right;padding:6px 0 6px 0;"';

  // 표 본문 (탭별)
  function makeRows(type) {
    let rows = '';
    nutrients.forEach(n => {
      if (n.id === 'calorie') return;
      const val = parseFloat(document.getElementById(`input_${n.id}`).value);
      const unit = document.getElementById(`unit_${n.id}`).value;
      if (isNaN(val)) return;
      let value = 0, percent = '';
      let roundType = 'g';
      if (n.id === 'natrium' || n.id === 'cholesterol') roundType = 'mg';
      else if (n.id === 'carbohydrate' || n.id === 'sugar' || n.id === 'afat' || n.id === 'transfat' || n.id === 'satufat' || n.id === 'protein') roundType = 'g';

      if (type === 'total') {
        let raw = (val * baseAmount * servings) / 100;
        value = roundKoreanNutrition(raw, roundType);
        percent = n.limit ? Math.round(value / n.limit * 100) : '';
      } else if (type === 'unit') {
        let raw = (val * baseAmount) / 100;
        value = roundKoreanNutrition(raw, roundType);
        percent = n.limit ? Math.round(value / n.limit * 100) : '';
      } else {
        let raw = val;
        value = roundKoreanNutrition(raw, roundType);
        percent = n.limit ? Math.round(value / n.limit * 100) : '';
      }
      const indent = (n.id === 'sugar' || n.id === 'transfat' || n.id === 'satufat');
      // 항목명 굵게, 실측값은 한 칸 띄우고 일반글씨
      rows += `<tr>
        <td ${indent ? tdLabelIndentClass : tdLabelClass}><strong>${n.label}</strong> <span ${tdValueClass}>${comma(value)}${unit}</span></td>
        <td ${tdPercentClass}>${percent !== '' ? `<strong>${percent}</strong>%` : ''}</td>
      </tr>`;
    });
    // 안내문구(표 내부 마지막 tr, 작은 글씨)
    rows += `
      <tr>
        <td colspan="2" class="nutrition-preview-footer-inside">
          <strong>1일 영양성분 기준치에 대한 비율(%)</strong>은 2000kcal 기준이므로 개인의 필요 열량에 따라 다를 수 있습니다.
        </td>
      </tr>
    `;
    return rows;
  }

  // 표 헤더 (비율 문구는 헤더에만, 작은 글씨)
  const tableHeader = `
    <thead>
      <tr>
        <th ${thSmall}>${tabMap[currentTab]}</th>
        <th ${thRightSmall}>1일 영양성분 기준치에 대한 비율</th>
      </tr>
    </thead>
  `;

  // 최종 렌더링 (탭별)
  document.getElementById('resultBoxTotal').innerHTML =
    previewBox +
    `<table class="nutrition-preview-table" style="${tableStyle}">
      ${tableHeader}
      <tbody>${makeRows('total')}</tbody>
    </table>`;

  document.getElementById('resultBoxUnit').innerHTML =
    previewBox +
    `<table class="nutrition-preview-table" style="${tableStyle}">
      ${tableHeader}
      <tbody>${makeRows('unit')}</tbody>
    </table>`;

  document.getElementById('resultBox100g').innerHTML =
    previewBox +
    `<table class="nutrition-preview-table" style="${tableStyle}">
      ${tableHeader}
      <tbody>${makeRows('100g')}</tbody>
    </table>`;

  let summaryText = [`총 내용량: ${comma(totalWeight)}${baseUnit}`, `열량: ${comma(kcal)}kcal`];
  nutrients.forEach(n => {
    if (n.id === 'calorie') return;
    const val = parseFloat(document.getElementById(`input_${n.id}`).value);
    const unit = document.getElementById(`unit_${n.id}`).value;
    if (isNaN(val)) return;
    summaryText.push(`${n.label}: ${comma(val)}${unit}`);
  });
  window.nutritionSummaryValue = summaryText.join(', ');
  updateNutritionSummaryText();

  // 탭 전환
  switchResultTab(currentTab);
}

function updateNutritionSummaryText() {
  const selected = document.getElementById('tabSelector').value;
  const labelMap = { total: '총 내용량 기준', unit: '단위내용량 기준', '100g': '100g(ml) 기준' };
  window.nutritionText = `(${labelMap[selected]}) ` + (window.nutritionSummaryValue || '');
}

function switchResultTab(type) {
  const tabBtn = document.querySelector(`#resultTab .nav-link[data-tab="${type}"]`);
  if (tabBtn) {
    const tabInstance = bootstrap.Tab.getOrCreateInstance(tabBtn);
    tabInstance.show();
  }
  document.getElementById('tabSelector').value = type;
  updateNutritionSummaryText();
}

function sendNutritionDataToParent() {
  if (!window.nutritionText || !window.nutritionSummaryValue) {
    alert("영양성분 계산을 먼저 실행해주세요.");
    return;
  }
  if (window.opener) {
    try {
      const textarea = window.opener.document.getElementById("nutrition_text") ||
                 window.opener.document.querySelector('textarea[name="nutrition_text"]');
      if (textarea) {
        textarea.value = window.nutritionText;
      }
      const displayUnit = document.getElementById('tabSelector').value;
      const baseAmount = document.getElementById('base_amount').value;
      const baseUnit = document.getElementById('base_amount_unit').value;
      const servings = document.getElementById('servings_per_package').value;
      const nutritionValues = {};
      nutrients.forEach(n => {
        const val = document.getElementById(`input_${n.id}`)?.value;
        const unit = document.getElementById(`unit_${n.id}`)?.value;
        if (val && !isNaN(parseFloat(val))) {
          nutritionValues[n.id] = { value: val, unit: unit };
        }
      });
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
      window.opener.document.querySelector('input[name="serving_size"]').value = baseAmount;
      window.opener.document.querySelector('input[name="serving_size_unit"]').value = baseUnit;
      window.opener.document.querySelector('input[name="units_per_package"]').value = servings;
      window.opener.document.querySelector('input[name="nutrition_display_unit"]').value = displayUnit;
      Object.keys(nutritionValues).forEach(key => {
        const formFieldName = fieldMapping[key];
        if (formFieldName) {
          const valueField = window.opener.document.querySelector(`input[name="${formFieldName}"]`);
          const unitField = window.opener.document.querySelector(`input[name="${formFieldName}_unit"]`);
          if (valueField) valueField.value = nutritionValues[key].value;
          if (unitField) unitField.value = nutritionValues[key].unit;
        }
      });
      const labelId = window.opener.document.getElementById('label_id')?.value;
      if (labelId) {
        const nutritionData = {
          label_id: labelId,
          serving_size: baseAmount,
          serving_size_unit: baseUnit,
          units_per_package: servings,
          nutrition_display_unit: displayUnit,
          nutritions: window.nutritionText,
        };
        Object.keys(nutritionValues).forEach(key => {
          const formFieldName = fieldMapping[key];
          if (formFieldName) {
            nutritionData[formFieldName] = nutritionValues[key].value;
            nutritionData[`${formFieldName}_unit`] = nutritionValues[key].unit;
          }
        });
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

function getCsrfToken() {
  const cookies = document.cookie.split(';');
  for (let i = 0; i < cookies.length; i++) {
    const cookie = cookies[i].trim();
    if (cookie.startsWith('csrftoken=')) {
      return cookie.substring('csrftoken='.length, cookie.length);
    }
  }
  if (window.opener) {
    const csrfInput = window.opener.document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfInput) return csrfInput.value;
  }
  return '';
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

function loadExistingData(data) {
  if (!data || Object.keys(data).length === 0) return;
  console.log("로드할 영양성분 데이터:", data);
  if (data.serving_size) {
    document.getElementById('base_amount').value = data.serving_size;
  }
  if (data.serving_size_unit) {
    document.getElementById('base_amount_unit').value = data.serving_size_unit;
  }
  if (data.units_per_package) {
    document.getElementById('servings_per_package').value = data.units_per_package;
  }
  if (data.display_unit && ['total', 'unit', '100g'].includes(data.display_unit)) {
    switchResultTab(data.display_unit);
  }
  if (data.nutrients) {
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
    if (document.getElementById('base_amount').value && document.getElementById('servings_per_package').value) {
      calculateNutrition();
      switchResultTab(data.display_unit || 'total');
    }
  }
}

function initNutritionCalculator() {
  buildInputForm();

  // 셀렉트박스, 입력값, 단위 변경 시 실시간 계산
  document.getElementById('tabSelector').addEventListener('change', (e) => {
    calculateNutrition(e.target.value);
  });
  document.querySelectorAll('#resultTab .nav-link').forEach(btn => {
    btn.addEventListener('shown.bs.tab', () => {
      const type = btn.getAttribute('data-tab');
      document.getElementById('tabSelector').value = type;
      calculateNutrition(type);
      updateNutritionSummaryText();
    });
  });

  // 모든 input/select에 입력/변경 이벤트 연결
  document.querySelectorAll(
    '#nutrient-inputs input, #nutrient-inputs select, #base_amount, #base_amount_unit, #servings_per_package'
  ).forEach(el => {
    el.addEventListener('input', () => {
      calculateNutrition(document.getElementById('tabSelector').value);
    });
    el.addEventListener('change', () => {
      calculateNutrition(document.getElementById('tabSelector').value);
    });
  });

  // 탭 변경 시에도 실시간 반영
  document.getElementById('tabSelector').dispatchEvent(new Event('change'));

  const event = new CustomEvent('nutrition-calculator-ready');
  document.dispatchEvent(event);
}

document.addEventListener('DOMContentLoaded', initNutritionCalculator);