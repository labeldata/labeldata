window.phrasesData = JSON.parse(document.getElementById('phrases-data').textContent);

// ------------------ 라벨 관리 기능 ------------------
function copyLabel(labelId) {
  if (!labelId) {
    alert("복사할 라벨이 없습니다.");
    return;
  }
  if (confirm("현재 라벨을 복사하시겠습니까?")) {
    window.location.href = `/label/duplicate/${labelId}/`;
  }
}

function deleteLabel(labelId) {
  if (!labelId) {
    alert("삭제할 라벨이 없습니다.");
    return;
  }
  if (confirm("정말로 이 라벨을 삭제하시겠습니까? 복구할 수 없습니다.")) {
    window.location.href = `/label/delete/${labelId}/`;
  }
}

// ------------------ 초기화 & 그룹 체크박스 로직 ------------------
function initCheckBoxGroups() {
  // 장기보존식품 그룹: 1개만 선택
  $('.grp-long-shelf').on('change', function(e) {
    if (this.checked) {
      $('.grp-long-shelf').not(this).prop('checked', false).data('alreadyChecked', false);
      $(this).data('alreadyChecked', true);
      
      // 선택된 값을 hidden 필드에 설정
      $('#hidden_preservation_type').val(this.value);
    } else {
      $(this).data('alreadyChecked', false);
      // 체크 해제 시 hidden 필드도 비움
      $('#hidden_preservation_type').val('');
    }
    updateSummary(); // 요약 갱신
  });

  // 제조방법 그룹: 1개만 선택 (조건 제외)
  $('.grp-sterilization').on('change', function(e) {
    if (this.id === "chk_sterilization_other") return;

    if (this.checked) {
      $('.grp-sterilization').not('#chk_sterilization_other').not(this)
        .prop('checked', false).data('alreadyChecked', false);
      $(this).data('alreadyChecked', true);
      
      // 선택된 값을 hidden 필드에 설정
      $('#hidden_processing_method').val(this.value);
    } else {
      $(this).data('alreadyChecked', false);
      // 체크 해제 시 hidden 필드도 비움
      $('#hidden_processing_method').val('');
    }

    // 조건 체크박스 활성화 여부
    if ($("#chk_sanitized").is(":checked") || $("#chk_aseptic").is(":checked")) {
      $("#chk_sterilization_other").prop("disabled", false);
    } else {
      $("#chk_sterilization_other").prop("disabled", true).prop("checked", false);
      // 조건이 비활성화되면 조건 값도 비움
      $('input[name="processing_condition"]').val('');
      $('#hidden_processing_condition').val('');
    }
    updateSummary(); // 요약 갱신
  });

  // 조건 체크박스 및 텍스트 입력 필드 이벤트 핸들러 추가
  $("#chk_sterilization_other").on('change', function() {
    // 체크 해제 시 값을 지우지 않고 요약 갱신만 함
    updateSummary();
  });

  // 조건 텍스트 입력 시 hidden 필드 업데이트
  $('input[name="processing_condition"]').on('input', function() {
    $('#hidden_processing_condition').val(this.value);
    // 조건 체크박스가 체크된 경우에만 요약 갱신
    if ($("#chk_sterilization_other").is(":checked")) {
      updateSummary();
    }
  });
}

function initSingleSelectGroup(selector, exceptionId = null) {
    $(selector).on('click', function (e) {
        if (this.id === exceptionId) return;
        const alreadyChecked = $(this).data('alreadyChecked') || false;
        if (alreadyChecked) {
            $(this).prop('checked', false).data('alreadyChecked', false);
        } else {
            $(selector).not(this).prop('checked', false).data('alreadyChecked', false);
            $(this).prop('checked', true).data('alreadyChecked', true);
        }
        e.stopPropagation();
    });
}

function getCheckedLabel(selector) {
  const checked = $(selector).filter(':checked');
  if (checked.length) {
      const id = checked.attr('id');
      const label = $(`label[for="${id}"]`).text();
      return label || null;
  }
  return null;
}

// ------------------ 식품유형 요약 업데이트 ------------------
function updateSummary() {
  const summaries = [];

  // 소분류
  const foodSmall = $('#food_type option:selected').text();
  if (foodSmall && foodSmall !== "소분류") summaries.push(foodSmall);

  // 장기보존식품 변환 처리
  const longShelfId = $('.grp-long-shelf:checked').attr('id');
  let isFrozenHeated = false;
  if (longShelfId === "chk_frozen_heated") {
      summaries.push("가열하여 섭취하는 냉동식품");
      isFrozenHeated = true;
  } else if (longShelfId === "chk_frozen_nonheated") {
      summaries.push("가열하지 않고 섭취하는 냉동식품");
  } else if (longShelfId === "chk_retort") {
      summaries.push("레토르트식품");
  } else {
      const longShelfLabel = getCheckedLabel('.grp-long-shelf');
      if (longShelfLabel) summaries.push(longShelfLabel);
  }

  // 제조방법 체크 항목 확인 및 변환
  const methodLabels = {
      "chk_sanitized": "살균제품",
      "chk_aseptic": "멸균제품",
      "chk_yutang": "유탕.유처리제품"
  };

  let methodChecked = false;

  $(".grp-sterilization:checked").each(function () {
      const methodId = $(this).attr("id");
      if (methodLabels[methodId]) {
          summaries.push(methodLabels[methodId]);
          methodChecked = true;
      }
  });

  // 조건 체크박스가 체크되었을 때 조건 필드의 값을 추가
  if ($("#chk_sterilization_other").is(":checked")) {
    const conditionValue = $("input[name='processing_condition']").val();
    if (conditionValue && conditionValue.trim()) {
      summaries.push(conditionValue);
    }
  }
  
  // 변경된 조건: 가열하여 섭취하는 냉동식품 + 제조방법 모두 미체크 => 비살균제품
  if (isFrozenHeated && !methodChecked) {
      summaries.push("비살균제품");
  }

  $('#selected-info').text("식품유형 : " + summaries.join(" | "));
}

