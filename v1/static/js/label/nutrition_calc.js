/*
 * 이론치로 영양성분표를 만드는 세 걸음 — 화면 쪽.
 *
 *     계산값  ──오차──▶  적용값  ──반올림──▶  표시될 값
 *
 * 사람들이 가진 것은 레시피로 뽑은 **계산값**이다. 규정은 실측값이 표시량에서
 * 얼마나 벌어져도 되는지를 **한쪽 방향으로만** 정해 두었으므로, 안전한 쪽이
 * 성분마다 반대다. 그 방향대로 오차를 물린 것이 **적용값**이고, 표시 단위로
 * 반올림해 라벨에 인쇄되는 것이 **표시될 값**이다.
 *
 * 서버도 같은 계산을 한다(services/nutrition_calc.py). 사용자가 값을 넣는
 * 동안 서버를 부를 수 없어 여기에도 두지만, **규정 숫자는 서버가 내려준다**
 * (nutrition-rules-data). 숫자를 두 벌로 적어 두면 어느 날 한쪽만 고쳐진다.
 */
(function () {
  'use strict';

  function rules() {
    return window.NUTRITION_RULES || {};
  }

  function number(value) {
    if (value === null || value === undefined) return null;
    var text = String(value).replace(/,/g, '').trim();
    if (!text) return null;
    var n = parseFloat(text);
    return isNaN(n) ? null : n;
  }

  /**
   * 이 성분은 오차를 어느 쪽으로 물려야 안전한가.
   *
   *   +1  높여 적는다 (실측이 표시량의 120% 미만이어야 하는 성분)
   *   -1  낮춰 적는다 (실측이 표시량의 80% 이상이어야 하는 성분)
   */
  function direction(field) {
    return (rules().toleranceUp || []).indexOf(field) >= 0 ? 1 : -1;
  }

  /* 열량은 오차를 직접 곱하지 않는다. 탄단지가 정하는 값이라 따로 부풀리면
     표 안이 서로 맞지 않는다 — 보정한 탄단지로 다시 계산한다. */
  var SKIP = ['calories'];

  /**
   * 계산값에 오차를 물린다.
   *
   * values  {성분: 계산값}
   * rate    보정폭(%)
   * mode    'up'   실측 120% 무리만 높인다 (현장에서 쓰는 방식)
   *         'both' 실측 80% 무리도 함께 낮춘다 (규정이 정한 두 방향 모두)
   *
   * **늘 계산값에서 출발해야 한다.** 적용값에 다시 물리면 두 번 곱해진다.
   */
  function applyTolerance(values, rate, mode) {
    var percent = number(rate) || 0;
    var out = {};
    Object.keys(values).forEach(function (field) {
      var value = number(values[field]);
      if (value === null || SKIP.indexOf(field) >= 0 || !percent) {
        out[field] = values[field];
        return;
      }
      var way = direction(field);
      if (way < 0 && mode !== 'both') {
        out[field] = values[field];
        return;
      }
      out[field] = Math.round(value * (1 + way * percent / 100) * 1e6) / 1e6;
    });
    return out;
  }

  /**
   * 탄수화물·단백질·지방으로 열량을 계산한다. 규정이 정한 계수를 쓴다.
   *
   * 식이섬유와 당알코올은 **탄수화물 안에 들어 있으면서 계수가 다르다.**
   * 그만큼을 빼고 각자의 계수로 센다.
   *
   * Returns: 열량 또는 null (탄단지 중 하나라도 없으면)
   */
  function caloriesFromMacros(values) {
    var factors = rules().calorieFactors || {};
    var carb = number(values.carbohydrates);
    var protein = number(values.proteins);
    var fat = number(values.fats);
    if (carb === null || protein === null || fat === null) return null;

    var fiber = number(values.dietary_fiber) || 0;
    var alcohols = number(values.sugar_alcohols) || 0;
    var rest = Math.max(carb - fiber - alcohols, 0);
    var total = rest * (factors.carbohydrates || 4)
              + fiber * (factors.dietary_fiber || 2)
              + alcohols * (factors.sugar_alcohols || 2.4)
              + protein * (factors.proteins || 4)
              + fat * (factors.fats || 9);
    return Math.round(total * 1e4) / 1e4;
  }

  /**
   * 100 g 당 값을 1회 제공량 기준으로. 기준량을 모르면 null.
   *
   * 분모를 모르면서 곱하면 모든 수치의 뜻이 바뀐다 — 그건 안 하느니만 못하다.
   */
  function perServing(values, per100, serving) {
    var base = number(per100), amount = number(serving);
    if (!base || !amount || base <= 0 || amount <= 0) return null;
    var factor = amount / base;
    var out = {};
    Object.keys(values).forEach(function (field) {
      var value = number(values[field]);
      if (value !== null) out[field] = Math.round(value * factor * 1e6) / 1e6;
    });
    return out;
  }

  /**
   * 고열량·저영양 식품인가. **값은 1회 제공량 기준이어야 한다.**
   *
   * Returns: {verdict: true|false|null, kind, hits: [줄 …], why}
   *          **모르는 것과 아닌 것은 다르다** — 값이 비면 verdict 는 null 이다.
   */
  function hiengLntrt(values, kind, noodle) {
    var all = rules().hieng || {};
    var names = rules().hiengNames || {};
    var list = all[kind];
    if (!list) {
      return { verdict: null, kind: '', hits: [],
               why: '간식용인지 식사대용인지 정해야 판정할 수 있습니다.' };
    }
    var data = window.NUTRITION_DATA || {};
    var known = {};
    ['calories', 'proteins', 'saturated_fats', 'sugars', 'natriums']
      .forEach(function (field) {
        var value = number(values[field]);
        if (value !== null) known[field] = value;
      });
    if (known.calories === undefined) {
      return { verdict: null, kind: names[kind] || '', hits: [],
               why: '열량이 없어 판정할 수 없습니다.' };
    }

    var hits = [], unknown = false;
    list.forEach(function (rule) {
      var met = true, words = [];
      for (var i = 0; i < rule.length; i++) {
        var field = rule[i][0], sign = rule[i][1], bound = rule[i][2];
        if (known[field] === undefined) { met = false; unknown = true; break; }
        if (field === 'natriums' && noodle && bound === 600) {
          bound = rules().hiengNoodleSodium || 1000;
        }
        var unit = (data[field] || {}).unit || '';
        words.push(((data[field] || {}).label || field) + ' ' + known[field] + unit
                   + ' (' + (sign === '>' ? '초과' : '미만') + ' 기준 ' + bound + unit + ')');
        if (!(sign === '>' ? known[field] > bound : known[field] < bound)) {
          met = false;
          break;
        }
      }
      if (met) hits.push(words.join(' + '));
    });

    if (hits.length) return { verdict: true, kind: names[kind], hits: hits };
    if (unknown) {
      return { verdict: null, kind: names[kind], hits: [],
               why: '단백질·포화지방·당류·나트륨 중 비어 있는 값이 있어 '
                    + '모든 기준을 다 보지 못했습니다.' };
    }
    return { verdict: false, kind: names[kind], hits: [] };
  }

  window.nutritionCalc = {
    direction: direction,
    applyTolerance: applyTolerance,
    caloriesFromMacros: caloriesFromMacros,
    perServing: perServing,
    hiengLntrt: hiengLntrt,
  };
})();
