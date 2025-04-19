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
  const servings = parseInt(document.getElementById('servings_per_package').value);
  if (!baseAmount || baseAmount <= 0 || !servings || servings <= 0) {
    alert("1회 제공량과 포장 갯수는 양수로 입력해주세요.");
    return;
  }
  document.getElementById('resultBoxTotal').innerHTML = '';
  document.getElementById('resultBoxUnit').innerHTML = '';
  document.getElementById('resultBox100g').innerHTML = '';

  const baseUnit = document.getElementById('base_amount_unit').value;
  const totalWeight = baseAmount * servings;
  const kcal = getKcalValue();

  const totalHeader = `<div class="summary-header">총 내용량 ${comma(totalWeight)}${baseUnit}<br>${comma(kcal)} kcal</div>`;
  const unitHeader = `<div class="summary-header">총 내용량 ${comma(totalWeight)}${baseUnit} (${comma(baseAmount)}${baseUnit} × ${comma(servings)}조각)<br>1조각(${baseAmount}${baseUnit})당 ${comma(kcal)} kcal</div>`;
  const g100Header = `<div class="summary-header">총 내용량 ${comma(totalWeight)}${baseUnit}<br>100${baseUnit}당 ${comma(kcal)} kcal</div>`;
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

  const currentTab = document.getElementById('tabSelector').value;
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

      // nutrition_items 데이터를 배열 형식으로 준비
      const nutritionItems = [];
      nutrients.forEach(n => {
        const val = document.getElementById(`input_${n.id}`)?.value;
        const unit = document.getElementById(`unit_${n.id}`)?.value;
        if (val && !isNaN(parseFloat(val))) {
          const formattedValue = `${comma(parseFloat(val))}${unit}`;
          let dv = '';
          if (n.limit) {
            const percent = Math.round((parseFloat(val) / n.limit) * 100);
            dv = `${percent}%`;
          }
          nutritionItems.push({
            label: n.label,
            value: formattedValue,
            dv: dv
          });
        }
      });

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

      // 부모 창의 폼 필드에 데이터 설정
      window.opener.document.querySelector('input[name="serving_size"]').value = baseAmount;
      window.opener.document.querySelector('input[name="serving_size_unit"]').value = baseUnit;
      window.opener.document.querySelector('input[name="units_per_package"]').value = servings;
      window.opener.document.querySelector('input[name="nutrition_display_unit"]').value = displayUnit;

      // nutrition_items 데이터를 부모 창에 전달
      const nutritionItemsInput = window.opener.document.querySelector('input[name="nutrition_items"]');
      if (nutritionItemsInput) {
        nutritionItemsInput.value = JSON.stringify(nutritionItems);
      }

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
          nutrition_items: nutritionItems // nutrition_items 추가
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
  document.getElementById('tabSelector').addEventListener('change', (e) => {
    switchResultTab(e.target.value);
  });
  document.querySelectorAll('#resultTab .nav-link').forEach(btn => {
    btn.addEventListener('shown.bs.tab', () => {
      const type = btn.getAttribute('data-tab');
      document.getElementById('tabSelector').value = type;
      updateNutritionSummaryText();
    });
  });
  switchResultTab('total');
  const event = new CustomEvent('nutrition-calculator-ready');
  document.dispatchEvent(event);
}

document.addEventListener('DOMContentLoaded', initNutritionCalculator);