// ------------------ 팝업 로직 ------------------
function handleIngredientPopup() {
  // 팝업 열기
  openIngredientPopup();
  
  // 원재료명(참고) 섹션이 존재하는 경우에만 표시 (템플릿에서 조건부로 렌더링되기 때문)
  const rawmtrlSection = document.getElementById('rawmtrl_nm_section');
  if (rawmtrlSection) {
    if (rawmtrlSection.classList.contains('collapse')) {
      rawmtrlSection.classList.add('show'); // 펼치기
    }
  }
}

function openIngredientPopup() {
  const rawmtrlNmDisplay = document.querySelector('textarea[name="rawmtrl_nm_display"]').value || "";
  const labelId = document.getElementById('label_id')?.value;
  const url = `/label/ingredient-popup/?rawmtrl_nm_display=${encodeURIComponent(rawmtrlNmDisplay)}&label_id=${labelId}`;
  window.open(url, 'IngredientPopup', 'width=1400,height=900,scrollbars=yes');
}

function openPreviewPopup() {
  const labelId = document.getElementById('label_id')?.value;
  if (!labelId) {
    alert("라벨이 저장되지 않았습니다.");
    return;
  }
  // 선택된 체크박스만 쿼리스트링에 반영
  const checkedFields = document.querySelectorAll("input[type='checkbox']:checked");
  let queryString = new URLSearchParams();
  checkedFields.forEach((chk) => {
    queryString.append(chk.name, "true");
  });
  const previewUrl = `/label/preview/?label_id=${labelId}&${queryString.toString()}`;
  window.open(previewUrl, 'previewPopup', 'width=1400,height=900,scrollbars=yes');
}

window.addEventListener('message', function(e) {
  if (e.data.type === 'applyPhrases') {
    const phrases = e.data.phrases;
    const categoryMapping = {
      'storage': 'storage_method',
      'package': 'frmlc_mtrqlt',
      'manufacturer': 'bssh_nm',
      'distributor': 'distributor_address',
      'repacker': 'repacker_address',
      'importer': 'importer_address',
      'expiry': 'pog_daycnt',
      'cautions': 'cautions',
      'additional': 'additional_info'
    };

    Object.keys(phrases).forEach(category => {
      const mappedCategory = categoryMapping[category] || category;
      const textarea = document.querySelector(`textarea[name="${mappedCategory}"]`);
      if (textarea) {
        if (Array.isArray(phrases[category]) && phrases[category].length > 0) {
          const contents = phrases[category].map(p => p.content).join('\n');
          textarea.value = contents;
          updateTextareaHeight(textarea);
        } else if (phrases[category] && phrases[category][0]) {
          textarea.value = phrases[category][0].content;
          updateTextareaHeight(textarea);
        }
      }
    });
  }
});

// ------------------ 토글 버튼 로직 ------------------
function initToggleButtons() {
  // 식품유형 섹션 토글
  const foodTypeBtn = document.getElementById("toggleFoodTypeBtn");
  const foodTypeSection = document.querySelector("#food-type-section");
  
  if (foodTypeBtn && foodTypeSection) {
    foodTypeBtn.addEventListener("click", function () {
      const isHidden = foodTypeSection.style.display === "none";
      foodTypeSection.style.display = isHidden ? "block" : "none";
      foodTypeBtn.innerText = isHidden ? "∧" : "∨";
      foodTypeBtn.setAttribute("title", isHidden ? "접기" : "펼치기");
    });
  }

  // 규정 패널 토글
  const regulationBtn = document.getElementById("toggleRegulationBtn");
  const regulationPanel = document.getElementById("regulationPanel");
  
  if (regulationBtn && regulationPanel) {
    regulationBtn.addEventListener("click", function () {
      const isCollapsed = regulationPanel.classList.toggle("collapsed");
      regulationBtn.innerHTML = isCollapsed ? "❮" : "❯";
      regulationBtn.setAttribute("title", isCollapsed ? "펼치기" : "접기");
    });
  }

  // 제조원 정보 토글
  const manufacturerBtn = document.getElementById("toggleManufacturerBtn");
  const manufacturerCollapse = document.getElementById("other-manufacturers");
  
  if (manufacturerBtn && manufacturerCollapse) {
    manufacturerCollapse.addEventListener("shown.bs.collapse", function () {
      manufacturerBtn.innerText = "∧";
      manufacturerBtn.setAttribute("title", "접기");
    });

    manufacturerCollapse.addEventListener("hidden.bs.collapse", function () {
      manufacturerBtn.innerText = "∨";
      manufacturerBtn.setAttribute("title", "펼치기");
    });
  }
}

