// 전역 데이터 초기화

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
  pog_daycnt: 'chk_pog_daycnt',
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
  pog_daycnt_arr: ['input[name="pog_daycnt"]', 'select[name="date_option_display"]'],
  rawmtrl_nm_display_arr: ['textarea[name="rawmtrl_nm_display"]'],
  rawmtrl_nm_arr: ['textarea[name="rawmtrl_nm"]'],
  cautions_arr: ['textarea[name="cautions"]'],
  additional_info_arr: ['textarea[name="additional_info"]'],
  calories_arr: ['textarea[name="nutrition_text"]']
};

// DOMContentLoaded 이벤트로 초기화 보장
document.addEventListener('DOMContentLoaded', function () {
  // 초기화

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

  // ------------------ 필드 클릭 이벤트 초기화 ------------------
  let nutritionPopupOpen = false;
  let ingredientPopupOpen = false;

  function initFieldClickEvents() {
    // 영양성분 필드 클릭 시 계산기 팝업 열기
    const nutritionTextarea = document.getElementById('nutrition_text');
    if (nutritionTextarea) {
      nutritionTextarea.addEventListener('click', function(e) {
        e.preventDefault();
        if (!nutritionPopupOpen) {
          nutritionPopupOpen = true;
          handleNutritionTablePopup();
          setTimeout(() => {
            nutritionPopupOpen = false;
          }, 1000);
        }
      });
    }

    // 원재료명(표로입력) 필드 클릭 시 원재료명 팝업 열기
    const rawmtrlTextarea = document.getElementById('rawmtrl_nm');
    if (rawmtrlTextarea) {
      // 원재료명 필드는 항상 클릭 가능하도록 disabled 속성 강제 제거
      rawmtrlTextarea.disabled = false;
      rawmtrlTextarea.classList.remove('disabled-textarea');
      
      rawmtrlTextarea.addEventListener('click', function(e) {
        e.preventDefault();
        if (!ingredientPopupOpen) {
          ingredientPopupOpen = true;
          handleIngredientPopup();
          setTimeout(() => {
            ingredientPopupOpen = false;
          }, 1000);
        }
      });
    }
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

  // ===== 영양성분 계산기 팝업 관련 함수들 =====

  // 팝업 열기
  window.openNutritionCalculator = function () {
    const labelId = document.getElementById('label_id')?.value || '';
    openPopup(`/label/nutrition-calculator-popup/?label_id=${labelId}`, 'NutritionCalculator', 1300, 1000);
  };

  // 팝업 열기 (기존 데이터 포함)
  window.handleNutritionTablePopup = function () {
      const labelId = document.getElementById('label_id')?.value || '';
      const existingData = collectExistingNutritionData();
      const productNameField = document.querySelector('input[name="prdlst_nm"]');
      if (productNameField && productNameField.value.trim()) {
          existingData.product_name = productNameField.value.trim();
      }

      let url = `/label/nutrition-calculator-popup/?label_id=${labelId}`;
      if (existingData && Object.keys(existingData).length > 0) {
          const params = new URLSearchParams();
          Object.keys(existingData).forEach(key => {
              // 모든 필드를 전달 (빈 값도 포함)
              params.append(key, existingData[key] || '');
          });
          url += '&' + params.toString();
      }
      openPopup(url, 'NutritionCalculator', 1300, 1000);
  };

  // 부모창의 기존 영양성분 데이터 수집 (필드명 통일로 간소화)
  function collectExistingNutritionData() {
  // 기존 영양성분 데이터 수집 시작
    const data = {};
    
    // 기본 설정값들 (HTML 템플릿의 hidden 필드와 일치)
    const basicFields = [
      'serving_size', 'serving_size_unit', 'units_per_package', 'nutrition_display_unit',
      'basic_display_type', 'parallel_display_type'
    ];
    
    // 영양성분 필드들 (HTML과 일치하는 필드명 사용)
    const nutritionFields = [
      'calories', 'natriums', 'carbohydrates', 'sugars', 
      'fats', 'trans_fats', 'saturated_fats', 
      'cholesterols', 'proteins',
      
      // 추가 영양성분 (선택) - 모델의 26개 필드와 정확히 일치
      'dietary_fiber', 'calcium', 'iron', 'magnesium', 'phosphorus', 
      'potassium', 'zinc', 'vitamin_a', 'vitamin_d', 'vitamin_c', 
      'thiamine', 'riboflavin', 'niacin', 'vitamin_b6', 'folic_acid', 
      'vitamin_b12', 'selenium', 'iodine', 'copper', 'manganese', 
      'chromium', 'molybdenum', 'vitamin_e', 'vitamin_k', 'biotin', 'pantothenic_acid'
    ];
    
    // 모든 필드 검사 (다양한 셀렉터로 필드 찾기) - 영양성분 unit 필드도 포함
    [...basicFields, ...nutritionFields].forEach(fieldName => {
      let field = document.querySelector(`input[name="${fieldName}"]`);
      if (!field) field = document.getElementById(fieldName);
      if (!field) field = document.querySelector(`input[type="hidden"][name="${fieldName}"]`);
      if (!field) field = document.querySelector(`[name="${fieldName}"]`);
      
      // 영양성분 단위 필드도 수집
      let unitField = null;
      if (nutritionFields.includes(fieldName)) {
        unitField = document.querySelector(`input[name="${fieldName}_unit"]`);
      }
      
      // 모든 필드를 수집하되, 기본 필드는 빈 값도 포함
      if (field) {
        const popupFieldName = fieldName;
        const value = field.value ? field.value.trim() : '';
        
        // 기본 필드는 빈 값이어도 전달
        if (basicFields.includes(fieldName)) {
          data[popupFieldName] = value;
        } else {
          // 영양성분 필드는 값이 있을 때만 전달
          if (value !== '' && value !== '0') {
            data[popupFieldName] = value;
          }
        }
        
        // 영양성분 단위 필드 처리
        if (unitField) {
          const unitValue = unitField.value ? unitField.value.trim() : '';
          if (unitValue !== '') {
            data[`${fieldName}_unit`] = unitValue;
          }
        }
      } else {
        // 필드를 찾지 못한 경우 기본값으로 빈 문자열 설정 (기본 필드만)
        if (basicFields.includes(fieldName)) {
          data[fieldName] = '';
        }
      }
      
      // 표시 기준 설정 필드가 없으면 기본값 사용
      if (['basic_display_type', 'parallel_display_type'].includes(fieldName) && !field) {
        const defaultValues = {
          'basic_display_type': 'per_100g',
          'parallel_display_type': 'per_serving'
        };
        data[fieldName] = defaultValues[fieldName];
      }
    });
    
  // 수집된 데이터 (디버그 로그 제거)
    
    return data;
  }

  window.openPreviewPopup = function() {
    const form = document.getElementById("labelForm");
    if (!form) {
        console.error("오류: #labelForm 요소를 찾을 수 없습니다.");
        return;
    }
    
    let labelId = document.getElementById('label_id')?.value;
    if (!labelId) {
        const urlParams = new URLSearchParams(window.location.search);
        labelId = urlParams.get('label_id');
    }
    
    if (!labelId) {
        alert('라벨을 먼저 저장해주세요.');
        return;
    }
    
    const url = `/label/preview/?label_id=${labelId}`;
    const popup = window.open(url, "label_preview", "width=1200,height=900,scrollbars=yes,resizable=yes");
    
    if (!popup) {
        alert("팝업이 차단되었습니다. 브라우저의 팝업 차단 설정을 확인해 주세요.");
        return;
    }

    // 팝업이 데이터를 요청하면('requestPreviewData') 이 리스너가 응답합니다.
    window.addEventListener('message', function handlePreviewRequest(e) {
        // 이 메시지가 우리가 연 팝업(e.source)에서 온 것인지 확인
        if (e.source !== popup || e.data.type !== 'requestPreviewData') {
            return;
        }

  // Preview popup requested data; sending collected data

        const checkedData = {};
        
        // 체크박스 ID와 실제 데이터 필드의 name 속성을 1:1로 매핑
        const fieldIdToNameMap = {
            'chk_prdlst_nm': 'prdlst_nm',
            'chk_ingredient_info': 'ingredient_info',
            'chk_prdlst_dcnm': 'prdlst_dcnm',
            'chk_prdlst_report_no': 'prdlst_report_no',
            'chk_content_weight': 'content_weight',
            'chk_country_of_origin': 'country_of_origin',
            'chk_storage_method': 'storage_method',
            'chk_frmlc_mtrqlt': 'frmlc_mtrqlt',
            'chk_bssh_nm': 'bssh_nm',
            'chk_distributor_address': 'distributor_address',
            'chk_repacker_address': 'repacker_address',
            'chk_importer_address': 'importer_address',
            'chk_pog_daycnt': 'pog_daycnt',
            'chk_rawmtrl_nm_display': 'rawmtrl_nm_display',
            'chk_cautions': 'cautions',
            'chk_additional_info': 'additional_info',
            'chk_nutrition_text': 'nutrition_text'
        };

        document.querySelectorAll('input[type="checkbox"][id^="chk_"]').forEach(cb => {
            if (cb.checked) {
                const fieldName = fieldIdToNameMap[cb.id];
                if (fieldName) {
                    const inputElement = document.querySelector(`[name="${fieldName}"]`);
                    if (inputElement) {
                        // 미리보기 페이지가 기대하는 표준 필드명을 키(key)로 사용
                        checkedData[fieldName] = inputElement.value || '';
                        
                        // pog_daycnt 필드의 경우 날짜 옵션도 함께 전달
                        if (fieldName === 'pog_daycnt') {
                            const dateOptionElement = document.querySelector('select[name="date_option_display"]');
                            if (dateOptionElement) {
                                checkedData['date_option'] = dateOptionElement.value || '소비기한';
                            }
                        }
                    }
                }
            }
        });

        // 미리보기 설정값들 수집
        const previewSettings = {
            width: document.querySelector('input[name="width"]')?.value || '10',
            height: document.querySelector('input[name="height"]')?.value || '10',
            font_family: document.querySelector('select[name="font_family"]')?.value || "'Noto Sans KR'",
            font_size: document.querySelector('input[name="font_size"]')?.value || '10',
            letter_spacing: document.querySelector('input[name="letter_spacing"]')?.value || '-5',
            line_height: document.querySelector('input[name="line_height"]')?.value || '1.2'
        };
        


        // 팝업으로 최종 데이터 전송
        popup.postMessage({
            type: 'previewCheckedFields',
            checked: checkedData,
            settings: previewSettings,
            update_datetime: new Date().toISOString().slice(0, 16).replace('T', ' ')
        }, '*');

        // 이벤트 리스너를 한 번만 실행하고 제거하여 중복 호출 방지
        window.removeEventListener('message', handlePreviewRequest);
    });
  };

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
    

    
    return fetch(`/label/food-type-settings/?food_type=${encodeURIComponent(foodType)}`)
      .then(response => response.json())
      .then(data => {

        
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

          updateDateDropdownOptions(settings.pog_daycnt_options);
        }
        
        // 체크박스 업데이트 항상 실행
        Object.keys(settings).forEach(field => {
          if (field === 'relevant_regulations' || field === 'pog_daycnt_options') return;
          
          const value = settings[field];
          const checkboxId = fieldMappings[field] || `chk_${field}`;
          const checkbox = document.getElementById(checkboxId);
          
          if (checkbox) {

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
    const dateOptions = document.querySelector('select[name="date_option_display"]');
    if (!dateOptions) {
      console.warn('Date options select not found in updateDateDropdown');
      return;
    }
    

    
    dateOptions.disabled = value === 'D';
    Array.from(dateOptions.options).forEach(option => (option.disabled = value === 'D'));
    if (value === 'D') {
      dateOptions.value = '';
    }
    

  }

  function updateDateDropdownOptions(options) {
    const dateOptions = document.querySelector('select[name="date_option_display"]');
    if (!dateOptions) {
      console.warn('Date options select not found');
      return;
    }
    

    
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
          // 원재료명(표로입력) 필드는 항상 클릭 가능하도록 disabled 하지 않음
          if (field.name === 'rawmtrl_nm') {
            field.disabled = false;
            field.classList.remove('disabled-textarea');
            return;
          }
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
    // 소비기한/품질유지기한 드롭다운(select[name="date_option_display"])에는 select2를 적용하지 않음 (검색 기능 제거)
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



  // ------------------ 초기화 및 이벤트 바인딩 ------------------
  $(document).ready(function () {
    initSelect2Components();
    initCheckBoxGroups();
    initToggleButtons();
    initCheckboxFieldToggle();
    initFoodTypeFiltering();
    initAutoExpand();
    initFieldClickEvents();

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
  // 제품 정보 자동 입력 함수
  function applyProductDataToLabel(btn, productData) {
    btn.innerHTML = '<i class="fas fa-download me-1"></i>정보가져옴';
    btn.className = 'btn btn-info btn-sm';
    btn.title = '식품안전나라 등록 정보를 가져왔습니다';
    
    // 제품명
    if (productData.prdlst_nm) {
      const prdlstNmInput = document.querySelector('input[name="prdlst_nm"]');
      if (prdlstNmInput) {
        prdlstNmInput.value = productData.prdlst_nm;
        prdlstNmInput.style.backgroundColor = '#e3f2fd';
        prdlstNmInput.style.border = '2px solid #2196f3';
        const checkbox = document.getElementById('chk_prdlst_nm');
        if (checkbox) checkbox.checked = true;
      }
    }
    
    // 식품유형
    if (productData.prdlst_dcnm) {
      const prdlstDcnmInput = document.querySelector('input[name="prdlst_dcnm"]');
      if (prdlstDcnmInput) {
        prdlstDcnmInput.value = productData.prdlst_dcnm;
        prdlstDcnmInput.style.backgroundColor = '#e3f2fd';
        prdlstDcnmInput.style.border = '2px solid #2196f3';
        const checkbox = document.getElementById('chk_prdlst_dcnm');
        if (checkbox) checkbox.checked = true;
      }
    }
    
    // 용기·포장재질
    if (productData.packaging_material) {
      const packagingInput = document.querySelector('input[name="frmlc_mtrqlt"]');
      if (packagingInput) {
        packagingInput.value = productData.packaging_material;
        packagingInput.style.backgroundColor = '#e3f2fd';
        packagingInput.style.border = '2px solid #2196f3';
        const checkbox = document.getElementById('chk_frmlc_mtrqlt');
        if (checkbox) checkbox.checked = true;
      }
    }
    
    // 제조원
    if (productData.manufacturer) {
      const manufacturerInput = document.querySelector('input[name="bssh_nm"]');
      if (manufacturerInput) {
        manufacturerInput.value = productData.manufacturer;
        manufacturerInput.style.backgroundColor = '#e3f2fd';
        manufacturerInput.style.border = '2px solid #2196f3';
        const checkbox = document.getElementById('chk_bssh_nm');
        if (checkbox) checkbox.checked = true;
      }
    }
    
    // 원재료명
    if (productData.rawmtrl_nm) {
      const rawmtrlTextarea = document.querySelector('textarea[name="rawmtrl_nm_display"]');
      if (rawmtrlTextarea) {
        rawmtrlTextarea.value = productData.rawmtrl_nm;
        rawmtrlTextarea.style.backgroundColor = '#e3f2fd';
        rawmtrlTextarea.style.border = '2px solid #2196f3';
        const checkbox = document.getElementById('chk_rawmtrl_nm_display');
        if (checkbox) checkbox.checked = true;
      }
    }
    
    // 성공 알림 표시
    alert('제품 정보를 성공적으로 불러왔습니다.\n\n기본정보(제품명, 식품유형), 원재료명, 기타항목(용기·포장재질, 제조원)이 자동으로 입력되었습니다.');
  }

  window.verifyReportNo = function(labelId) {
    const btn = document.getElementById('verifyReportNoBtn');
    if (!btn) return;
    
    // 상태 복구: 완료된 상태에서 클릭 시 초기화
    const completedStates = ['사용가능', '형식오류', '규칙오류', '미등록', '검증실패', '오류발생', '정보가져옴'];
    const isCompleted = completedStates.some(state => btn.innerHTML.includes(state));
    
    if (isCompleted) {
      btn.innerHTML = '번호검증';
      btn.className = 'btn btn-outline-primary btn-sm';
      btn.title = 'API 중복 검사 및 번호 규칙 검증';
      return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>검증 중...';
    btn.className = 'btn btn-secondary btn-sm';
    
    const reportNoInput = document.querySelector('input[name="prdlst_report_no"]');
    let reportNo = reportNoInput?.value?.trim();
    
    if (!reportNo) {
      btn.innerHTML = '<i class="fas fa-edit me-1"></i>입력필요';
      btn.className = 'btn btn-outline-secondary btn-sm';
      btn.title = '품목보고번호를 입력해주세요';
      btn.disabled = false;
      
      setTimeout(() => {
        alert('품목보고번호를 입력하세요.');
        btn.innerHTML = '번호검증';
        btn.className = 'btn btn-outline-primary btn-sm';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
      }, 1000);
      return;
    }

    // 검증용 번호: 하이픈(-)을 제거한 값
    const verifyReportNo = reportNo.replace(/-/g, '');

    // 단일 API 호출로 검증 진행 (홈 화면과 동일한 방식)
    fetch('/label/verify-report-no/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({ 
        label_id: labelId,  // 라벨 크리에이션에서는 labelId 전달
        prdlst_report_no: verifyReportNo 
      })
    })
    .then(res => res.json())
    .then(data => {
      // 성공 상태 처리
      if (data.verified && data.status === 'available') {
        btn.innerHTML = '<i class="fas fa-check-circle me-1"></i>사용가능';
        btn.className = 'btn btn-success btn-sm';
        btn.title = '등록된 품목보고번호로 사용 가능합니다';
        return;
      }
      
      // 등록된 제품 정보가 있는 경우 - 사용자가 선택
      if (data.status === 'completed' && data.product_data) {
        // 사용자 확인 대화상자
        const userConfirmed = confirm('이미 신고된 제품이 있습니다.\n식품안전나라에 신고된 제품의 정보를 불러오시겠습니까?');
        
        if (!userConfirmed) {
          // 취소 선택 시 - 검증 버튼 초기화
          btn.innerHTML = '번호검증';
          btn.className = 'btn btn-outline-primary btn-sm';
          btn.title = 'API 중복 검사 및 번호 규칙 검증';
          return;
        }
        
        // 확인 선택 시 - 정보 자동 입력
        applyProductDataToLabel(btn, data.product_data);
        return;
      }
      
      // 실패 상태별 처리
      const status = data.status || 'unknown';
      let message = data.message || '검증에 실패했습니다.';
      
      switch(status) {
        case 'format_error':
          btn.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>형식오류';
          btn.className = 'btn btn-warning action-btn-modern';
          btn.title = '품목보고번호 형식이 올바르지 않습니다';
          break;
          
        case 'rule_error':
          btn.innerHTML = '<i class="fas fa-ban me-1"></i>규칙오류';
          btn.className = 'btn btn-warning action-btn-modern';
          btn.title = '품목보고번호 규칙에 맞지 않습니다';
          break;
          
        case 'not_found':
          btn.innerHTML = '<i class="fas fa-question-circle me-1"></i>미등록';
          btn.className = 'btn btn-danger action-btn-modern';
          btn.title = '등록되지 않은 품목보고번호입니다';
          break;
          
        case 'error':
        default:
          btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>검증실패';
          btn.className = 'btn btn-danger action-btn-modern';
          btn.title = '검증 중 오류가 발생했습니다';
          break;
      }
      
      // 비침입적인 방식으로 오류 표시
      setTimeout(() => {
        const shouldRetry = confirm(message + '\n\n다시 검증하시겠습니까?');
        if (shouldRetry) {
          btn.innerHTML = '번호검증';
          btn.className = 'btn btn-outline-primary btn-sm';
          btn.title = 'API 중복 검사 및 번호 규칙 검증';
        }
      }, 100);
    })
    .catch(err => {
      handleVerificationNetworkError(btn, err);
    })
    .finally(() => {
      btn.disabled = false;
    });
  };

  // 검증 오류 처리 함수 (홈 화면과 동일)
  function handleVerificationError(btn, data) {
    const status = data.status || 'unknown';
    let message = data.message || '검증에 실패했습니다.';
    
    switch(status) {
      case 'format_error':
        btn.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>형식오류';
        btn.className = 'btn btn-warning btn-sm';
        btn.title = '품목보고번호 형식이 올바르지 않습니다';
        break;
        
      case 'rule_error':
        btn.innerHTML = '<i class="fas fa-ban me-1"></i>규칙오류';
        btn.className = 'btn btn-warning btn-sm';
        btn.title = '품목보고번호 규칙에 맞지 않습니다';
        break;
        
      case 'not_found':
        btn.innerHTML = '<i class="fas fa-question-circle me-1"></i>미등록';
        btn.className = 'btn btn-danger btn-sm';
        btn.title = '등록되지 않은 품목보고번호입니다';
        break;
        
      case 'completed':
        btn.innerHTML = '<i class="fas fa-info-circle me-1"></i>중복확인';
        btn.className = 'btn btn-info btn-sm';
        btn.title = '이미 등록된 번호입니다';
        break;
        
      case 'error':
      default:
        btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>검증실패';
        btn.className = 'btn btn-danger btn-sm';
        btn.title = '검증 중 오류가 발생했습니다';
        break;
    }
    
    // 비침입적인 방식으로 오류 표시
    setTimeout(() => {
      const shouldRetry = confirm(message + '\n\n다시 검증하시겠습니까?');
      if (shouldRetry) {
        btn.innerHTML = '번호검증';
        btn.className = 'btn btn-outline-primary btn-sm';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
      }
    }, 100);
  }

  // 네트워크 오류 처리 함수 (홈 화면과 동일)
  function handleVerificationNetworkError(btn, err) {
    btn.innerHTML = '<i class="fas fa-wifi me-1"></i>통신오류';
    btn.className = 'btn btn-secondary btn-sm';
    btn.title = '네트워크 연결 또는 서버 오류';
    
    setTimeout(() => {
      const errorMsg = '검증 중 통신 오류가 발생했습니다.\n' + 
                      '인터넷 연결을 확인하고 다시 시도해주세요.\n\n' +
                      '오류 내용: ' + (err.message || '알 수 없는 오류');
      
      if (confirm(errorMsg + '\n\n다시 시도하시겠습니까?')) {
        btn.innerHTML = '번호검증';
        btn.className = 'btn btn-outline-primary btn-sm';
        btn.title = 'API 중복 검사 및 번호 규칙 검증';
      }
    }, 100);
  }

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

  // 팝업에서 보낸 데이터 수신 리스너
  window.addEventListener('message', function(event) {
    // 보안을 위해 event.origin을 확인하는 것이 좋습니다.
    // if (event.origin !== 'https://your-domain.com') return;

    if (event.data && event.data.type === 'nutritionData') {
      const popupData = event.data.data;
      const convertedData = convertPopupDataToParentFormat(popupData);
      handleNutritionDataUpdate(convertedData);
      
      // 영양성분 데이터 업데이트 완료
      
    } else if (event.data && event.data.type === 'nutritionReset') {
      handleNutritionDataReset();
    }
  });

  // 팝업 데이터를 부모창 형식으로 변환 (필드명 통일로 간소화)
  function convertPopupDataToParentFormat(popupData) {
  // 변환 함수 입력 데이터
    const convertedData = { settings: {}, formattedData: {}, resultHTML: '' };
    
    // 기본 설정 데이터 - 모델 필드명으로 매핑
    if (popupData.settings) {
      convertedData.settings = {
        // 계산기에서 전송한 필드명을 부모창 필드명으로 매핑
        serving_size: popupData.settings.serving_size,
        units_per_package: popupData.settings.units_per_package,
        nutrition_display_unit: popupData.settings.nutrition_display_unit,
        serving_size_unit: popupData.settings.serving_size_unit || 'g'
      };
    } else {
      // 하위 호환성을 위한 fallback
      convertedData.settings = {
        base_amount: popupData.baseAmount,
        servings_per_package: popupData.servingsPerPackage,
        nutrition_display_unit: popupData.style,
        basic_display_type: popupData.basic_display_type,
        parallel_display_type: popupData.parallel_display_type
      };
    }
    
    // 영양성분 데이터 - 필드명 통일로 변환 불필요
    if (popupData.nutritionInputs) {
      convertedData.formattedData = popupData.nutritionInputs;
    }
    
    // HTML 결과 추가
    if (popupData.html) {
      convertedData.resultHTML = popupData.html;
    }
    
  // 변환 함수 출력 데이터
    return convertedData;
  }

  // 팝업에서 받은 데이터로 폼 업데이트
  function handleNutritionDataUpdate(data) {
    // 영양성분 데이터 업데이트 처리 (디버그 로그 제거)

    // 1. 기본 설정 데이터 저장 - 실제 존재하는 필드들만 처리
    if (data.settings) {
      // 다양한 가능한 필드명들로 시도
      const possibleBaseAmountFields = [
        'input[name="serving_size"]',
        'input[name="nutrition_base_amount"]',
        'input[name="base_amount"]'
      ];
      
      const possibleUnitsFields = [
        'input[name="units_per_package"]',
        'input[name="servings_per_package"]'
      ];
      
      const possibleStyleFields = [
        'input[name="nutrition_display_unit"]',
        'input[name="nutrition_style"]',
        'input[name="style"]'
      ];

      // 기본 양 필드 찾기
      let baseAmountField = null;
      for (const selector of possibleBaseAmountFields) {
        baseAmountField = document.querySelector(selector);
        if (baseAmountField) break;
      }

      // 포장당 단위 필드 찾기
      let unitsPerPackageField = null;
      for (const selector of possibleUnitsFields) {
        unitsPerPackageField = document.querySelector(selector);
        if (unitsPerPackageField) break;
      }

      // 스타일 필드 찾기 - nutrition_display_unit 필드를 우선 검색
      let nutritionStyleField = document.querySelector('input[name="nutrition_display_unit"]');
      if (!nutritionStyleField) {
        for (const selector of possibleStyleFields) {
          nutritionStyleField = document.querySelector(selector);
          if (nutritionStyleField) break;
        }
      }
      
  // 기본 설정 필드 존재 여부 확인
      
      // 기본 설정값들 업데이트 (다양한 필드명 대응)
      const settingsMap = {
        'serving_size': data.settings.serving_size || data.settings.base_amount || '',
        'serving_size_unit': data.settings.serving_size_unit || 'g',
        'units_per_package': data.settings.units_per_package || data.settings.servings_per_package || '1',
        'nutrition_display_unit': data.settings.nutrition_display_unit || data.settings.style || '',
        'basic_display_type': data.settings.basic_display_type || 'per_100g',
        'parallel_display_type': data.settings.parallel_display_type || 'per_serving'
      };
      
      Object.entries(settingsMap).forEach(([fieldName, value]) => {
        const field = document.querySelector(`input[name="${fieldName}"]`);
        if (field) {
          const oldValue = field.value;
          field.value = value;
        }
      });

      // 표시 기준 설정 필드들 처리
      const basicDisplayTypeField = document.querySelector('input[name="basic_display_type"]');
      if (basicDisplayTypeField && data.settings.basic_display_type) {
        basicDisplayTypeField.value = data.settings.basic_display_type;
      }

      const parallelDisplayTypeField = document.querySelector('input[name="parallel_display_type"]');
      if (parallelDisplayTypeField && data.settings.parallel_display_type) {
        parallelDisplayTypeField.value = data.settings.parallel_display_type;
      }
    }

    // 2. 포맷된 영양성분 데이터를 필드에 저장 - 필드명 통일로 직접 매핑
      const nutritionData = data.formattedData || data.nutritionInputs;
      if (nutritionData) {
  // 포맷된 데이터 처리 시작
      
      let updatedFields = 0;
      let foundFields = [];
      let processedData = {};
      
      // 필드명이 통일되어 직접 매핑 가능
      Object.keys(nutritionData).forEach(fieldName => {
        const valueField = document.querySelector(`input[name="${fieldName}"]`);
        const unitField = document.querySelector(`input[name="${fieldName}_unit"]`);
        
        if (valueField || unitField) {
          foundFields.push(fieldName);
        }
        
        if (nutritionData[fieldName] && (valueField || unitField)) {
          // 처리 가능한 영양소: fieldName
          
          if (valueField) {
            valueField.value = nutritionData[fieldName].value || '';
            // 값 필드 업데이트
            updatedFields++;
          }
          
          if (unitField) {
            unitField.value = nutritionData[fieldName].unit || '';
            // 단위 필드 업데이트
          }
          
          // 처리된 데이터 저장
          processedData[fieldName] = {
            value: nutritionData[fieldName].value || '',
            unit: nutritionData[fieldName].unit || '',
            label: nutritionData[fieldName].label || ''
          };
        }
      });
      
  // 업데이트 완료
    }

    // 3. 영양성분 텍스트 필드에 결과 요약 저장
    const nutritionTextField = document.querySelector('textarea[name="nutrition_text"]');
  // 영양성분 텍스트 필드 존재 여부
    
    if (nutritionTextField && data.formattedData) {
      const nutritionItems = Object.values(data.formattedData)
        .filter(item => item.value !== '' && item.value !== null && item.value !== undefined)
        .map(item => `${item.label} ${item.value}${item.unit}`);
      
      nutritionTextField.value = nutritionItems.join(', ');
      // 영양성분 체크박스 자동 체크
      const nutritionCheckbox = document.getElementById('chk_nutrition_text');
      if (nutritionCheckbox && nutritionItems.length > 0) {
        nutritionCheckbox.checked = true;
        // change 이벤트를 발생시키지 않아 자동 폼 제출 방지
      }
    }
  }

  // 팝업에서 초기화 버튼 클릭 시 부모창 데이터도 초기화
  function handleNutritionDataReset() {
    // 영양성분 데이터 초기화
    const nutritionTextField = document.querySelector('textarea[name="nutrition_text"]');
    if (nutritionTextField) {
      nutritionTextField.value = '';
    }
    
    // 영양성분 체크박스 해제
    const nutritionCheckbox = document.getElementById('chk_nutrition_text');
    if (nutritionCheckbox) {
      nutritionCheckbox.checked = false;
      // change 이벤트를 발생시키지 않아 자동 폼 제출 방지
    }
    
    const fieldNames = [
      'serving_size', 'units_per_package', 'nutrition_style', 'calories', 'natriums', 'carbohydrates', 'sugars',
      'fats', 'trans_fats', 'saturated_fats', 'cholesterols', 'proteins', 'dietary_fiber', 'calcium', 'iron',
      'potassium', 'magnesium', 'zinc', 'phosphorus', 'vitamin_a', 'vitamin_d', 'vitamin_e', 'vitamin_c',
      'vitamin_b1', 'vitamin_b2', 'niacin', 'vitamin_b6', 'folic_acid', 'vitamin_b12', 'selenium',
      'pantothenic_acid', 'biotin', 'iodine', 'vitamin_k', 'copper', 'manganese', 'chromium', 'molybdenum'
    ];

    fieldNames.forEach(fieldName => {
      const valueField = document.querySelector(`input[name="${fieldName}"]`);
      const unitField = document.querySelector(`input[name="${fieldName}_unit"]`);
      if (valueField) valueField.value = '';
      if (unitField) unitField.value = '';
    });
  }

  // 팝업창에서 호출할 함수 (기존 데이터 전달용)
  window.getNutritionDataForPopup = function() {
    const data = collectExistingNutritionData();
    
    // 직접 매핑 - 필드명이 통일되어 변환 로직 제거
    const convertedData = {
      // 모델 필드명 기반으로 설정값 전달
      serving_size: data.serving_size || '100',  // 단위량
      units_per_package: data.units_per_package || '1',  // 포장갯수  
      nutrition_display_unit: data.nutrition_display_unit || 'basic',  // 표시 스타일
      serving_size_unit: data.serving_size_unit || 'g'  // 단위량 단위
    };
    

    
    // 필수 영양성분 (항상 전달)
    const requiredNutrients = ['calories', 'natriums', 'carbohydrates', 'sugars', 'fats', 'trans_fats', 'saturated_fats', 'cholesterols', 'proteins'];
    requiredNutrients.forEach(field => {
      convertedData[field] = data[field] || '';
    });
    
    // 추가 영양성분 (값이 있을 때만 전달) - DB 필드명 사용
    const additionalNutrients = [
      'dietary_fiber', 'calcium', 'iron', 'potassium', 'magnesium', 'zinc', 'phosphorus', 
      'vitamin_a', 'vitamin_d', 'vitamin_e', 'vitamin_c', 'thiamine', 'riboflavin', 
      'niacin', 'vitamin_b6', 'folic_acid', 'vitamin_b12', 'selenium', 'pantothenic_acid', 
      'biotin', 'iodine', 'vitamin_k', 'copper', 'manganese', 'chromium', 'molybdenum'
    ];
    
    const transmittedAdditionalNutrients = [];
    additionalNutrients.forEach(field => {
      const value = data[field];
      

      
      // 셀렉트박스 방식: 실제 값이 있는 경우에만 전달 (빈 값은 전달하지 않음)
      if (value !== undefined && value !== null && value !== '' && (typeof value !== 'string' || value.trim() !== '')) {
        convertedData[field] = value;
        transmittedAdditionalNutrients.push(field);
      }
    });
    

    return convertedData;
  };

  // DOM 로드 완료 시 초기화 함수들 실행
  document.addEventListener('DOMContentLoaded', function() {
    initializeLabelNameSync();
    initializeContentWeightFields();
  });
});

// ==================== 알레르기 관리 기능 (Label Creation) ====================

// 알레르기 데이터 저장소
let selectedIngredientAllergensLabel = new Set();
let selectedCrossContaminationAllergensLabel = new Set();

// 알레르기 모듈 토글
function toggleAllergenModuleLabel() {
    const content = document.getElementById('allergenModuleContentLabel');
    const icon = document.getElementById('allergenModuleToggleIconLabel');
    
    if (content.style.display === 'none') {
        content.style.display = 'flex';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        content.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
}

// 알레르기 자동 감지 (rawmtrl_nm_display 기반)
function detectAllergensLabel() {
    const rawmtrlTextarea = document.getElementById('rawmtrl_nm_display_textarea');
    if (!rawmtrlTextarea) return;
    
    const rawmtrlText = rawmtrlTextarea.value;
    const detectingIndicator = document.getElementById('allergenDetectingIndicatorLabel');
    
    // 로딩 인디케이터 표시
    if (detectingIndicator) {
        detectingIndicator.style.display = 'flex';
    }
    
    // 약간의 지연 후 실행하여 로딩 효과 표시
    setTimeout(() => {
        if (!rawmtrlText || rawmtrlText.trim() === '') {
            if (detectingIndicator) {
                detectingIndicator.style.display = 'none';
            }
            return;
        }
    
    // constants.js의 ALLERGEN_KEYWORDS 사용 (home_demo.js와 동일한 키워드)
    const allergenKeywords = window.allergenKeywords || window.ALLERGEN_KEYWORDS || {};
    
    // 감지된 알레르기
    const detectedAllergens = new Set();
    
    // 각 알레르기 그룹의 키워드로 검색 (home_demo.js와 동일한 로직)
    for (const [allergen, keywords] of Object.entries(allergenKeywords)) {
        for (const keyword of keywords) {
            let found = false;
            
            // 1글자 키워드는 단어 경계 체크 (오탐 방지)
            if (keyword.length === 1) {
                const regex = new RegExp(`[\\s,():]${keyword}[\\s,():]|^${keyword}[\\s,():]|[\\s,():]${keyword}$|^${keyword}$`, 'gi');
                if (regex.test(rawmtrlText)) {
                    found = true;
                }
            } else {
                // 2글자 이상은 포함 여부만 체크
                if (rawmtrlText.toLowerCase().includes(keyword.toLowerCase())) {
                    found = true;
                }
            }
            
            if (found) {
                detectedAllergens.add(allergen);
                break;
            }
        }
    }
    
    // 기존 선택된 알레르기와 병합
    detectedAllergens.forEach(a => selectedIngredientAllergensLabel.add(a));
    
    // UI 업데이트
    updateAllergenTagsLabel();
    
    // 로딩 인디케이터 숨기기
    if (detectingIndicator) {
        detectingIndicator.style.display = 'none';
    }
    }, 300); // 300ms 지연
}

// 수동 감지 트리거
function manualDetectAllergensLabel() {
    selectedIngredientAllergensLabel.clear();
    detectAllergensLabel();
    updateAllergenButtonStatesLabel();
}

// 알레르기 태그 추가
function addAllergenTagLabel(allergen) {
    selectedIngredientAllergensLabel.add(allergen);
    updateAllergenTagsLabel();
}

// 알레르기 태그 제거
function removeAllergenTagLabel(allergen) {
    selectedIngredientAllergensLabel.delete(allergen);
    updateAllergenTagsLabel();
}

// 알레르기 태그 UI 업데이트
function updateAllergenTagsLabel() {
    const container = document.getElementById('detectedAllergensLabel');
    const summary = document.getElementById('allergenSummaryLabel');
    
    if (!container) return;
    
    if (selectedIngredientAllergensLabel.size === 0) {
        container.innerHTML = '<span class="text-muted"><i class="fas fa-info-circle me-1"></i>원재료명(최종표시)을 입력하면 자동으로 감지됩니다</span>';
        if (summary) {
            summary.innerHTML = '<span class="text-muted" style="font-size: 0.75rem;">원재료명을 입력하면 자동 감지됩니다</span>';
        }
    } else {
        container.innerHTML = '';
        selectedIngredientAllergensLabel.forEach(allergen => {
            const tag = document.createElement('span');
            tag.className = 'badge bg-danger me-1 mb-1';
            tag.style.fontSize = '0.8rem';
            tag.style.padding = '0.3em 0.5em';
            tag.innerHTML = `${allergen} <i class="fas fa-times ms-1" style="cursor: pointer;" onclick="removeAllergenTagLabel('${allergen}')"></i>`;
            container.appendChild(tag);
        });
        
        // 헤더 요약에도 모든 배지 표시 (접었을 때 보이는 부분)
        if (summary) {
            summary.innerHTML = '';
            selectedIngredientAllergensLabel.forEach(allergen => {
                const tag = document.createElement('span');
                tag.className = 'badge bg-danger me-1 mb-1';
                tag.style.fontSize = '0.85rem';
                tag.style.padding = '0.35em 0.6em';
                tag.textContent = allergen;
                summary.appendChild(tag);
            });
        }
    }
    
    // hidden input 업데이트
    document.getElementById('selected_ingredient_allergens_label').value = Array.from(selectedIngredientAllergensLabel).join(',');
    
    // 제조시설 혼입 버튼 상태 업데이트 (중복 방지)
    updateAllergenButtonStatesLabel();
}

// 알레르기 버튼 상태 업데이트 (제조시설 혼입 버튼 비활성화)
function updateAllergenButtonStatesLabel() {
    // 직접 추가 버튼 상태 업데이트
    document.querySelectorAll('.quick-allergen-btn-label').forEach(button => {
        const allergen = button.dataset.allergen;
        if (selectedIngredientAllergensLabel.has(allergen)) {
            button.classList.remove('btn-outline-secondary');
            button.classList.add('btn-info');
        } else {
            button.classList.remove('btn-info');
            button.classList.add('btn-outline-secondary');
        }
    });
    
    // 제조시설 혼입 우려물질 버튼 비활성화 (선택된 알레르기 항목)
    document.querySelectorAll('.allergen-toggle-label').forEach(button => {
        const allergen = button.dataset.allergen;
        if (selectedIngredientAllergensLabel.has(allergen)) {
            // 원재료에 이미 사용된 경우 비활성화 및 선택 해제
            button.disabled = true;
            button.classList.remove('btn-warning');
            button.classList.add('btn-outline-secondary', 'opacity-50');
            button.title = '원재료로 사용되어 제조시설 혼입 경고에 추가할 수 없습니다';
            // 선택된 상태에서 제거
            selectedCrossContaminationAllergensLabel.delete(allergen);
        } else {
            // 활성화
            button.disabled = false;
            button.classList.remove('opacity-50');
            button.title = '';
        }
    });
}

// 제조시설 혼입 알레르기 토글
function toggleAllergenLabel(allergen) {
    // 원재료에 이미 사용된 알레르기는 토글 불가
    if (selectedIngredientAllergensLabel.has(allergen)) {
        return;
    }
    
    if (selectedCrossContaminationAllergensLabel.has(allergen)) {
        selectedCrossContaminationAllergensLabel.delete(allergen);
    } else {
        selectedCrossContaminationAllergensLabel.add(allergen);
    }
    updateCrossContaminationUILabel();
}

// 모든 제조시설 알레르기 선택/해제
function toggleAllAllergensLabel() {
    const btn = document.getElementById('toggleAllAllergensLabelBtn');
    const allAllergens = ['알류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우', '돼지고기', '복숭아', '토마토', '아황산류', '호두', '잣', '닭고기', '쇠고기', '오징어', '조개류'];
    
    if (selectedCrossContaminationAllergensLabel.size === allAllergens.length) {
        selectedCrossContaminationAllergensLabel.clear();
    } else {
        allAllergens.forEach(a => selectedCrossContaminationAllergensLabel.add(a));
    }
    
    updateCrossContaminationUILabel();
}

// 제조시설 혼입 UI 업데이트
function updateCrossContaminationUILabel() {
    const buttons = document.querySelectorAll('.allergen-toggle-label');
    buttons.forEach(btn => {
        const allergen = btn.dataset.allergen;
        if (selectedCrossContaminationAllergensLabel.has(allergen)) {
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('btn-warning');
        } else {
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-outline-secondary');
        }
    });
    
    // 전체 선택 버튼 텍스트 업데이트
    const btn = document.getElementById('toggleAllAllergensLabelBtn');
    const allAllergens = ['알류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게', '새우', '돼지고기', '복숭아', '토마토', '아황산류', '호두', '잣', '닭고기', '쇠고기', '오징어', '조개류'];
    if (selectedCrossContaminationAllergensLabel.size === allAllergens.length) {
        btn.innerHTML = '<i class="fas fa-times me-1"></i>전체 해제';
    } else {
        btn.innerHTML = '<i class="fas fa-check-double me-1"></i>전체 선택';
    }
    
    // 미리보기 업데이트
    updateCrossContaminationPreviewLabel();
}

// 혼입 경고 문구 미리보기 업데이트
function updateCrossContaminationPreviewLabel() {
    const preview = document.getElementById('crossContaminationPreviewLabel');
    const text = document.getElementById('crossContaminationTextLabel');
    
    if (selectedCrossContaminationAllergensLabel.size === 0) {
        preview.style.display = 'none';
    } else {
        const allergenList = Array.from(selectedCrossContaminationAllergensLabel).join(', ');
        text.textContent = `이 제품은 ${allergenList}를 사용한 제품과 같은 제조시설에서 제조하고 있습니다.`;
        preview.style.display = 'block';
    }
}

// 주의사항에 혼입 경고 추가
function toggleAllergenWarningLabel() {
    if (selectedCrossContaminationAllergensLabel.size === 0) {
        alert('먼저 제조시설 혼입 우려 물질을 선택해주세요.');
        return;
    }
    
    const cautionsTextarea = document.querySelector('textarea[name="cautions"]');
    if (!cautionsTextarea) return;
    
    const allergenList = Array.from(selectedCrossContaminationAllergensLabel).join(', ');
    const warningText = `이 제품은 ${allergenList}를 사용한 제품과 같은 제조시설에서 제조하고 있습니다.`;
    
    let currentCautions = cautionsTextarea.value.trim();
    
    // 이미 있는지 확인
    if (currentCautions.includes(warningText)) {
        alert('이미 주의사항에 추가되어 있습니다.');
        return;
    }
    
    // 추가
    if (currentCautions === '') {
        cautionsTextarea.value = warningText;
    } else {
        cautionsTextarea.value = currentCautions + '\n' + warningText;
    }
    
    alert('주의사항에 추가되었습니다.');
}

// 알레르기 관리 초기화
function initializeAllergenManagementLabel() {
    // 직접 추가 버튼 이벤트
    document.querySelectorAll('.quick-allergen-btn-label').forEach(btn => {
        btn.addEventListener('click', function() {
            addAllergenTagLabel(this.dataset.allergen);
        });
    });
    
    // 제조시설 혼입 버튼 이벤트
    document.querySelectorAll('.allergen-toggle-label').forEach(btn => {
        btn.addEventListener('click', function() {
            toggleAllergenLabel(this.dataset.allergen);
        });
    });
    
    // rawmtrl_nm_display 변경 시 자동 감지
    const rawmtrlTextarea = document.getElementById('rawmtrl_nm_display_textarea');
    if (rawmtrlTextarea) {
        rawmtrlTextarea.addEventListener('input', debounce(function() {
            detectAllergensLabel();
        }, 800));
    }
    
    // 저장된 알레르기 데이터 로드
    loadSavedAllergensLabel();
}

// 저장된 알레르기 데이터 로드
function loadSavedAllergensLabel() {
    // 원재료 사용 알레르기 로드 (allergens 필드)
    const ingredientInput = document.getElementById('selected_ingredient_allergens_label');
    if (ingredientInput && ingredientInput.value) {
        const allergens = ingredientInput.value.split(',').filter(a => a.trim() !== '');
        allergens.forEach(a => selectedIngredientAllergensLabel.add(a.trim()));
        updateAllergenTagsLabel();
    }
    
    // 제조시설 혼입 알레르기 로드 (주의사항 텍스트에서 파싱)
    const cautionsTextarea = document.querySelector('textarea[name="cautions"]');
    if (cautionsTextarea && cautionsTextarea.value) {
        const cautionsText = cautionsTextarea.value;
        // "이 제품은 ...를 사용한 제품과 같은 제조시설에서 제조하고 있습니다." 패턴 찾기 (※ 기호 제거)
        const pattern = /이\s*제품은\s+([^를]+)를\s*사용한\s*제품과\s*같은\s*제조시설에서\s*제조하고\s*있습니다\.?/;
        const match = cautionsText.match(pattern);
        
        if (match && match[1]) {
            // 쉼표 또는 "와/과"로 분리된 알레르기 목록 추출
            const allergenText = match[1].trim();
            const allergens = allergenText.split(/[,،、]/).map(a => a.trim()).filter(a => a !== '');
            
            allergens.forEach(a => selectedCrossContaminationAllergensLabel.add(a));
            updateCrossContaminationUILabel();
        }
    }
}

// 디바운스 유틸리티
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initializeAllergenManagementLabel();
});
