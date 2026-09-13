/*
 * 영양성분 표시 규칙 — **한 곳에서 정한다.**
 *
 * 「식품등의 표시기준」의 반올림·"미만" 표기는 성분마다 다르다. 나트륨과
 * 콜레스테롤은 같은 mg 인데 경계가 다르고(120 vs 100), 트랜스지방은 0.2 미만이
 * 0 이지만 0.5 미만은 "0.5g 미만" 이라고 적어야 하며, 당류만 "미만" 표기가 없다.
 *
 * 이 규칙이 세 곳에 흩어져 있었고 **셋이 서로 달랐다.**
 *
 *   · v1/label/services/nutrition_calc.py 의 display_value  (서버 · 옳음)
 *   · nutrition_calculator_popup.js 의 processNutritionValue (계산기 · 옳음)
 *   · label_preview.js 의 roundKoreanNutrition               (미리보기 · **틀림**)
 *
 * 미리보기 것은 성분이 아니라 단위('kcal'/'mg'/'g')로만 갈라서, 성분별 규칙을
 * 애초에 표현할 수 없었다. 그래서 **화면에서 확인한 표와 실제로 인쇄되는 표의
 * 숫자가 달랐다.** 특히 트랜스지방 0.3 g 을 `0` 으로 인쇄했다 — 표시기준
 * 위반이다. 콜레스테롤 3 mg 도 `0` 이었고(옳게는 "5mg 미만"), 당류 3.7 g 은
 * `3.7`(옳게는 `4`), 나트륨 경계는 140(옳게는 120)이었다.
 *
 * 그래서 JS 쪽 두 벌을 이 파일 하나로 모은다. 계산기와 미리보기가 같은 파일을
 * 읽으므로 한쪽만 고쳐지는 일이 생기지 않는다. 서버 쪽 display_value 와
 * 같은 답을 내야 하고, 그것은 v1/label/tests.py 가 지킨다.
 */

// 숫자에 쉼표 추가
function formatNumberWithCommas(num) {
  if (typeof num === 'string') {
    return num;
  }
  if (typeof num !== 'number' || isNaN(num)) {
    return '0';
  }
  return num.toLocaleString('ko-KR');
}

// 영양성분 값 처리 함수 (식품등의 표시기준)
function processNutritionValue(key, value) {
  if (!value || value === 0) return '0';

  const roundedValue = parseFloat(value);
  if (isNaN(roundedValue)) return '0';

  switch (key) {
    case 'calories':
      if (roundedValue < 5) return '5kcal 미만';
      return formatNumberWithCommas(Math.round(roundedValue / 5) * 5); // 5kcal 단위
    case 'natriums':
    case 'sodium':
      if (roundedValue < 5) return '0';
      if (roundedValue <= 120) {
        // 120mg 이하: 5mg 단위 반올림 (식약처 기준)
        return formatNumberWithCommas(Math.round(roundedValue / 5) * 5);
      }
      // 120mg 초과: 10mg 단위 반올림 (식약처 기준)
      return formatNumberWithCommas(Math.round(roundedValue / 10) * 10);
    case 'cholesterols':
    case 'cholesterol':
      if (roundedValue < 2) return '0';
      if (roundedValue < 5) return '5mg 미만';
      if (roundedValue <= 100) {
        // 100mg 이하: 5mg 단위 반올림 (식약처 기준)
        return formatNumberWithCommas(Math.round(roundedValue / 5) * 5);
      }
      // 100mg 초과: 10mg 단위 반올림 (식약처 기준)
      return formatNumberWithCommas(Math.round(roundedValue / 10) * 10);
    case 'calcium':
    case 'iron':
    case 'potassium':
    case 'magnesium':
    case 'phosphorus':
    case 'zinc':
    case 'selenium':
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'carbohydrates':
    case 'carbohydrate':
    case 'proteins':
    case 'protein':
    case 'dietary_fiber':
      if (roundedValue < 1) return '1g 미만';
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'sugars': // 당류는 '미만' 표시 없음
      if (roundedValue < 0.5) return '0';
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'fats':
    case 'fat':
    case 'saturated_fats':
    case 'saturated_fat':
      if (roundedValue < 0.5) return '0';
      if (roundedValue <= 5) {
        return formatNumberWithCommas(Math.round(roundedValue * 10) / 10);
      }
      return formatNumberWithCommas(Math.round(roundedValue));
    case 'trans_fats':
    case 'trans_fat':
      if (roundedValue < 0.2) return '0';
      if (roundedValue < 0.5) return '0.5g 미만';
      return formatNumberWithCommas(Math.round(roundedValue * 10) / 10);
    default:
      if (roundedValue < 0.1) return '0';
      return formatNumberWithCommas(Math.round(roundedValue * 10) / 10);
  }
}

window.formatNumberWithCommas = formatNumberWithCommas;
window.processNutritionValue = processNutritionValue;