// ------------------ 영양성분 데이터 처리 ------------------
function updateNutritionFields(data) {
  if (data) {
    const fieldMap = {
      serving_size: "serving_size",
      serving_size_unit: "serving_size_unit",
      units_per_package: "units_per_package",
      nutrition_display_unit: "nutrition_display_unit",
      calories: "calories",
      calories_unit: "calories_unit",
      natriums: "natriums",
      natriums_unit: "natriums_unit",
      carbohydrates: "carbohydrates",
      carbohydrates_unit: "carbohydrates_unit",
      sugars: "sugars", 
      sugars_unit: "sugars_unit",
      fats: "fats",
      fats_unit: "fats_unit",
      trans_fats: "trans_fats",
      trans_fats_unit: "trans_fats_unit",
      saturated_fats: "saturated_fats",
      saturated_fats_unit: "saturated_fats_unit",
      cholesterols: "cholesterols",
      cholesterols_unit: "cholesterols_unit",
      proteins: "proteins",
      proteins_unit: "proteins_unit"
    };
    
    Object.keys(fieldMap).forEach(key => {
      const field = document.querySelector(`input[name="${fieldMap[key]}"]`);
      if (field && data[key] !== undefined) {
        field.value = data[key];
      }
    });
  }
}

function openNutritionCalculator() {
    const labelId = document.getElementById('label_id').value;
    const url = `/label/nutrition-calculator-popup/?label_id=${labelId}`;
    window.open(url, 'NutritionCalculator', 'width=1100,height=900,scrollbars=yes');
}

// ------------------ 식품유형 대분류-소분류 연동 기능 ------------------
function initFoodTypeFiltering() {
  const initialFoodGroup = $('#food_group').val();
  const initialFoodType = $('#food_type').val();
  
  // hidden 필드에 초기값 설정
  $('#hidden_food_group').val(initialFoodGroup);
  $('#hidden_food_type').val(initialFoodType);
  
  if (initialFoodType && (!initialFoodGroup || initialFoodGroup === '')) {
    // 소분류에 대응하는 대분류 찾기
    const selectedOption = $('#food_type option:selected');
    const group = selectedOption.data('group');
    
    if (group) {
      $('#food_group').val(group);
      $('#hidden_food_group').val(group);
    } else {
      fetch(`/label/get-food-group/?food_type=${encodeURIComponent(initialFoodType)}`)
        .then(response => response.json())
        .then(data => {
          if (data.success && data.food_group) {
            $('#food_group').val(data.food_group);
            $('#hidden_food_group').val(data.food_group);
          }
        })
        .catch(error => console.error('대분류 조회 중 오류:', error));
    }
  }
  
  if (initialFoodGroup && (!initialFoodType || initialFoodType === '')) {
    fetch(`/label/food-types-by-group/?group=${encodeURIComponent(initialFoodGroup)}`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // 소분류 드롭다운 갱신
          const foodTypeSelect = $('#food_type');
          foodTypeSelect.empty().append('<option value="">소분류</option>');
          data.food_types.forEach(item => {
            const option = new Option(item.food_type, item.food_type);
            option.dataset.group = item.food_group;
            foodTypeSelect.append(option);
          });
        }
      })
      .catch(error => console.error('소분류 데이터 로딩 중 오류:', error));
  }
  
  if (initialFoodType) {
    updateCheckboxesByFoodType(initialFoodType)
      .catch(err => console.error('초기 체크박스 설정 중 오류:', err));
  }
}

function updateCheckboxesByFoodType(foodType) {
  if (!foodType) return Promise.resolve();
  return fetch(`/label/food-type-settings/?food_type=${encodeURIComponent(foodType)}`)
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        const settings = data.settings;
        const fieldMappings = {
          'prdlst_dcnm': 'chk_prdlst_dcnm',
          'rawmtrl_nm': 'chk_rawmtrl_nm_display',
          'nutritions': 'chk_calories' // 쉼표 제거
        };
        Object.keys(settings).forEach(field => {
          const value = settings[field];
          const checkboxId = fieldMappings[field] || `chk_${field}`;
          const checkbox = document.getElementById(checkboxId);
          if (checkbox) {
            if (value === 'Y') {
              checkbox.checked = true;
              checkbox.disabled = false;
              checkbox.dataset.forcedDisabled = "false";
            } else if (value === 'N') {
              checkbox.checked = false;
              checkbox.disabled = false;
              checkbox.dataset.forcedDisabled = "false";
            } else if (value === 'D') {
              checkbox.checked = false;
              checkbox.disabled = true;
              checkbox.dataset.forcedDisabled = "true";
            }
            checkbox.dispatchEvent(new Event('change'));
          }
          if (field === 'pog_daycnt' && settings.pog_daycnt) {
            updateDateDropdown(settings.pog_daycnt);
          }
        });
        if (settings.pog_daycnt_options !== undefined) {
          updateDateDropdownOptions(settings.pog_daycnt_options);
        }
        if (settings.relevant_regulations !== undefined) {
          const regulationsTextarea = document.querySelector('textarea[name="related_regulations"]');
          if (regulationsTextarea) {
            regulationsTextarea.value = settings.relevant_regulations;
            adjustRegulationBoxHeight(regulationsTextarea);
          }
        }
        return true;
      }
      return false;
    })
    .catch(error => {
      console.error('체크박스 설정 로딩 중 오류:', error);
      return false;
    });
}

