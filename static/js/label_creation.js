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
    } else {
      $(this).data('alreadyChecked', false);
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
    } else {
      $(this).data('alreadyChecked', false);
    }

    // 조건 체크박스 활성화 여부
    if ($("#chk_sanitized").is(":checked") || $("#chk_aseptic").is(":checked")) {
      $("#chk_sterilization_other").prop("disabled", false);
    } else {
      $("#chk_sterilization_other").prop("disabled", true).prop("checked", false);
    }
    updateSummary(); // 요약 갱신
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
function initFoodTypeFiltering() {
  // DOM 요소 가져오기
  const foodGroupSelect = document.getElementById('food_group');
  const foodTypeSelect = document.getElementById('food_type');
  
  // 초기 소분류 옵션 전체 저장 (필터링 리셋용)
  const allFoodTypeOptions = Array.from(foodTypeSelect.options).map(option => ({
    value: option.value,
    text: option.text,
    group: option.dataset.group || ''  // data-group 속성 추출
  }));

  // 1. 대분류 선택 시 소분류 필터링
  foodGroupSelect.addEventListener('change', function() {
    const selectedGroup = this.value;
    
    // 소분류 목록 초기화
    foodTypeSelect.innerHTML = '<option value="">소분류</option>';
    
    if (!selectedGroup) {
      // 대분류 선택하지 않은 경우 모든 소분류 표시
      allFoodTypeOptions.forEach(option => {
        if (option.value) { // 빈 옵션은 제외
          const newOption = document.createElement('option');
          newOption.value = option.value;
          newOption.textContent = option.text;
          newOption.dataset.group = option.group;
          foodTypeSelect.appendChild(newOption);
        }
      });
    } else {
      // 선택된 대분류에 해당하는 소분류만 필터링
      fetch(`/label/food-types-by-group/?group=${encodeURIComponent(selectedGroup)}`)
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            data.food_types.forEach(item => {
              const option = document.createElement('option');
              option.value = item.food_type;
              option.textContent = item.food_type;
              option.dataset.group = item.food_group;
              foodTypeSelect.appendChild(option);
            });
          }
        })
        .catch(error => {
          console.error('소분류 데이터 로딩 중 오류:', error);
          // 에러 발생 시 로컬 데이터로 대체
          const filteredOptions = allFoodTypeOptions.filter(
            option => option.group === selectedGroup || !option.group
          );
          filteredOptions.forEach(option => {
            if (option.value) {
              const newOption = document.createElement('option');
              newOption.value = option.value;
              newOption.textContent = option.text;
              newOption.dataset.group = option.group;
              foodTypeSelect.appendChild(newOption);
            }
          });
        });
    }
  });
  
  // 2. 소분류 선택 시 대분류 자동 선택
  foodTypeSelect.addEventListener('change', function() {
    const selectedOption = this.options[this.selectedIndex];
    if (selectedOption && selectedOption.value) {
      const group = selectedOption.dataset.group;
      if (group && foodGroupSelect.value !== group) {
        // 소분류에 연결된 대분류 값이 있고, 현재 대분류와 다를 경우
        foodGroupSelect.value = group;
        
        // 필요한 경우 Select2 업데이트
        if ($.fn.select2 && $(foodGroupSelect).data('select2')) {
          $(foodGroupSelect).trigger('change');
        }
      } else if (!group) {
        // 대분류 정보가 없는 경우 서버에서 조회
        fetch(`/label/get-food-group/?food_type=${encodeURIComponent(selectedOption.value)}`)
          .then(response => response.json())
          .then(data => {
            if (data.success && data.food_group) {
              foodGroupSelect.value = data.food_group;
              
              // 필요한 경우 Select2 업데이트
              if ($.fn.select2 && $(foodGroupSelect).data('select2')) {
                $(foodGroupSelect).trigger('change');
              }
              
              // 현재 선택된 소분류에 대분류 정보 저장
              selectedOption.dataset.group = data.food_group;
            }
          })
          .catch(error => console.error('대분류 조회 중 오류:', error));
      }
    }
  });
}

// ------------------ Document Ready ------------------
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
  // 전역으로 updateNutritionFields 함수 노출
  window.updateNutritionFields = updateNutritionFields;

  // 식품유형 값 동기화
  $('#food_group').on('change', function() {
    $('#hidden_food_group').val($(this).val());
  });
  
  $('#food_type').on('change', function() {
    $('#hidden_food_type').val($(this).val());
  });
  
  // 초기 값도 설정
  $('#hidden_food_group').val($('#food_group').val());
  $('#hidden_food_type').val($('#food_type').val());

  // 장기보존식품 값 동기화
  $('.grp-long-shelf').on('change', function() {
    if (this.checked) {
      $('#hidden_preservation_type').val(this.value);
    } else {
      $('#hidden_preservation_type').val('');
    }
  });

  // 제조방법 값 동기화
  $('.grp-sterilization').not('#chk_sterilization_other').on('change', function() {
    if (this.checked) {
      $('#hidden_processing_method').val(this.value);
    } else {
      $('#hidden_processing_method').val('');
    }
  });

  // 조건 상세 값 동기화
  $('input[name="processing_condition"]').on('input', function() {
    $('#hidden_processing_condition').val(this.value);
  });

  // 초기 값 설정
  const selectedPreservation = $('.grp-long-shelf:checked').val() || '';
  const selectedMethod = $('.grp-sterilization:checked').not('#chk_sterilization_other').val() || '';
  const conditionValue = $('input[name="processing_condition"]').val() || '';

  $('#hidden_preservation_type').val(selectedPreservation);
  $('#hidden_processing_method').val(selectedMethod);
  $('#hidden_processing_condition').val(conditionValue);
});

// DOMContentLoaded 이벤트 핸들러 (Select2 초기화 등)
document.addEventListener("DOMContentLoaded", function () {
  // 초기화
  updateSummary();
});

// DOM이 로드된 후 초기화 함수 실행
document.addEventListener('DOMContentLoaded', function() {
  // 이미 저장된 식품유형이 있는 경우, 페이지 로드 시 소분류 목록 필터링
  const foodGroupSelect = document.getElementById('food_group');
  const foodTypeSelect = document.getElementById('food_type');
  
  if (foodGroupSelect && foodGroupSelect.value) {
    // 이미 대분류 값이 선택되어 있는 경우
    const selectedGroup = foodGroupSelect.value;
    
    // 처음 페이지 로드 시 소분류가 이미 선택되어 있으므로 변경할 필요는 없음
    // 하지만 Select2가 적용된 경우를 대비하여 트리거
    if ($.fn.select2 && $(foodGroupSelect).data('select2')) {
      $(foodGroupSelect).trigger('change');
    }
  }
});