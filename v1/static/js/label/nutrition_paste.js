/*
 * 영양성분 표를 엑셀에서 붙여넣기.
 *
 * 배합비는 표로 붙여넣게 해 뒀는데(sheet_paste.js) 영양성분은 칸마다 손으로
 * 옮겨 적어야 했다. 사람들이 가진 것은 대개 이런 표다.
 *
 *     나트륨    660 mg   33 %
 *     탄수화물  1 g       0 %
 *     …
 *
 * **항목명을 읽어 맞춘다.** 자리로 넣으면 순서가 다른 표에서 값이 통째로
 * 어긋난다 — 어느 회사 표는 당류가 지방 뒤에 있고, 어느 표는 %가 앞에 있다.
 * 이름을 견주면 순서를 몰라도 된다. AI 를 쓰지 않는다. 이름 목록과 견주는
 * 사전 대조라 결과가 늘 같고, 무엇을 어디에 넣었는지 그대로 말해 줄 수 있다.
 *
 * **표의 머리도 함께 읽는다.** 여기가 빠지면 숫자만 맞고 뜻이 틀린다.
 *
 *     ┌───────────────────────────────┐
 *     │ 영양정보   총 내용량 100 g      │   ← 단위량 100 g, 포장개수 1
 *     │            96 kcal             │   ← 총 내용량 전체의 열량
 *     │ 총 내용량당   1일 영양성분…      │   ← **이 표가 무엇 당인지**
 *     └───────────────────────────────┘
 *
 * 저장 칸은 언제나 100 g 당이라, "무엇 당인지" 를 모르면 환산을 못 한다.
 * 그대로 넣으면 다시 표를 그릴 때 인쇄된 값과 다른 숫자가 나온다 — 실제로
 * 그 일이 났다. 그래서 머리에서 읽은 기준을 입력 기준과 표시기준에 함께
 * 넣어 둔다.
 *
 * 붙여넣기를 가로채는 것은 **여러 칸일 때만**이다. 한 칸짜리 값을 붙여넣는
 * 것은 그냥 그 칸에 들어가야 한다.
 */