function updateDateDropdown(value) {
  const dateOptions = document.querySelector('select[name="date_option"]');
  if (!dateOptions) return;
  
  Array.from(dateOptions.options).forEach(option => {
    option.disabled = false;
  });
  
  if (value === 'D') {
    Array.from(dateOptions.options).forEach(option => {
      option.disabled = true;
    });
    dateOptions.value = '';
    dateOptions.disabled = true;
  } else if (value === 'Y') {
    dateOptions.disabled = false;
  }
}

function updateDateDropdownOptions(options) {
  const dateOptions = document.querySelector('select[name="date_option"]');
  if (!dateOptions) {
    return;
  }
    
  const currentValue = dateOptions.value;
  
  if (!dateOptions.dataset.originalOptions) {
    dateOptions.dataset.originalOptions = dateOptions.innerHTML;
  }
  
  if (options && Array.isArray(options) && options.length > 0) {
    dateOptions.innerHTML = '';
    
    options.forEach(option => {
      if (!option) return;
      
      const optionElement = document.createElement('option');
      optionElement.value = option;
      optionElement.textContent = option;
      dateOptions.appendChild(optionElement);
    });
    
    if (options.includes(currentValue)) {
      dateOptions.value = currentValue;
    } else if (options.length > 0) {
      dateOptions.value = options[0];
    }
    
  } else {
    
    if (dateOptions.dataset.originalOptions) {
      dateOptions.innerHTML = dateOptions.dataset.originalOptions;
    } else {
      const defaultOptions = [
        {value: '소비기한', text: '소비기한'},
        {value: '품질유지기한', text: '품질유지기한'},
        {value: '제조연월일', text: '제조연월일'},
        {value: '생산연도', text: '생산연도'}
      ];
      
      dateOptions.innerHTML = '';
      defaultOptions.forEach(opt => {
        const optEl = document.createElement('option');
        optEl.value = opt.value;
        optEl.textContent = opt.text;
        dateOptions.appendChild(optEl);
      });
    }
  }
  
  dateOptions.disabled = false;
}

function initCheckboxFieldToggle() {
  const checkboxes = document.querySelectorAll('input[type="checkbox"][id^="chk_"]');
  
  checkboxes.forEach(function(checkbox) {
    if (checkbox.getAttribute('data-initialized') === 'true') {
      return;
    }
    
    checkbox.setAttribute('data-initialized', 'true');
    
    const fieldName = checkbox.id.replace('chk_', '');
    
    if (fieldName === 'rawmtrl_nm') {
      checkbox.disabled = true;
      const textarea = document.querySelector('textarea[name="rawmtrl_nm"]');
      if (textarea) {
        textarea.disabled = true;
        textarea.classList.add('disabled-textarea');
      }
      return;
    }
    
    let relatedFields = findRelatedFields(fieldName);
    
    if (relatedFields.length > 0) {
      checkbox.addEventListener('change', function() {
        relatedFields.forEach(function(field) {
          if (checkbox.dataset.forcedDisabled === "true") {
            field.disabled = true;
            field.classList.add('disabled-textarea');
          } else {
            field.disabled = false;
            field.classList.remove('disabled-textarea');
          }
         });
      });
      
      relatedFields.forEach(function(field) {
        if (checkbox.dataset.forcedDisabled === "true") {
          field.disabled = true;
          field.classList.add('disabled-textarea');
        } else {
          field.disabled = false;
          field.classList.remove('disabled-textarea');
        }
      });
    }
  });
}

function findRelatedFields(fieldName) {
  const fieldMappings = {
    'label_nm': ['input[name="my_label_name"]'],
    'prdlst_dcnm': ['input[name="prdlst_dcnm"]'],
    'prdlst_nm': ['input[name="prdlst_nm"]'],
    'ingredients_info': ['input[name="ingredient_info"]'],
    'content_weight': ['input[name="content_weight"]'],
    'weight_calorie': ['input[name="weight_calorie"]'],
    'prdlst_report_no': ['input[name="prdlst_report_no"]'],
    'country_of_origin': ['select[name="country_of_origin"]'],
    'storage_method': ['input[name="storage_method"]'],
    'frmlc_mtrqlt': ['input[name="frmlc_mtrqlt"]'],
    'manufacturer_info': ['input[name="bssh_nm"]'],
    'distributor_address': ['input[name="distributor_address"]'],
    'repacker_address': ['input[name="repacker_address"]'],
    'importer_address': ['input[name="importer_address"]'],
    'date_info': ['input[name="pog_daycnt"]', 'select[name="date_option"]'],
    'rawmtrl_nm_display': ['textarea[name="rawmtrl_nm_display"]'],
    'rawmtrl_nm': ['textarea[name="rawmtrl_nm"]'],
    'cautions': ['textarea[name="cautions"]'],
    'additional_info': ['textarea[name="additional_info"]'],
    'calories': ['textarea[name="nutrition_text"]']
  };
  
  const selectors = fieldMappings[fieldName] || [];
  const fields = [];
  
  selectors.forEach(function(selector) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(function(el) {
      fields.push(el);
    });
  });
  
  return fields;
}

