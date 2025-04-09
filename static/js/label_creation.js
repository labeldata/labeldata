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
      console.log('장기보존식품 설정:', this.value);
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
      console.log('제조방법 설정:', this.value);
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
    if (!this.checked) {
      // 체크 해제 시 조건 입력 필드 비움
      $('input[name="processing_condition"]').val('');
      $('#hidden_processing_condition').val('');
    }
  });

  // 조건 텍스트 입력 시 hidden 필드 업데이트
  $('input[name="processing_condition"]').on('input', function() {
    $('#hidden_processing_condition').val(this.value);
    console.log('조건 설정:', this.value);
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

  // 조건 상세
  const manufacturingOther = $("input[name='sterilization_other_detail']").val();
  if (manufacturingOther) summaries.push(manufacturingOther);

  // ✅ 변경된 조건: 가열하여 섭취하는 냉동식품 + 제조방법 모두 미체크 => 비살균제품
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
// nutrition_calculator.js에서 전달한 영양성분 데이터를 처리하는 함수
function updateNutritionFields(data) {
  // hidden 필드들에 영양성분 데이터 설정
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
    
    // 각 필드에 값 설정
    Object.keys(fieldMap).forEach(key => {
      const field = document.querySelector(`input[name="${fieldMap[key]}"]`);
      if (field && data[key] !== undefined) {
        field.value = data[key];
      }
    });
    
    // 영양성분 체크박스 자동 선택 부분 제거 (주석 처리)
    // const nutritionCheckbox = document.getElementById("chk_calories");
    // if (nutritionCheckbox) {
    //   nutritionCheckbox.checked = true;
    // }
  }
}

// 영양성분 계산기 팝업 함수
function openNutritionCalculator() {
    // 현재 라벨 ID
    const labelId = document.getElementById('label_id').value;
    
    // 현재 라벨 ID를 쿼리 파라미터로 전달
    const url = `/label/nutrition-calculator-popup/?label_id=${labelId}`;
    
    // 팝업 창 열기
    const popup = window.open(url, 'NutritionCalculator', 'width=1100,height=800,scrollbars=yes');
  }

// ------------------ 식품유형 대분류-소분류 연동 기능 ------------------
// initFoodTypeFiltering 함수 수정 - 페이지 로드 시 초기화
function initFoodTypeFiltering() {
  // 초기 값 설정
  const initialFoodGroup = $('#food_group').val();
  const initialFoodType = $('#food_type').val();
  
  console.log(`페이지 로드 시 초기값 - 대분류: ${initialFoodGroup}, 소분류: ${initialFoodType}`);
  
  // hidden 필드에 초기값 설정
  $('#hidden_food_group').val(initialFoodGroup);
  $('#hidden_food_type').val(initialFoodType);
  
  // 소분류가 있지만 대분류가 선택되지 않은 경우 대분류를 자동으로 설정
  if (initialFoodType && (!initialFoodGroup || initialFoodGroup === '')) {
    console.log(`소분류는 있지만 대분류가 없음. 소분류: ${initialFoodType}`);
    
    // 소분류에 대응하는 대분류 찾기
    const selectedOption = $('#food_type option:selected');
    const group = selectedOption.data('group');
    
    if (group) {
      console.log(`소분류 ${initialFoodType}에 대한 대분류 찾음: ${group}`);
      $('#food_group').val(group);
      $('#hidden_food_group').val(group);
    } else {
      // 대분류 정보가 없는 경우 서버에서 조회
      console.log('대분류 정보가 없어 서버에서 조회 시도');
      fetch(`/label/get-food-group/?food_type=${encodeURIComponent(initialFoodType)}`)
        .then(response => response.json())
        .then(data => {
          if (data.success && data.food_group) {
            console.log(`서버에서 대분류 정보 수신: ${data.food_group}`);
            $('#food_group').val(data.food_group);
            $('#hidden_food_group').val(data.food_group);
          }
        })
        .catch(error => console.error('대분류 조회 중 오류:', error));
    }
  }
  
  // 대분류가 있지만 소분류가 선택되지 않은 경우 소분류 목록 필터링
  if (initialFoodGroup && (!initialFoodType || initialFoodType === '')) {
    console.log(`대분류는 있지만 소분류가 없음. 대분류: ${initialFoodGroup}`);
    
    // 대분류에 해당하는 소분류 목록 로드
    fetch(`/label/food-types-by-group/?group=${encodeURIComponent(initialFoodGroup)}`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          console.log(`대분류 ${initialFoodGroup}에 대한 소분류 ${data.food_types.length}개 로드됨`);
          
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
  
  // 페이지 로드 시 이미 선택된 식품유형에 대해 체크박스 설정 적용
  if (initialFoodType) {
    console.log(`초기 소분류 ${initialFoodType}에 대한 설정 적용`);
    updateCheckboxesByFoodType(initialFoodType)
      .catch(err => console.error('초기 체크박스 설정 중 오류:', err));
  }
}

// ------------------ 식품유형에 따른 체크박스 설정 ------------------
// updateCheckboxesByFoodType 함수 수정 - 소비기한 드롭다운 옵션 업데이트 부분 추가
function updateCheckboxesByFoodType(foodType) {
  if (!foodType) return Promise.resolve();
  
  console.log(`식품유형 ${foodType}에 따른 설정 시작`);
  
  return fetch(`/label/food-type-settings/?food_type=${encodeURIComponent(foodType)}`)
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        console.log('서버에서 받은 설정:', data.settings);
        const settings = data.settings;
        
        const fieldMappings = {
          'prdlst_dcnm': 'chk_prdlst_dcnm',
          'rawmtrl_nm': 'chk_rawmtrl_nm_display',
          'nutritions': 'chk_calories'
        };
        
        // Y는 체크, N은 체크 해제, D는 필드 비활성화
        Object.keys(settings).forEach(field => {
          const value = settings[field];
          const checkboxId = fieldMappings[field] || `chk_${field}`;
          const checkbox = document.getElementById(checkboxId);
          
          if (checkbox) {
            console.log(`필드 ${field} (${checkboxId}) 값: ${value}`); 
            
            if (value === 'Y') {
              checkbox.checked = true;
              checkbox.disabled = false;
              checkbox.dataset.forcedDisabled = "false"; // 강제 비활성화 아님
            } else if (value === 'N') {
              checkbox.checked = false;
              checkbox.disabled = false;
              checkbox.dataset.forcedDisabled = "false"; // 강제 비활성화 아님
            } else if (value === 'D') {
              checkbox.checked = false;
              checkbox.disabled = true;
              checkbox.dataset.forcedDisabled = "true"; // 강제 비활성화
            }
            
            // change 이벤트 발생시켜 관련 필드 상태 갱신
            checkbox.dispatchEvent(new Event('change'));
          }
          
          // 소비기한 드롭다운 필터링
          if (field === 'pog_daycnt' && settings.pog_daycnt) {
            updateDateDropdown(settings.pog_daycnt);
          }
        });
        
        // 소비기한 드롭다운 옵션 업데이트
        if (settings.pog_daycnt_options !== undefined) {
          console.log('소비기한 옵션 업데이트:', settings.pog_daycnt_options);
          updateDateDropdownOptions(settings.pog_daycnt_options);
        }
        
        // 관련 규정 정보 설정
        if (settings.relevant_regulations !== undefined) {
          console.log('관련 규정 정보 업데이트');
          const regulationsTextarea = document.querySelector('textarea[name="related_regulations"]');
          if (regulationsTextarea) {
            regulationsTextarea.value = settings.relevant_regulations;
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

// 소비기한 드롭다운 필터링 함수 추가
function updateDateDropdown(value) {
  const dateOptions = document.querySelector('select[name="date_option"]');
  if (!dateOptions) return;
  
  // 모든 옵션 활성화 초기화
  Array.from(dateOptions.options).forEach(option => {
    option.disabled = false;
  });
  
  // 값에 따라 필터링
  if (value === 'D') {
    // 모든 옵션 비활성화
    Array.from(dateOptions.options).forEach(option => {
      option.disabled = true;
    });
    dateOptions.value = '';
    dateOptions.disabled = true;
  } else if (value === 'Y') {
    // 모든 옵션 활성화
    dateOptions.disabled = false;
  }
}

// 소비기한 드롭다운 옵션 업데이트 함수 수정
function updateDateDropdownOptions(options) {
  const dateOptions = document.querySelector('select[name="date_option"]');
  if (!dateOptions) {
    console.error('소비기한 드롭다운을 찾을 수 없습니다.');
    return;
  }
  
  console.log('소비기한 드롭다운 옵션 업데이트 시작:', options);
  
  // 기존 선택된 값 저장
  const currentValue = dateOptions.value;
  console.log('현재 선택된 값:', currentValue);
  
  // 이전 옵션 저장 (최초 1회만)
  if (!dateOptions.dataset.originalOptions) {
    dateOptions.dataset.originalOptions = dateOptions.innerHTML;
  }
  
  // 값이 있고 유효한 배열이면 드롭다운 옵션 교체
  if (options && Array.isArray(options) && options.length > 0) {
    dateOptions.innerHTML = ''; // 기존 옵션 모두 제거
    
    options.forEach(option => {
      if (!option) return; // 빈 옵션은 건너뜀
      
      const optionElement = document.createElement('option');
      optionElement.value = option;
      optionElement.textContent = option;
      dateOptions.appendChild(optionElement);
    });
    
    // 이전에 선택한 값이 새 옵션 목록에 있으면 그 값을 선택, 없으면 첫 번째 옵션 선택
    if (options.includes(currentValue)) {
      dateOptions.value = currentValue;
    } else if (options.length > 0) {
      dateOptions.value = options[0];
    }
    
    console.log('소비기한 드롭다운 업데이트 완료. 새 값:', dateOptions.value);
  } else {
    // 옵션이 없거나 유효하지 않은 경우 원래 옵션으로 복원
    console.log('유효한 소비기한 옵션이 없습니다. 기본 옵션으로 복원');
    
    if (dateOptions.dataset.originalOptions) {
      dateOptions.innerHTML = dateOptions.dataset.originalOptions;
    } else {
      // 기본 옵션 설정
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
  
  // 드롭다운 활성화
  dateOptions.disabled = false;
}

// 체크박스와 관련 입력 필드 활성화/비활성화 함수 완전 재작성
// 체크박스-필드 토글 함수 수정에서 원재료명(참고) 체크박스 특별 처리 추가
function initCheckboxFieldToggle() {
  console.log('체크박스-필드 매핑 초기화');
  
  // 체크박스 목록
  const checkboxes = document.querySelectorAll('input[type="checkbox"][id^="chk_"]');
  
  // 각 체크박스에 이벤트 핸들러 연결
  checkboxes.forEach(function(checkbox) {
    // 이벤트 핸들러 등록 표시
    if (checkbox.getAttribute('data-initialized') === 'true') {
      return;
    }
    
    checkbox.setAttribute('data-initialized', 'true');
    
    // 체크박스 ID에서 필드 이름 추출
    const fieldName = checkbox.id.replace('chk_', '');
    console.log(`체크박스 설정 중: ${checkbox.id} -> ${fieldName}`);
    
    // 원재료명(참고) 체크박스는 항상 비활성화
    if (fieldName === 'rawmtrl_nm') {
      // 체크박스와 텍스트영역 모두 비활성화
      checkbox.disabled = true;
      const textarea = document.querySelector('textarea[name="rawmtrl_nm"]');
      if (textarea) {
        textarea.disabled = true;
        textarea.classList.add('disabled-textarea');
      }
      return; // 이 체크박스에 대한 추가 처리 중단
    }
    
    // 나머지 코드는 그대로 유지...
    let relatedFields = findRelatedFields(fieldName);
    
    if (relatedFields.length > 0) {
      // 체크박스 변경 이벤트 핸들러
      checkbox.addEventListener('change', function() {
        console.log(`체크박스 ${this.id} 상태 변경: ${this.checked}`);
        
        // 체크박스 상태에 따라 입력 필드 활성화/비활성화
        relatedFields.forEach(function(field) {
          // 강제 비활성화된 체크박스인 경우에만 필드를 비활성화
          if (checkbox.dataset.forcedDisabled === "true") {
            field.disabled = true;
            field.classList.add('disabled-textarea');
          } else {
            // 강제 비활성화가 아닌 경우, 체크 여부와 관계없이 항상 활성화
            field.disabled = false;
            field.classList.remove('disabled-textarea');
          }
          
          console.log(`필드 ${field.name || field.id} 상태: disabled=${field.disabled}, forcedDisabled=${checkbox.dataset.forcedDisabled}`);
        });
      });
      
      // 초기 상태 설정
      relatedFields.forEach(function(field) {
        // 체크박스가 강제 비활성화된 경우에만 필드를 비활성화
        if (checkbox.dataset.forcedDisabled === "true") {
          field.disabled = true;
          field.classList.add('disabled-textarea');
        } else {
          // 강제 비활성화가 아닌 경우, 체크 여부와 관계없이 항상 활성화
          field.disabled = false;
          field.classList.remove('disabled-textarea');
        }
      });
    } else {
      console.warn(`체크박스 ${checkbox.id}에 대한 관련 필드를 찾을 수 없음`);
    }
  });
  
  console.log('체크박스-필드 매핑 초기화 완료');
}

// 체크박스 필드명에 해당하는 입력 필드들을 찾는 함수 개선
function findRelatedFields(fieldName) {
  // 체크박스 ID와 관련 입력 필드의 매핑 테이블
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
  
  // 매핑 테이블에서 필드 이름에 해당하는 선택자 가져오기
  const selectors = fieldMappings[fieldName] || [];
  const fields = [];
  
  // 각 선택자에 해당하는 HTML 요소 찾기
  selectors.forEach(function(selector) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(function(el) {
      fields.push(el);
    });
  });
  
  return fields;
}

// 기본 체크박스 값 설정 함수 수정 (기존 함수 교체)
function setDefaultCheckboxes() {
  // 항상 설정해야 하는 기본 체크박스 값
  const defaultChecked = {
    'chk_prdlst_nm': true,          // 제품명 - 체크함
    'chk_content_weight': true,      // 내용량 - 체크함
    'chk_manufacturer_info': true,   // 제조원 소재지 - 체크함
    'chk_date_info': true            // 소비기한 - 체크함
  };
  
  const defaultUnchecked = {
    'chk_label_nm': false,           // 라벨명 - 체크 안함
    'chk_ingredients_info': false,   // 성분명 및 함량 - 체크 안함
    'chk_distributor_address': false,// 유통전문 판매원 - 체크 안함
    'chk_repacker_address': false,   // 소분원 - 체크 안함
    'chk_importer_address': false,   // 수입원 - 체크 안함
    'chk_rawmtrl_nm': false          // 원재료명(참고) - 체크 안함
  };
  
  // 새 라벨 생성인 경우에만 적용
  if (!$('#label_id').val() || $('#label_id').val() === '') {
    console.log("새 라벨 생성 시 기본 체크박스 설정 적용");
    
    // 체크해야 하는 체크박스 처리
    Object.keys(defaultChecked).forEach(checkboxId => {
      const checkbox = document.getElementById(checkboxId);
      if (checkbox && !checkbox.disabled) {
        checkbox.checked = defaultChecked[checkboxId];
        // change 이벤트 발생시켜 관련 필드 상태 갱신
        checkbox.dispatchEvent(new Event('change'));
      }
    });
    
    // 체크 해제해야 하는 체크박스 처리
    Object.keys(defaultUnchecked).forEach(checkboxId => {
      const checkbox = document.getElementById(checkboxId);
      if (checkbox && !checkbox.disabled) {
        checkbox.checked = defaultUnchecked[checkboxId];
        // change 이벤트 발생시켜 관련 필드 상태 갱신
        checkbox.dispatchEvent(new Event('change'));
      }
    });
  }
}

// 폼 제출 이벤트에서 체크박스 값을 Y/N으로 변환
function prepareFormData() {
  // 체크박스 값 처리
  $('input[type="checkbox"]').each(function() {
    const checkboxName = $(this).attr('name');
    if (checkboxName && checkboxName.startsWith('chk_')) {
      // 체크박스가 체크되어 있으면 'Y', 아니면 'N'으로 설정
      const value = $(this).prop('checked') ? 'Y' : 'N';
      
      // hidden 필드 찾기 또는 생성
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
      
      console.log(`체크박스 ${checkboxName} 값 설정: ${value}`);
    }
  });
  
  // 장기보존식품, 제조방법, 조건 값 확인 및 설정
  const preservationType = $('.grp-long-shelf:checked').val() || '';
  const processingMethod = $('.grp-sterilization:checked').not('#chk_sterilization_other').val() || '';
  const processingCondition = $('input[name="processing_condition"]').val() || '';
  
  $('#hidden_preservation_type').val(preservationType);
  $('#hidden_processing_method').val(processingMethod);
  $('#hidden_processing_condition').val(processingCondition);
  
  console.log('폼 제출 준비:', {
    preservationType,
    processingMethod,
    processingCondition
  });
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

// Document Ready 이벤트 핸들러 정리 (중복 제거)
$(document).ready(function() {
  // 체크박스 그룹 초기화
  initCheckBoxGroups();
  
  // 요약 업데이트
  updateSummary();
  
  // 이벤트 리스너 연결
  $('.select2-food-type, input[type="checkbox"], input[name="sterilization_other_detail"]')
    .on('change input', updateSummary);
  
  // 토글 버튼 초기화
  initToggleButtons();
  
  // 식품유형 필터링 초기화
  initFoodTypeFiltering();
  
  // Select2 컴포넌트 초기화
  initSelect2Components();
  
  // 식품유형 소분류 선택 시 대분류 자동 설정 및 관련 규정 정보 업데이트
  $('#food_type').off('change').on('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    if (selectedOption && selectedOption.value) {
      const group = selectedOption.dataset.group;
      console.log(`소분류 선택: ${selectedOption.value}, 대분류: ${group}`);
      
      if (group) {
        // 대분류 값을 숨겨진 대분류 select와 hidden 필드에 설정
        $('#food_group').val(group);
        $('#hidden_food_group').val(group);
        console.log(`대분류 자동 설정: ${group}`);
      } else if (!group) {
        // 대분류 정보가 없는 경우 서버에서 조회
        console.log('대분류 정보 없음, 서버에서 조회 시도');
        fetch(`/label/get-food-group/?food_type=${encodeURIComponent(selectedOption.value)}`)
          .then(response => response.json())
          .then(data => {
            if (data.success && data.food_group) {
              console.log(`서버에서 대분류 정보 수신: ${data.food_group}`);
              $('#food_group').val(data.food_group);
              $('#hidden_food_group').val(data.food_group);
              
              // 현재 선택된 소분류에 대분류 정보 저장
              selectedOption.dataset.group = data.food_group;
            }
          })
          .catch(error => console.error('대분류 조회 중 오류:', error));
      }
      
      // 식품유형에 따른 설정 업데이트 (체크박스, 소비기한, 관련 규정 등)
      updateCheckboxesByFoodType(selectedOption.value);
      updateSummary();
    }
  });
  
  // 대분류 선택 시 소분류 필터링 코드 개선
  $('#food_group').off('change').on('change', function() {
    const selectedGroup = this.value;
    console.log(`대분류 선택: ${selectedGroup}`);
    
    // hidden 필드에 값 설정
    $('#hidden_food_group').val(selectedGroup);
    
    // 소분류 드롭다운 초기화
    const foodTypeSelect = $('#food_type');
    
    // 현재 선택된 소분류 값 저장
    const currentFoodType = $('#food_type').val();
    
    // 소분류 비우고 기본 옵션 추가
    foodTypeSelect.empty().append('<option value="">소분류</option>');
    
    if (!selectedGroup) {
      console.log('대분류 미선택, 모든 소분류 표시');
      fetch('/label/food-types-by-group/')
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            data.food_types.forEach(item => {
              const option = new Option(item.food_type, item.food_type);
              option.dataset.group = item.food_group;
              foodTypeSelect.append(option);
            });
            // select2 업데이트 트리거
            foodTypeSelect.trigger('change');
          }
        })
        .catch(error => console.error('소분류 데이터 로딩 중 오류:', error));
    } else {
      console.log(`선택된 대분류의 소분류 로드: ${selectedGroup}`);
      fetch(`/label/food-types-by-group/?group=${encodeURIComponent(selectedGroup)}`)
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            data.food_types.forEach(item => {
              const option = new Option(item.food_type, item.food_type);
              option.dataset.group = item.food_group;
              foodTypeSelect.append(option);
            });
            // select2 업데이트 트리거
            foodTypeSelect.trigger('change');
          }
        })
        .catch(error => console.error('소분류 데이터 로딩 중 오류:', error));
    }
    
    updateSummary();
  });
  
  // 체크박스-필드 토글 초기화
  initCheckboxFieldToggle();
  
  // 폼 제출 이벤트 핸들러 - 중복 없이 한 번만 정의
  $("#labelForm").off('submit').on('submit', function() {
    console.log("폼 제출 시작: 데이터 처리");
    
    // 식품유형 값 최종 확인 및 설정
    const selectedFoodGroup = $('#food_group').val();
    const selectedFoodType = $('#food_type').val();
    
    $('#hidden_food_group').val(selectedFoodGroup);
    $('#hidden_food_type').val(selectedFoodType);
    
    // 체크박스 값 처리
    prepareFormData();
    
    console.log("폼 제출 준비 완료");
    return true; // 폼 제출 계속 진행
  });
  
  // 식품유형 값 동기화
  $('#food_group').on('change', function() {
    const selectedValue = $(this).val();
    $('#hidden_food_group').val(selectedValue);
    console.log(`대분류 변경: ${selectedValue}, hidden 값: ${$('#hidden_food_group').val()}`);
  });
  
  $('#food_type').on('change', function() {
    const selectedValue = $(this).val();
    $('#hidden_food_type').val(selectedValue);
    console.log(`소분류 변경: ${selectedValue}, hidden 값: ${$('#hidden_food_type').val()}`);
    
    if (selectedValue) {
      // 식품유형에 따른 체크박스 설정 적용
      updateCheckboxesByFoodType(selectedValue)
        .catch(err => console.error('체크박스 설정 적용 중 오류:', err));
    }
  });
  
  // 초기 값 설정
  $('#hidden_food_group').val($('#food_group').val());
  $('#hidden_food_type').val($('#food_type').val());
  
  // 페이지 로드 시 이미 선택된 식품유형에 대해 체크박스 설정 적용
  const selectedFoodType = $('#food_type').val();
  if (selectedFoodType) {
    updateCheckboxesByFoodType(selectedFoodType)
      .catch(err => console.error('초기 체크박스 설정 중 오류:', err));
  } else {
    // 식품유형이 선택되지 않은 경우 기본 체크박스 설정 적용
    setDefaultCheckboxes();
    // 체크박스 상태에 따라 필드 활성화/비활성화 초기화
    document.querySelectorAll('input[type="checkbox"][id^="chk_"]').forEach(function(checkbox) {
      checkbox.dispatchEvent(new Event('change'));
    });
  }

  console.log("문서 로딩 완료 및 초기화 작업 완료");
});


function openPhrasePopup() {
  const width = 1100;
  const height = 800;
  const left = (screen.width - width) / 2;
  const top = (screen.height - height) / 2;
  
  // URL을 phrase_popup으로 변경
  window.open('/label/phrases/', 'phrasePopup', 
      `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`);
}

// 버튼에 이벤트 핸들러 연결
document.addEventListener('DOMContentLoaded', function() {
  // 주의사항과 기타표시사항의 버튼을 모두 선택
  const phraseButtons = document.querySelectorAll('[onclick="openPhrasePopup()"]');
  phraseButtons.forEach(button => {
      button.onclick = function() {
          openPhrasePopup();
      };
  });
});