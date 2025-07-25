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

  function adjustHeight(element, maxHeight = Infinity) {
    if (!element) return;
    element.style.height = 'auto';  // 기본 높이 제거
    const scrollHeight = element.scrollHeight + 2;
    element.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
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
    if (!textarea) return;
    const isRegulation = textarea.name === 'related_regulations';
    adjustHeight(textarea, isRegulation ? Infinity : 200);  // 일반 항목도 최대 200px까지는 허용
    if (isRegulation) {
      adjustRegulationBoxHeight(textarea);
    }
  };

  function initAutoExpand() {
    document.querySelectorAll('textarea.form-control, textarea.auto-expand').forEach(textarea => {
      updateTextareaHeight(textarea);
      if (textarea.name !== 'related_regulations') {
        textarea.addEventListener('input', () => updateTextareaHeight(textarea));
        textarea.addEventListener('change', () => updateTextareaHeight(textarea));
      }
    });

    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === 1) {
            node.querySelectorAll('textarea.form-control, textarea.auto-expand').forEach(updateTextareaHeight);
          }
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

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
    const summaries = [];
    const foodSmall = $('#food_type option:selected').text();
    if (foodSmall && foodSmall !== '소분류') {
      summaries.push(foodSmall);
    }

    const longShelfId = $('.grp-long-shelf:checked').attr('id');
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
    // 적용 버튼 시에만 summary-step1에 표시
    $('#summary-step1').text(summaryText).attr('title', summaryText);
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

    function updateHiddenFields() {
      hiddenFoodGroup.val(foodGroup.val());
      hiddenFoodType.val(foodType.val());
    }

    function updateFoodTypes(group, currentType) {
      foodType.empty().append('<option value="">소분류</option>');
      // 대분류가 비어있어도 전체 식품유형 데이터를 불러옴
      const url = `/label/food-types-by-group/?group=${encodeURIComponent(group || '')}`;
      
      fetch(url)
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            data.food_types.forEach(item => {
              const option = new Option(item.food_type, item.food_type);
              option.dataset.group = item.food_group;
              foodType.append(option);
            });
            foodType.val(currentType && data.food_types.some(t => t.food_type === currentType) ? currentType : null).trigger('change.select2');
          }
        });
    }

    foodGroup.on('change', function () {
      const group = this.value;
      updateHiddenFields();
      updateFoodTypes(group, foodType.val());
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
      updateFoodTypes('', initialFoodType);
    }

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
    initAutoExpand();

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
    document.getElementById('applyStep1Btn').style.display = 'none';
    document.getElementById('expandStep1Btn').style.display = '';
  }

  function step1Expand() {
    document.getElementById('step1-body').style.display = '';
    document.getElementById('applyStep1Btn').style.display = '';
    document.getElementById('expandStep1Btn').style.display = 'none';
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
  document.getElementById('applyStep1Btn').style.display = '';
  document.getElementById('expandStep1Btn').style.display = 'none';
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
    if (btn.textContent === '검증완료' || btn.textContent === '검증실패') {
      btn.textContent = '번호검증';
      btn.classList.remove('btn-success', 'btn-danger');
      btn.classList.add('btn-outline-primary');
      return;
    }
    btn.disabled = true;
    btn.textContent = '저장 중...';
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    let reportNo = reportNoInput?.value?.trim();
    if (!reportNo) {
      alert('품목보고번호를 입력하세요.');
      btn.disabled = false;
      btn.textContent = '번호검증';
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
      btn.textContent = '검증 중...';
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
        btn.textContent = '검증완료';
        btn.classList.remove('btn-outline-primary', 'btn-danger');
        btn.classList.add('btn-success');
      } else {
        btn.textContent = '검증실패';
        btn.classList.remove('btn-outline-primary', 'btn-success');
        btn.classList.add('btn-danger');
      }
    })
    .catch(err => {
      alert('저장 또는 검증 중 오류가 발생했습니다. ' + (err.message || ''));
      btn.textContent = '번호검증';
    })
    .finally(() => {
      btn.disabled = false;
    });
  };
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
});