function setDefaultCheckboxes() {
  const defaultChecked = {
    'chk_prdlst_nm': true,
    'chk_content_weight': true,
    'chk_manufacturer_info': true,
    'chk_date_info': true
  };
  
  const defaultUnchecked = {
    'chk_label_nm': false,
    'chk_ingredients_info': false,
    'chk_distributor_address': false,
    'chk_repacker_address': false,
    'chk_importer_address': false,
    'chk_rawmtrl_nm': false
  };
  
  if (!$('#label_id').val() || $('#label_id').val() === '') {

    Object.keys(defaultChecked).forEach(checkboxId => {
      const checkbox = document.getElementById(checkboxId);
      if (checkbox && !checkbox.disabled) {
        checkbox.checked = defaultChecked[checkboxId];
        checkbox.dispatchEvent(new Event('change'));
      }
    });
    
    Object.keys(defaultUnchecked).forEach(checkboxId => {
      const checkbox = document.getElementById(checkboxId);
      if (checkbox && !checkbox.disabled) {
        checkbox.checked = defaultUnchecked[checkboxId];
        checkbox.dispatchEvent(new Event('change'));
      }
    });
  }
}

function prepareFormData() {
  $('input[type="checkbox"]').each(function() {
    const checkboxName = $(this).attr('name');
    if (checkboxName && checkboxName.startsWith('chk_')) {
      const value = $(this).prop('checked') ? 'Y' : 'N';
      let hiddenField = $(`input[type="hidden"][name="${checkboxName}"]`);
      if (hiddenField.length === 0) {
        hiddenField = $('<input>').attr({
          type: 'hidden',
          name: checkboxName,
          value: value
        });
        $(this).after(hiddenField);
      } else {
        hiddenField.val(value);
      }
    }
  });
  
  const preservationType = $('.grp-long-shelf:checked').val() || '';
  const processingMethod = $('.grp-sterilization:checked').not('#chk_sterilization_other').val() || '';
  const processingCondition = $('input[name="processing_condition"]').val() || '';
  
  $('#hidden_preservation_type').val(preservationType);
  $('#hidden_processing_method').val(processingMethod);
  $('#hidden_processing_condition').val(processingCondition);

}

// Select2 초기화 함수 추가
function initSelect2Components() {
  // 대분류 드롭다운에 select2 적용
  $('#food_group').select2({
    placeholder: "대분류 선택",
    allowClear: true,
    width: '100%'
  });
  
  // 소분류 드롭다운에 select2 적용
  $('#food_type').select2({
    placeholder: "소분류 선택",
    allowClear: true,
    width: '100%'
  });
  
  // 원산지 드롭다운에 select2 적용
  $('select[name="country_of_origin"]').select2({
    placeholder: "원산지 선택",
    allowClear: true,
    width: '100%'
  });
}

