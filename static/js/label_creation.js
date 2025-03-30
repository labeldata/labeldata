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
  const foodSmall = $('#food_type_small option:selected').text();
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

  // 원재료명(참고) 섹션 표시
  const rawmtrlSection = document.getElementById('rawmtrl_nm_section');
  if (rawmtrlSection.classList.contains('collapse')) {
    rawmtrlSection.classList.add('show'); // 펼치기
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
  // 전역으로 updateNutritionFields 함수 노출
  window.updateNutritionFields = updateNutritionFields;
});

// DOMContentLoaded 이벤트 핸들러 (Select2 초기화 등)
document.addEventListener("DOMContentLoaded", function () {
  // 초기화
  updateSummary();
});