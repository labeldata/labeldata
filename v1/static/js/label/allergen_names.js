/*
 * 알레르기 표시 명칭을 하나로 판정한다. (서버의 label/services/allergen_names.py 와 같은 규칙)
 *
 * **같은 물질이 여러 표기로 돌아다닌다.**
 *
 *     알류  /  알류(달걀)  /  달걀  /  알류 함유  /  난류
 *
 * 표시기준이 정한 명칭은 "알류" 이고, 괄호는 무엇을 넣었는지 밝히는 부연이다.
 * 그런데 화면은 이 값을 **문자열 그대로 Map 의 키로** 썼다. 저장값에서 온
 * "알류(달걀)" 과 원재료명 자동 감지가 찾아낸 "알류" 가 서로 다른 키라,
 * 한 줄에 같은 물질이 두 번 적혔다.
 *
 *     알류(달걀), 우유, 대두, 밀, 알류
 *
 * 태그를 넣는 자리마다 mergeAllergen 을 쓴다. 그냥 map.set(name, …) 하면
 * 같은 사고가 다시 난다.
 */
(function () {
  'use strict';

  // 값 뒤에 붙는 꼬리말. 물질 이름이 아니다.
  var TAIL = /\s*(함유|포함|사용|들어있음|등)\s*$/;
  // 괄호 부연. "알류(달걀)" 의 "(달걀)".
  var PAREN = /[(\[（【][^)\]）】]*[)\]）】]/g;

  function squeeze(text) {
    return String(text == null ? '' : text).replace(/\s+/g, '').toLowerCase();
  }

  // 키워드 표는 화면마다 다른 전역에 있다. 사본을 하나 더 만들지 않는다 —
  // 표가 두 벌이면 어느 날 한쪽만 고쳐진다.
  function keywordMap() {
    return window.allergenKeywords || window.PRODUCT_ALLERGEN_KEYWORDS || {};
  }

  var _index = null, _indexSource = null;
  function index() {
    var map = keywordMap();
    if (_index && _indexSource === map) return _index;
    var out = {};
    Object.keys(map).forEach(function (name) {
      out[squeeze(name)] = name;
      (map[name] || []).forEach(function (kw) {
        if (!(squeeze(kw) in out)) out[squeeze(kw)] = name;
      });
    });
    _index = out;
    _indexSource = map;
    return out;
  }

  /*
   * 표기 하나를 표시 명칭으로. 모르면 빈 문자열.
   *
   *     "알류(달걀)" -> "알류"      괄호는 부연이다
   *     "달걀"       -> "알류"      키워드는 그 물질에 속한다
   *     "알류 함유"  -> "알류"      꼬리말을 뗀다
   *     "홍삼"       -> ""          목록 밖 — 판정하지 않는다
   */
  function canonicalAllergen(token) {
    var text = String(token == null ? '' : token).trim().replace(TAIL, '').replace(/^[·,\s]+|[·,\s]+$/g, '');
    if (!text) return '';
    var table = index();

    var hit = table[squeeze(text)];
    if (hit) return hit;

    var base = text.replace(PAREN, '').replace(TAIL, '').trim().replace(/^[·,\s]+|[·,\s]+$/g, '');
    if (base) {
      hit = table[squeeze(base)];
      if (hit) return hit;
    }

    var inner = text.match(PAREN);
    for (var i = 0; inner && i < inner.length; i++) {
      hit = table[squeeze(inner[i].replace(/^[(\[（【]|[)\]）】]$/g, ''))];
      if (hit) return hit;
    }
    return '';
  }

  /*
   * 라벨에 적을 표기. 표시 명칭이거나, 명칭에 괄호 부연이 붙은 꼴만 그대로 둔다.
   *
   *     "알류(달걀)" -> "알류(달걀)"
   *     "대두류"     -> "대두"        명칭이 아니다
   *     "달걀"       -> "알류"
   */
  function displayAllergen(token, name) {
    var text = String(token == null ? '' : token).trim().replace(TAIL, '');
    if (text === name) return name;
    if (new RegExp('^' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
                   + '\\s*[(\\[（【][^)\\]）】]*[)\\]）】]$').test(text)) {
      return text;
    }
    return name;
  }

  /*
   * 태그 Map 에 하나 넣는다. **같은 물질이 이미 있으면 합친다.**
   *
   * 자세한 표기를 남긴다 — "알류(달걀)" 은 무엇을 넣었는지까지 말한다.
   * 목록 밖의 문구는 그대로 둔다(그런 것을 적는 라벨이 있다).
   */
  function mergeAllergen(map, token, source) {
    var text = String(token == null ? '' : token).trim().replace(TAIL, '');
    if (!text) return;
    var name = canonicalAllergen(text);
    if (!name) {
      if (!map.has(text)) map.set(text, source);
      return;
    }
    var form = displayAllergen(text, name);
    var existingKey = null;
    map.forEach(function (_src, key) {
      if (existingKey === null && canonicalAllergen(key) === name) existingKey = key;
    });
    if (existingKey === null) { map.set(form, source); return; }
    if (form.length > existingKey.length) {
      // 자세한 쪽으로 갈아 끼운다. 출처는 먼저 있던 것을 지킨다 —
      // 자동 감지가 손으로 고른 것을 덮으면 안 된다.
      var kept = map.get(existingKey);
      map.delete(existingKey);
      map.set(form, kept);
    }
  }

  window.canonicalAllergen = canonicalAllergen;
  window.displayAllergen = displayAllergen;
  window.mergeAllergen = mergeAllergen;
})();