// Document Ready 이벤트 핸들러
$(document).ready(function() {
  
  // Select2 컴포넌트 초기화
  initSelect2Components();
  
  initCheckBoxGroups();
  updateSummary();
  $('.select2-food-type, input[type="checkbox"], input[name="sterilization_other_detail"]')
    .on('change input', updateSummary);
  initToggleButtons();
  initFoodTypeFiltering();
  
  $('#food_type').off('change').on('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    if (selectedOption && selectedOption.value) {
      const group = selectedOption.dataset.group;
      
      if (group) {
        $('#food_group').val(group).trigger('change.select2');
        $('#hidden_food_group').val(group);
      } else if (!group) {
        fetch(`/label/get-food-group/?food_type=${encodeURIComponent(selectedOption.value)}`)
          .then(response => response.json())
          .then(data => {
            if (data.success && data.food_group) {
              $('#food_group').val(data.food_group).trigger('change.select2');
              $('#hidden_food_group').val(data.food_group);
              selectedOption.dataset.group = data.food_group;
            }
          })
          .catch(error => console.error('대분류 조회 중 오류:', error));
      }
      
      updateCheckboxesByFoodType(selectedOption.value);
      updateSummary();
    }
  });
  
  $('#food_group').off('change').on('change', function() {
    const selectedGroup = this.value;
    
    $('#hidden_food_group').val(selectedGroup);
    
    const foodTypeSelect = $('#food_type');
    
    // 소분류 비우고 기본 옵션 추가
    foodTypeSelect.empty();
    foodTypeSelect.append(new Option('소분류', ''));
    const currentFoodType = $('#food_type').val();
    foodTypeSelect.empty().append('<option value="">소분류</option>');
    
    if (!selectedGroup) {
      fetch('/label/food-types-by-group/')
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            data.food_types.forEach(item => {
              const option = new Option(item.food_type, item.food_type);
              option.dataset.group = item.food_group;
              foodTypeSelect.append(option);
            });
            // 소분류 select2 업데이트 - 초기화 후 다시 적용
            foodTypeSelect.val(null).trigger('change.select2');
            if (currentFoodType) {
              foodTypeSelect.val(currentFoodType);
            }
          }
        })
        .catch(error => console.error('소분류 데이터 로딩 중 오류:', error));
    } else {
      fetch(`/label/food-types-by-group/?group=${encodeURIComponent(selectedGroup)}`)
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            data.food_types.forEach(item => {
              const option = new Option(item.food_type, item.food_type);
              option.dataset.group = item.food_group;
              foodTypeSelect.append(option);
            });
            // 소분류 select2 업데이트 - 초기화 후 다시 적용
            foodTypeSelect.val(null).trigger('change.select2');
            if (currentFoodType) {
              const exists = Array.from(foodTypeSelect.options).some(opt => opt.value === currentFoodType);
              if (exists) {
                foodTypeSelect.val(currentFoodType);
              }
            }
          }
        })
        .catch(error => console.error('소분류 데이터 로딩 중 오류:', error));
    }
    
    updateSummary();
  });
  
  initCheckboxFieldToggle();
  
  $("#labelForm").off('submit').on('submit', function() {
    
    // 식품유형 값 최종 확인 및 설정
    const selectedFoodGroup = $('#food_group').val();
    const selectedFoodType = $('#food_type').val();
    $('#hidden_food_group').val(selectedFoodGroup);
    $('#hidden_food_type').val(selectedFoodType);
    prepareFormData();
    
    return true; // 폼 제출 계속 진행
  });
  
  $('#food_group').on('change', function() {
    const selectedValue = $(this).val();
    $('#hidden_food_group').val(selectedValue);
  });
  
  $('#food_type').on('change', function() {
    const selectedValue = $(this).val();
    $('#hidden_food_type').val(selectedValue);
    
    if (selectedValue) {
      updateCheckboxesByFoodType(selectedValue)
        .catch(err => console.error('체크박스 설정 적용 중 오류:', err));
    }
  });
  
  $('#hidden_food_group').val($('#food_group').val());
  $('#hidden_food_type').val($('#food_type').val());
  
  const selectedFoodType = $('#food_type').val();
  if (selectedFoodType) {
    updateCheckboxesByFoodType(selectedFoodType)
      .catch(err => console.error('초기 체크박스 설정 중 오류:', err));
  } else {
    setDefaultCheckboxes();
    document.querySelectorAll('input[type="checkbox"][id^="chk_"]').forEach(function(checkbox) {
      checkbox.dispatchEvent(new Event('change'));
    });
  }

});

document.addEventListener('DOMContentLoaded', function() {
  function initAutoExpand() {
      document.querySelectorAll('textarea.form-control, textarea.auto-expand').forEach(textarea => {
          adjustHeight(textarea);
          if (textarea.name !== 'related_regulations') {
              textarea.addEventListener('input', function() { adjustHeight(this); });
              textarea.addEventListener('change', function() { adjustHeight(this); });
          }
      });
  }

  function adjustHeight(element) {
      element.style.height = '38px';
      element.style.height = element.scrollHeight + 'px';
  }

  initAutoExpand();

  window.updateTextareaHeight = function(textarea) {
      if (textarea) adjustHeight(textarea);
  };

  const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
          mutation.addedNodes.forEach(function(node) {
              if (node.nodeType === 1) {
                  const textareas = node.querySelectorAll('textarea.form-control, textarea.auto-expand');
                  textareas.forEach(textarea => adjustHeight(textarea));
              }
          });
      });
  });

  observer.observe(document.body, { childList: true, subtree: true });

  const regulationTextarea = document.querySelector('textarea[name="related_regulations"]');
  if (regulationTextarea) {
    regulationTextarea.style.fontSize = '0.8rem';
    adjustRegulationBoxHeight(regulationTextarea);
  }
}); // 닫는 괄호 추가

function updateParentTextarea(category, content) {
  if (window.opener) {
      const textarea = window.opener.document.querySelector(`[name="${category}"]`);
      if (textarea) {
          textarea.value = content;
          window.opener.updateTextareaHeight(textarea);
      }
  }
}

function openPhrasePopup() {
  const width = 1100;
  const height = 900;
  const left = (screen.width - width) / 2;
  const top = (screen.height - height) / 2;
  window.open('/label/phrases/', 'phrasePopup', 
      `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`);
}

// ------------------ 내문구 탭 기능 (툴팁 + 즐겨찾기 정렬 + 디자인 동기화) ------------------

let phraseInsertMode = 'append';
let lastFocusedFieldName = null;

