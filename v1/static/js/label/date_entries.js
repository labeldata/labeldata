/*
 * 소비기한·제조연월일을 한 칸에 여러 줄로 담는다.
 *
 * 표시사항에는 날짜 항목이 여럿 필요할 때가 있다 — "제조연월일: 별도 표기" 와
 * "소비기한: 제조일로부터 12개월" 을 함께 인쇄하는 제품이 흔하다. 그런데 DB 에는
 * 이 값을 담을 칸이 pog_daycnt 하나뿐이다.
 *
 * 칸을 늘리는 대신 **한 칸에 줄로 쌓는다.** 한 줄이 항목 하나이고, 줄머리의
 * "유형:" 이 그 줄의 항목명이다.
 *
 *     제조연월일: 별도 표기
 *     소비기한: 제조일로부터 12개월
 *
 * 옛 값(줄머리 없는 한 줄)은 소비기한 한 건으로 읽는다. 그래서 이 규약을 몰랐던
 * 기존 라벨도 인쇄 결과가 달라지지 않는다. 반대로 소비기한 한 건만 있으면 줄머리
 * 없이 저장한다 — 데이터를 괜히 바꾸지 않는다.
 */
(function () {
  'use strict';

  // 표시기준이 쓰는 날짜 항목명. 이 이름으로 시작하는 줄만 항목으로 읽는다.
  // "제조일로부터 12개월" 처럼 값 안에 콜론이 없어도, 있어도 상관없다.
  var DATE_TYPES = ['소비기한', '품질유지기한', '유통기한',
                    '제조연월일', '제조일자', '생산연도'];
  var DEFAULT_TYPE = '소비기한';

  // defaultType — 줄머리가 없는 줄에 붙일 항목명. 옛 화면(label_creation)은
  // 항목명을 date_option 이라는 별도 값으로 들고 있어서, 그 값을 여기로 넘긴다.
  function parse(text, defaultType) {
    var fallback = defaultType || DEFAULT_TYPE;
    var out = [];
    String(text == null ? '' : text).split(/\r?\n/).forEach(function (line) {
      line = line.trim();
      if (!line) return;
      var type = fallback;
      // 줄머리가 "유형:" 이면 그 유형으로 읽는다. 정규식을 만들지 않는다 -
      // 항목명에 정규식 특수문자가 없다는 보장이 없고, 앞뒤만 보면 되는 일이다.
      for (var i = 0; i < DATE_TYPES.length; i++) {
        var name = DATE_TYPES[i];
        if (line.slice(0, name.length) !== name) continue;
        var rest = line.slice(name.length).replace(/^\s+/, '');
        if (rest.charAt(0) !== ':' && rest.charAt(0) !== '：') continue;
        type = name;
        line = rest.slice(1).trim();
        break;
      }
      out.push({ type: type, value: line });
    });
    return out;
  }

  function serialize(entries) {
    var rows = (entries || [])
      .map(function (e) {
        return { type: (e.type || DEFAULT_TYPE).trim(), value: (e.value || '').trim() };
      })
      .filter(function (e) { return e.value; });
    if (!rows.length) return '';
    // 소비기한 한 건이면 옛 모양 그대로 둔다
    if (rows.length === 1 && rows[0].type === DEFAULT_TYPE) return rows[0].value;
    return rows.map(function (e) { return e.type + ': ' + e.value; }).join('\n');
  }

  window.DateEntries = {
    TYPES: DATE_TYPES,
    DEFAULT_TYPE: DEFAULT_TYPE,
    parse: parse,
    serialize: serialize
  };
})();