(function () {
  'use strict';

  /** 견줄 때만 쓰는 형태. 띄어쓰기·괄호·구분기호를 지운다. */
  function key(text) {
    return String(text == null ? '' : text)
      .replace(/[\s()（）[\]{}/\\|·・,.\-_]/g, '')
      .toLowerCase();
  }

  /*
   * 라벨과 엑셀에서 실제로 쓰는 이름들. NUTRITION_DATA 의 이름이 기본이고,
   * 다르게 부르는 것만 여기에 덧붙인다. 새 이름이 나오면 한 줄을 더한다.
   */
  var EXTRA_NAMES = {
    calories:       ['열량', '칼로리', 'kcal', 'energy', 'calorie'],
    natriums:       ['나트륨', '소듐', 'sodium', 'na'],
    carbohydrates:  ['탄수화물', 'carbohydrate', 'carbs'],
    sugars:         ['당류', '총당류', 'sugar'],
    fats:           ['지방', '총지방', 'fat'],
    trans_fats:     ['트랜스지방', '트랜스지방산', 'transfat'],
    saturated_fats: ['포화지방', '포화지방산', 'saturatedfat'],
    cholesterols:   ['콜레스테롤', 'cholesterol'],
    proteins:       ['단백질', 'protein'],
    dietary_fiber:  ['식이섬유', 'dietaryfiber', 'fiber']
  };

  function names() {
    var data = window.NUTRITION_DATA || {};
    var out = {};
    Object.keys(data).forEach(function (field) {
      out[field] = [data[field].label];
    });
    Object.keys(EXTRA_NAMES).forEach(function (field) {
      if (!out[field]) out[field] = [];
      EXTRA_NAMES[field].forEach(function (name) {
        if (out[field].indexOf(name) < 0) out[field].push(name);
      });
    });
    return out;
  }

  /*
   * 이 글자가 어느 성분을 말하는가.
   *
   * **가장 긴 이름이 이긴다.** "트랜스지방" 에는 "지방" 도 들어 있는데, 긴
   * 쪽이 더 구체적이다. 짧은 쪽을 고르면 트랜스지방 값이 지방 칸으로 간다.
   *
   * **짧은 이름은 글자까지 같을 때만 본다.** 인(P)·철(Fe)처럼 한 글자짜리
   * 이름을 품는지로 보면 아무 문구나 걸린다("인공감미료" -> 인). 영문도
   * 마찬가지다("na" -> banana).
   *
   * Returns: {field, alias, score} 또는 null
   */
  function matchName(text, table) {
    var want = key(text);
    if (!want) return null;
    var best = null;
    Object.keys(table).forEach(function (field) {
      table[field].forEach(function (alias) {
        var a = key(alias);
        if (!a) return;
        var least = /^[a-z0-9]+$/.test(a) ? 3 : 2;
        var score = want === a ? 1000 + a.length
                  : (a.length >= least && want.indexOf(a) >= 0) ? a.length
                  : 0;
        if (score && (!best || score > best.score)) {
          best = { field: field, alias: alias, score: score };
        }
      });
    });
    return best;
  }

  /**
   * 이름을 뗀 나머지. 이름과 값이 한 칸에 같이 있는 표를 위해서다.
   *
   *     "나트륨 660 mg" -> " 660 mg"
   *     "비타민B6"      -> " "        이름 안의 6 을 값으로 보면 안 된다
   *
   * 글자 사이에 띄어쓰기가 끼어 있어도 뗀다("트랜스 지방").
   */
  function stripName(text, alias) {
    var pattern = String(alias).split('').map(function (ch) {
      return ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('\\s*');
    return String(text == null ? '' : text).replace(new RegExp(pattern, 'i'), ' ');
  }

  /* 단위. 무게는 서로 바꿔 넣을 수 있다 — 0.66 g 은 660 mg 이다. */
  var GRAMS = { 'μg': 1e-6, 'µg': 1e-6, 'ug': 1e-6, '㎍': 1e-6,
                'mg': 1e-3, '㎎': 1e-3, 'g': 1 };
  var UNIT_RE = /(kcal|㎉|mg|㎎|μg|µg|ug|㎍|ml|mL|㎖|g|l|L)\s*$/;

  function unitOf(text) {
    var m = String(text || '').trim().match(UNIT_RE);
    return m ? m[1] : '';
  }

  /** NUTRITION_DATA 의 단위에서 앞 토막만. "μg RAE" -> "μg" */
  function baseUnit(unit) {
    return String(unit || '').trim().split(/\s+/)[0];
  }

  /**
   * 칸에서 숫자를 꺼낸다. 넣을 칸의 단위와 다르면 맞춰 준다.
   *
   * **"5kcal 미만" 같은 칸은 숫자로 보지 않는다.** 5 로 넣으면 라벨에는
   * "5 kcal" 이 찍힌다 — 인쇄된 것과 다른 값이다. 못 읽었다고 말해 준다.
   */
  function valueOf(cell, wantUnit) {
    var text = String(cell == null ? '' : cell).replace(/,/g, '').trim();
    if (!text) return null;
    if (VAGUE_RE.test(text)) return null;
    if (/%|％|기준치/.test(text)) return null;        // 1일 기준치 비율 칸
    var m = text.match(/-?\d+(?:\.\d+)?/);
    if (!m) return null;
    var number = parseFloat(m[0]);
    if (isNaN(number)) return null;

    var from = unitOf(text), to = baseUnit(wantUnit);
    if (from && to && from !== to && GRAMS[from] && GRAMS[to]) {
      number = number * GRAMS[from] / GRAMS[to];
      number = Math.round(number * 1e6) / 1e6;
    }
    return String(number);
  }

  /* "5kcal 미만" 처럼 어림한 표기. 숫자로 넣으면 인쇄된 것과 다른 값이 된다 */
  var VAGUE_RE = /미만|이하|이상|초과/;

  /* 표의 머리. 이 표가 무엇 당인지, 그리고 그 기준량이 얼마인지 */
  var TOTAL_RE = /총\s*내용량/;
  var UNIT_BASIS_RE = /(1회\s*제공량|1회\s*섭취참고량|단위\s*내용량|단위량)/;
  var PER_100_RE = /100\s*(?:g|㎖|ml|mL|그램)\s*당/g;
  /* "100 g당" 바로 앞에 이 말이 있으면, 그 100 g 은 그 기준의 양이다.
     "총 내용량 100 g 당" 은 100 g 당 표가 아니라 총 내용량이 100 g 인 표다.
     서버도 같은 규칙으로 읽는다(ocr_apply.basis_kind). */
  var BASIS_HEAD_RE = /(총\s*내용량|1회\s*제공량|1회\s*섭취참고량|단위\s*내용량)\s*$/;

  function saysPer100(text) {
    PER_100_RE.lastIndex = 0;
    var hit;
    while ((hit = PER_100_RE.exec(text))) {
      if (!BASIS_HEAD_RE.test(text.slice(0, hit.index))) return true;
    }
    return false;
  }
  var AMOUNT_RE = /(\d[\d,]*(?:\.\d+)?)\s*(kg|㎖|ml|mL|g|L)(?![a-zA-Z])/;
  var KCAL_RE = /(\d[\d,]*(?:\.\d+)?)\s*(?:kcal|㎉|킬로칼로리)/i;

  /**
   * 붙여넣은 칸들에서 표의 머리를 읽는다.
   *
   * **무엇 당인지(열 머리)가 총 내용량 표기보다 세다.** 이런 표가 흔하다.
   *
   *     영양정보   총 내용량 500 g      ← 봉지에 든 양
   *     100 g당    1일 영양성분 …       ← 아래 숫자들은 이것 당이다
   *
   * 총 내용량을 기준으로 보면 500 으로 나누게 되고, 모든 수치가 다섯 배로
   * 틀어진다. 기준은 열 머리에서, 기준량은 "총 내용량 500 g" 에서 온다.
   *
   * Returns: {kind, amount, unit, amountKind, calories}
   *   kind        'total' | 'unit' | '100g' | ''   아래 숫자들이 무엇 당인가
   *   amount      기준량. 못 읽으면 null
   *   amountKind  그 기준량이 총 내용량인지('total') 한 개 분량인지('unit')
   *   calories    머리에만 적힌 열량("96 kcal"). 표에 열량 줄이 없는 라벨이 흔하다
   */
  function readHead(cells) {
    var per100 = false, total = null, unit = null, calories = null;

    cells.forEach(function (raw) {
      var text = String(raw == null ? '' : raw).trim();
      if (!text) return;

      if (saysPer100(text)) per100 = true;

      var found = text.match(AMOUNT_RE);
      var amount = found
          ? { amount: found[1].replace(/,/g, ''), unit: found[2] }
          : { amount: null, unit: '' };

      if (TOTAL_RE.test(text)) {
        if (!total || (!total.amount && amount.amount)) total = amount;
        return;
      }
      if (UNIT_BASIS_RE.test(text)) {
        if (!unit || (!unit.amount && amount.amount)) unit = amount;
        return;
      }
      /* 머리의 열량. "96 kcal" 처럼 **항목명 없이 홀로** 적힌 것만 본다 —
         "열량 96 kcal" 은 아래에서 항목으로 잡힌다. 단위(kcal)도 열량의
         이름이라, 단위를 뗀 나머지에 이름이 있는지로 가른다. */
      if (VAGUE_RE.test(text)) return;      // "5kcal 미만" 을 5 로 넣지 않는다
      var kcal = text.match(KCAL_RE);
      if (kcal && calories === null
          && !matchName(text.replace(KCAL_RE, ' '), names())) {
        calories = kcal[1].replace(/,/g, '');
      }
    });

    var source = (total && total.amount) ? total
               : (unit && unit.amount) ? unit
               : (total || unit);
    return {
      kind: per100 ? '100g' : total ? 'total' : unit ? 'unit' : '',
      amount: source ? source.amount : null,
      unit: source ? source.unit : '',
      amountKind: (source && source === total) ? 'total' : source ? 'unit' : '',
      calories: calories
    };
  }

  /** 이 줄에서 성분 이름이 적힌 칸 번호들 */
  function nameCells(row, table) {
    var at = [];
    row.forEach(function (cell, j) {
      if (String(cell == null ? '' : cell).trim() && matchName(cell, table)) {
        at.push(j);
      }
    });
    return at;
  }

  /**
   * 이름만 적힌 칸인가. 가로·세로를 가를 때 쓴다.
   *
   * "96 kcal" 도 이름(kcal)으로는 걸린다 — 값이 붙어 있으면 머리글 칸이
   * 아니다. 이걸 안 가리면 "열량 | 96 kcal" 줄이 이름 두 개짜리 머리글로
   * 보이고, 그 아랫줄이 통째로 값으로 짝지어진다.
   */
  function isNameOnly(cell, table) {
    var hit = matchName(cell, table);
    return !!hit && valueOf(stripName(cell, hit.alias), '') === null;
  }

  /**
   * 줄들을 {성분: 값} 으로 읽는다. 세로로 적힌 표와 가로로 적힌 표를 모두 본다.
   *
   *     세로   나트륨  660 mg          가로   나트륨  탄수화물
   *            탄수화물  1 g                  660 mg  1 g
   *
   * 어느 쪽인지는 **이름이 한 줄에 몰려 있는가**로 가른다. 이름 줄 하나에
   * 여럿이 있고 그 아랫줄에는 적으면 가로다.
   *
   * Returns: {found: {field: 값}, labels: [넣은 항목 이름], unread: [못 읽은 칸]}
   */
  function readRows(rows) {
    var table = names(), data = window.NUTRITION_DATA || {};
    var found = {}, labels = [], unread = [];

    function take(nameCell, valueCells) {
      var hit = matchName(nameCell, table);
      if (!hit || found[hit.field] !== undefined) return false;
      var want = (data[hit.field] || {}).unit;
      // 이름을 뗀 나머지를 먼저 본다 — "나트륨 660 mg" 처럼 한 칸에 같이
      // 적힌 표가 흔하다. 이름 안의 숫자(비타민B6)는 이렇게 걸러진다
      var cells = [stripName(nameCell, hit.alias)].concat(valueCells);
      for (var i = 0; i < cells.length; i++) {
        var value = valueOf(cells[i], want);
        if (value !== null) {
          found[hit.field] = value;
          labels.push((data[hit.field] || {}).label || hit.field);
          return true;
        }
      }
      // 이름은 알아봤는데 숫자를 못 읽었다. 조용히 비우지 않고 말해 준다.
      // 한 성분을 두 번 말하지 않는다("열량" 과 "5kcal 미만" 은 같은 칸이다)
      var label = (data[hit.field] || {}).label || hit.field;
      if (unread.indexOf(label) < 0) unread.push(label);
      return false;
    }

    /* 넣은 것은 못 읽은 목록에서 뺀다. 한 성분이 두 칸에 걸쳐 적힌 표
       ("열량 | 96 kcal")에서는 앞 칸이 빈손으로 끝나고 뒤 칸이 채운다. */
    function result() {
      return { found: found, labels: labels,
               unread: unread.filter(function (label) {
                 return labels.indexOf(label) < 0;
               }) };
    }

    var counts = rows.map(function (row) {
      return row.filter(function (cell) { return isNameOnly(cell, table); }).length;
    });
    var across = -1;
    for (var i = 0; i + 1 < rows.length; i++) {
      if (counts[i] >= 2 && counts[i] > counts[i + 1]) { across = i; break; }
    }

    if (across >= 0) {
      var head = rows[across], body = rows[across + 1];
      for (var c = 0; c < head.length; c++) take(head[c], [body[c]]);
      return result();
    }

    rows.forEach(function (row) {
      var at = nameCells(row, table);
      at.forEach(function (j, i) {
        // 다음 이름 전까지가 이 이름의 값이다. 한 줄에 두 쌍이 있는 표도 있다
        var end = i + 1 < at.length ? at[i + 1] : row.length;
        var cells = row.slice(j + 1, end);
        // 이름 하나뿐인 줄에서는 앞 칸도 본다 — 값이 왼쪽에 오는 표가 있다
        if (at.length === 1) cells = cells.concat(row.slice(0, j));
        take(row[j], cells);
      });
    });
    return result();
  }

  /* ── 화면에 넣기 ──────────────────────────────────────────────────────── */

  function setValue(id, value) {
    var el = document.getElementById(id);
    if (!el) return false;
    el.value = value;
    // 쉼표 넣기·환산 안내가 이 이벤트에 매달려 있다
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  /** 값이 든 추가 성분이 있으면 접혀 있던 자리를 펴 준다 */
  function openAdditional() {
    var section = document.getElementById('additional-nutrients');
    if (!section) return;
    section.style.display = 'block';
    var icon = document.getElementById('nutrition-toggle');
    var text = document.getElementById('nutrition-toggle-text');
    if (icon) { icon.textContent = '▲'; icon.classList.add('rotated'); }
    if (text) { text.textContent = '성분 접기'; }
  }

  function say(message) {
    var box = document.getElementById('nutritionPasteReport');
    if (!box) return;
    box.textContent = message;
    box.style.display = message ? 'block' : 'none';
  }

  /**
   * 읽은 것을 화면에 넣는다.
   *
   * **기준을 먼저 넣는다.** 단위량과 포장개수가 정해져야 입력 기준의 환산
   * 계수가 맞는다(inputBasisFactor).
   */
  function apply(head, rows) {
    var told = [];

    if (head.amount) {
      setValue('serving_size', head.amount);
      var unitSelect = document.getElementById('serving_size_unit');
      if (unitSelect && head.unit) {
        var want = head.unit.toLowerCase() === 'g' ? 'g' : 'ml';
        unitSelect.value = want;
      }
      // 읽은 기준량이 총 내용량이면 단위량이 곧 총량이다. 포장개수가 예전
      // 값으로 남아 있으면(2 등) 표의 총량이 그 배수가 된다.
      if (head.amountKind === 'total') setValue('units_per_package', '1');
      told.push('단위량 ' + head.amount + ' ' + (head.unit || 'g'));
    }

    if (head.kind) {
      /* 이 표가 무엇 당인지. 두 곳에 넣는다 —
         입력 기준(넣은 값을 100 g 당으로 환산할 때 쓴다)과
         표시기준(다시 표를 그릴 때 쓴다). 둘이 어긋나면 인쇄된 값과 다른
         숫자가 나온다. */
      setValue('nutrition_input_basis', head.kind === '100g' ? 'per_100' : head.kind);
      setValue('basic_display_type', head.kind);
      told.push('기준 ' + (head.kind === 'total' ? '총 내용량당'
                        : head.kind === 'unit' ? '단위량당' : '100 g 당'));
      if (typeof window.updateInputBasisNote === 'function') {
        window.updateInputBasisNote();
      }
    }

    var read = readRows(rows);
    var data = window.NUTRITION_DATA || {};
    var extra = false;
    Object.keys(read.found).forEach(function (field) {
      setValue(field, read.found[field]);
      if (!(data[field] || {}).required) extra = true;
    });
    // 머리에만 적힌 열량("96 kcal"). 표에 열량 줄이 따로 없는 라벨이 흔하다
    if (head.calories !== null && !read.found.calories) {
      setValue('calories', head.calories);
      read.labels.push('열량');
    }
    if (extra) openAdditional();

    var parts = [];
    if (read.labels.length) {
      parts.push(read.labels.length + '개 항목을 넣었습니다 — '
                 + read.labels.join(', ') + '.');
    }
    if (told.length) parts.push('표의 머리에서 ' + told.join(', ') + '을(를) 읽었습니다.');
    if (read.unread.length) {
      parts.push('"' + read.unread.join('", "') + '" 은(는) 숫자를 못 읽어 비워 뒀습니다.');
    }
    if (!read.labels.length && !told.length) {
      parts.push('알아본 항목이 없습니다. 항목명과 값을 함께 복사해 주세요.');
    }
    say(parts.join(' '));
    return read.labels.length + told.length;
  }

  /* ── 붙여넣기를 받는다 ────────────────────────────────────────────────── */

  function cellsOf(text) {
    return text.replace(/\r/g, '').split('\n')
      .map(function (line) { return line.split('\t'); });
  }

  document.addEventListener('paste', function (event) {
    var clip = event.clipboardData || window.clipboardData;
    if (!clip) return;
    var text = clip.getData('text/plain') || '';
    // 한 칸짜리는 그냥 그 칸에 들어가야 한다. 여러 칸일 때만 가로챈다
    if (!text || (text.indexOf('\t') < 0 && text.indexOf('\n') < 0)) return;
    if (!window.NUTRITION_DATA) return;

    var rows = cellsOf(text).filter(function (row) {
      return row.some(function (cell) { return String(cell || '').trim() !== ''; });
    });
    if (!rows.length) return;

    var flat = [];
    rows.forEach(function (row) { flat = flat.concat(row); });
    var head = readHead(flat);
    var read = readRows(rows);
    // 우리 표가 아니면 손대지 않는다. 알아본 것이 하나도 없으면 그냥 둔다
    if (!read.labels.length && !head.kind && head.calories === null) return;

    event.preventDefault();
    apply(head, rows);
  });

  window.nutritionPasteApply = apply;         // 시험이 쓴다
  window.nutritionPasteKey = key;             // 시험이 쓴다
  window.nutritionPasteMatch = matchName;     // 시험이 쓴다
  window.nutritionPasteHead = readHead;       // 시험이 쓴다
  window.nutritionPasteRows = readRows;       // 시험이 쓴다
})();