function getCategoryFromFieldName(fieldName) {
  const mapping = {
    'storage_method': 'storage',
    'frmlc_mtrqlt': 'package',
    'bssh_nm': 'manufacturer',
    'distributor_address': 'distributor',
    'repacker_address': 'repacker',
    'importer_address': 'importer',
    'pog_daycnt': 'expiry',
    'cautions': 'cautions',
    'additional_info': 'additional'
  };
  return mapping[fieldName] || null;
}

// 수정된 renderMyPhrasesForFocusedField 함수
function renderMyPhrasesForFocusedField() {
  const fieldName = lastFocusedFieldName || 'prdlst_nm';
  const category = getCategoryFromFieldName(fieldName);
  const listContainer = document.getElementById('myPhraseList');
  
  if (!category || !window.phrasesData) {
      if (listContainer) {
          listContainer.innerHTML = '<div class="text-muted" style="font-size: 0.8rem;">문구 데이터를 로드할 수 없습니다.</div>';
      }
      return;
  }
  if (!listContainer) {
      return;
  }

  listContainer.innerHTML = '<div class="loading" style="font-size: 0.8rem;">로딩 중...</div>';

  const isMultiSelect = ['cautions', 'additional'].includes(category);

  const textarea = document.querySelector(`textarea[name="${fieldName}"]`) ||
                  document.querySelector(`input[name="${fieldName}"]`);
  const currentValues = textarea ? textarea.value.split('\n').map(v => v.trim()).filter(Boolean) : [];

  const phraseList = window.phrasesData[category] || [];
  if (!phraseList.length) {
      listContainer.innerHTML = '<div class="text-muted" style="font-size: 0.8rem;">저장된 문구가 없습니다. 문구 관리에서 추가하세요.</div>';
      return;
  }

  const sortedPhrases = [...phraseList].sort((a, b) => {
      const aFav = a.note && a.note.includes('★') ? -1 : 0;
      const bFav = b.note && b.note.includes('★') ? -1 : 0;
      return aFav - bFav;
  });

  setTimeout(() => {
      const existingItems = new Map(Array.from(listContainer.children).map(item => [item.textContent, item]));
      listContainer.innerHTML = '';
      
      sortedPhrases.forEach(p => {
          let div;
          if (existingItems.has(p.content)) {
              div = existingItems.get(p.content);
          } else {
              div = document.createElement('div');
              div.className = 'phrase-item';
              div.textContent = p.content;
              div.style.padding = '6px 8px';
              div.style.border = '1px solid #ccc';
              div.style.borderRadius = '4px';
              div.style.cursor = 'pointer';
              div.style.fontSize = '0.8rem';
              div.style.transition = 'background-color 0.2s';
              div.style.marginBottom = '4px';

              div.addEventListener('click', () => {
                  if (!textarea) return;
                  if (isMultiSelect) {
                      const values = textarea.value.split('\n').map(v => v.trim()).filter(Boolean);
                      const index = values.indexOf(p.content);
                      if (index === -1) {
                          values.push(p.content);
                          div.style.backgroundColor = '#d0ebff';
                      } else {
                          values.splice(index, 1);
                          div.style.backgroundColor = '#fff';
                      }
                      textarea.value = values.join('\n');
                  } else {
                      if (textarea.value === p.content) {
                          textarea.value = '';
                          div.style.backgroundColor = '#fff';
                      } else {
                          textarea.value = p.content;
                          listContainer.querySelectorAll('.phrase-item').forEach(item => {
                              item.style.backgroundColor = '#fff';
                          });
                          div.style.backgroundColor = '#d0ebff';
                      }
                  }
                  updateTextareaHeight(textarea);
              });
          }

          const isSelected = currentValues.includes(p.content);
          div.style.backgroundColor = isSelected ? '#d0ebff' : '#fff';
          if (p.note) div.title = p.note;

          listContainer.appendChild(div);
      });
  }, 300);
}

document.addEventListener('DOMContentLoaded', () => {
  let focusTimeout;
  document.querySelectorAll('textarea, input[type="text"]').forEach(el => {
      el.addEventListener('focus', function () {
          clearTimeout(focusTimeout);
          focusTimeout = setTimeout(() => {
              lastFocusedFieldName = this.getAttribute('name');
              const myTab = document.getElementById('myphrases-tab');
              if (myTab && myTab.classList.contains('active')) {
                  renderMyPhrasesForFocusedField();
              }
          }, 100);
      });
  });

  const tabButtons = document.querySelectorAll('#phraseTab .nav-link');
  tabButtons.forEach(btn => {
    btn.style.fontSize = '0.8rem';
    btn.addEventListener('shown.bs.tab', () => {
      tabButtons.forEach(b => b.style.color = '');
      btn.style.color = '#0d6efd';
    });
    if (btn.classList.contains('active')) {
      btn.style.color = '#0d6efd';
    } else {
      btn.style.color = '';
    }
  });

  const myTab = document.getElementById('myphrases-tab');
  if (myTab) {
    myTab.addEventListener('click', () => {
      renderMyPhrasesForFocusedField();
    });
  }
});

// 규정 정보 표시 함수
function showRegulationInfo(fieldName) {
    const container = document.getElementById('myPhraseContainer');
    if (!container) return;

    const existingMsg = container.querySelector('.text-muted');
    if (existingMsg) existingMsg.remove();
    
    const existingInfo = container.querySelector('.regulation-info');
    if (existingInfo) existingInfo.remove();

    const fieldMapping = {
        'my_label_name': 'label_nm',
        'prdlst_dcnm': 'prdlst_dcnm',
        'prdlst_nm': 'prdlst_nm',
        'ingredient_info': 'ingredients_info',
        'content_weight': 'content_weight',
        'storage_method': 'storage',
        'frmlc_mtrqlt': 'package',
        'bssh_nm': 'manufacturer',
        'distributor_address': 'distributor',
        'pog_daycnt': 'expiry',
        'weight_calorie': 'weight_calorie',
        'rawmtrl_nm_display': 'rawmtrl_nm',
        'cautions': 'cautions',
        'additional_info': 'additional'
    };

    const mappedField = fieldMapping[fieldName] || fieldName;
    const regulationInfo = regulations[mappedField];

    if (regulationInfo) {
        const infoContainer = document.createElement('div');
        infoContainer.className = 'regulation-info';
        
        const lines = regulationInfo.split('\n');
        infoContainer.innerHTML = lines.map(line => 
            line.trim() ? `<p class="mb-1">${line}</p>` : '<br>'
        ).join('');
        
        const phraseList = document.getElementById('myPhraseList');
        container.appendChild(infoContainer);
    }
}

// 입력 필드 focus 이벤트에 규정 표시 추가
document.querySelectorAll('input[type="text"], textarea').forEach(el => {
    el.addEventListener('focus', function() {
        const fieldName = this.getAttribute('name');
        if (fieldName) {
            showRegulationInfo(fieldName);
        }
    });
});

let regulations = {};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('regulations-data')) {
        regulations = JSON.parse(document.getElementById('regulations-data').textContent);
    }

    let focusTimeout;
    document.querySelectorAll('textarea, input[type="text"]').forEach(el => {
        el.addEventListener('focus', function() {
            clearTimeout(focusTimeout);
            focusTimeout = setTimeout(() => {
                lastFocusedFieldName = this.getAttribute('name');
                const fieldName = lastFocusedFieldName;
                const myPhrasesTab = document.querySelector('#myphrases-tab');
                if (myPhrasesTab && myPhrasesTab.classList.contains('active')) {
                    renderMyPhrasesForFocusedField();
                    showRegulationInfo(fieldName);
                }
            }, 100);
        });
    });

    // 에러 수정: #myphrases-tab 요소가 존재하는지 확인 후 이벤트 리스너 추가
    const myPhrasesTab = document.querySelector('#myphrases-tab');
    if (myPhrasesTab) {
        myPhrasesTab.addEventListener('shown.bs.tab', () => {
            if (lastFocusedFieldName) {
                renderMyPhrasesForFocusedField();
                showRegulationInfo(lastFocusedFieldName);
            }
        });
    }
});

function adjustRegulationBoxHeight(textarea) {
  if (!textarea) return;
  const container = document.getElementById('regulation-content');
  if (!container) {
    return;
  }
  textarea.style.height = 'auto';
  const tabContent = container.closest('.tab-content');
  const maxHeight = tabContent ? tabContent.clientHeight * 0.9 : window.innerHeight * 0.6;
  const scrollHeight = textarea.scrollHeight + 10;
  container.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
  container.style.overflowY = scrollHeight > maxHeight ? 'auto' : 'hidden';
  textarea.style.height = '100%';
  textarea.style.resize = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
  function initAutoExpand() {
    document.querySelectorAll('textarea.form-control, textarea.auto-expand').forEach(textarea => {
      adjustHeight(textarea);
      if (textarea.name !== 'related_regulations') {
        textarea.addEventListener('input', function() {
          adjustHeight(this);
        });
        textarea.addEventListener('change', function() {
          adjustHeight(this);
        });
      }
    });
  }

  function adjustHeight(element) {
    element.style.height = '380px';
    element.style.height = element.scrollHeight + 'px';
  }

  initAutoExpand();

  window.updateTextareaHeight = function(textarea) {
    if (textarea) {
      adjustHeight(textarea);
      if (textarea.name === 'related_regulations') {
        adjustRegulationBoxHeight(textarea);
      }
    }
  };

  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      mutation.addedNodes.forEach(function(node) {
        if (node.nodeType === 1) {
          const textareas = node.querySelectorAll('textarea.form-control, textarea.auto-expand');
          textareas.forEach(textarea => {
            adjustHeight(textarea);
            if (textarea.name === 'related_regulations') {
              adjustRegulationBoxHeight(textarea);
            }
          });
        }
      });
    });
  });

  observer.observe(document.body, { childList: true, subtree: true });

  const regulationTextarea = document.querySelector('textarea[name="related_regulations"]');
  if (regulationTextarea) {
    regulationTextarea.style.fontSize = '0.8rem';
    adjustRegulationBoxHeight(regulationTextarea);
  }
});