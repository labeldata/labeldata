/*
 * 내 문구 — 주의사항·기타표시사항의 빠른 입력 버튼에 얹는다.
 *
 * 기본 문구는 버튼으로 있었는데 **고정 목록이라 손댈 수가 없었다.** 회사마다
 * 쓰는 문장이 다르고("본 제품은 ○○공장에서 제조합니다"), 기본 목록에 들어
 * 있는 상담 전화 같은 것은 그 회사 것이 아니다. 그러니 사람들은 버튼을 두고도
 * 매번 손으로 쳤다.
 *
 * 같은 자리에 **내 문구**를 둔다. 담고, 고치고, 지운다. 담아 둔 것은 표시사항
 * 작성 화면에도 의뢰서 창에도 같이 나온다 — 문구함(MyPhrase) 한 곳에 있다.
 *
 * 기본 문구는 그대로 둔다. 지우고 싶은 것은 안 누르면 그만이고, 기본을 고치면
 * 판독이 기다리는 문장까지 흔들린다(label_phrases.py 주석 참고).
 */
(function () {
  'use strict';

  var API = '/label/api/phrases/';

  function csrf() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    var hit = document.cookie.split('; ').find(function (row) {
      return row.indexOf('csrftoken=') === 0;
    });
    return hit ? hit.split('=')[1] : '';
  }

  function send(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  /* 문구함은 칸 이름으로 나뉜다. 주의사항 문구가 기타표시사항 줄에 뜨면
     고르는 사람이 매번 골라내야 한다. */
  var CATEGORY = { cautions: 'cautions', additional_info: 'additional' };

  function load(field, box, options) {
    box = box || document.querySelector('[data-my-phrases="' + field + '"]');
    if (!box) return;
    var opts = options || box.__phraseOptions || {};
    box.__phraseOptions = opts;
    var url = API + '?category=' + (CATEGORY[field] || 'all')
            + (opts.defaults ? '&defaults=1' : '');
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        draw(box, field, (data && (data.phrases || data.data)) || [],
             (data && data.defaults) || [], opts);
      })
      .catch(function () {});
  }

  function draw(box, field, list, defaults, opts) {
    box.innerHTML = '';

    /* 기본 문구도 같은 모양으로 그린다. 한 화면은 버튼이고 다른 화면은
       목록이면, 같은 문구를 두 벌로 관리하는 것처럼 보인다. */
    (defaults || []).forEach(function (phrase) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-outline-' + (phrase.tone || 'secondary') + ' btn-sm';
      btn.title = phrase.content || '';
      btn.textContent = phrase.name || '';
      btn.addEventListener('click', function () {
        if (opts && opts.onPick) opts.onPick(phrase.content || '', phrase.name || '');
      });
      box.appendChild(btn);
    });

    list.forEach(function (phrase) {
      var chip = document.createElement('span');
      chip.className = 'my-phrase-chip';
      /* 누르면 칸에 들어가고, 다시 누르면 빠진다 — 기본 문구 버튼과 같은
         몸짓이어야 한다. 여기만 다르면 손이 헷갈린다. */
      var use = document.createElement('button');
      use.type = 'button';
      use.className = 'btn btn-outline-dark btn-sm'
          + ((opts && opts.onPick) ? '' : ' product-quick-text-btn');
      use.setAttribute('data-field', field);
      use.setAttribute('data-text', phrase.content || phrase.text || '');
      use.title = phrase.content || phrase.text || '';
      use.textContent = phrase.name || (phrase.content || '').slice(0, 20);
      if (opts && opts.onPick) {
        use.addEventListener('click', function () {
          opts.onPick(phrase.content || phrase.text || '', phrase.name || '');
        });
      }

      chip.appendChild(use);

      /* **담고 고치고 빼는 것은 한 자리에서만 한다.**
         표시사항은 기본정보 탭에서 쓰므로 문구도 거기서 관리한다. 의뢰서
         창에서는 고르기만 한다 — 같은 일을 두 화면에서 할 수 있게 해 두면
         어디서 무엇을 고쳤는지 사람이 좇지 못한다. */
      if (!opts || opts.manage !== false) {
        var edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'my-phrase-act';
        edit.title = '문구 고치기';
        // 아이콘 글꼴이 없는 화면에서는 빈 네모만 보인다. 글자로 그린다
        edit.textContent = '고침';
        edit.addEventListener('click', function () { rename(field, phrase, box); });

        var drop = document.createElement('button');
        drop.type = 'button';
        drop.className = 'my-phrase-act';
        drop.title = '문구함에서 빼기';
        drop.textContent = '×';
        drop.addEventListener('click', function () { remove(field, phrase, box); });

        chip.appendChild(edit);
        chip.appendChild(drop);
      }
      box.appendChild(chip);
    });

    // 담는 자리도 같은 줄에 둔다. 쓰다가 "이건 다음에도" 싶은 순간이 여기다
    if (!opts || opts.manage !== false) {
      var add = document.createElement('button');
      add.type = 'button';
      add.className = 'btn btn-outline-primary btn-sm my-phrase-add';
      add.textContent = '+ 내 문구 추가';
      add.addEventListener('click', function () { create(field, box); });
      box.appendChild(add);
    }

    // 새로 그린 버튼도 기본 버튼과 같은 동작을 갖게 한다
    if (typeof window.initProductQuickTextButtons === 'function') {
      window.initProductQuickTextButtons();
    }
  }

  function create(field, box) {
    var text = window.prompt('문구함에 담을 문장을 적어 주세요.\n'
                             + '(이 칸에 자주 넣는 문장을 그대로 적으면 됩니다)');
    if (!text || !text.trim()) return;
    var name = window.prompt('버튼에 적을 짧은 이름 (비우면 앞부분을 씁니다)',
                             text.trim().slice(0, 12)) || '';
    send(API + 'save/', { content: text.trim(), name: name.trim(),
                          category: CATEGORY[field] || 'additional' })
      .then(function (data) { if (data && data.success) load(field, box); })
      .catch(function () {});
  }

  function rename(field, phrase, box) {
    var text = window.prompt('문구를 고칩니다.', phrase.content || phrase.text || '');
    if (text === null) return;
    if (!text.trim()) return;
    var name = window.prompt('버튼에 적을 짧은 이름', phrase.name || '');
    if (name === null) return;
    send(API + phrase.id + '/update/', { content: text.trim(), name: name.trim() })
      .then(function (data) { if (data && data.success) load(field, box); })
      .catch(function () {});
  }

  function remove(field, phrase, box) {
    if (!window.confirm('"' + (phrase.name || '') + '" 을(를) 문구함에서 뺍니다.\n'
                        + '이미 칸에 넣어 둔 글자는 그대로 남습니다.')) return;
    send(API + phrase.id + '/delete/', {})
      .then(function (data) { if (data && data.success) load(field, box); })
      .catch(function () {});
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-my-phrases]').forEach(function (box) {
      load(box.getAttribute('data-my-phrases'));
    });
  });

  /**
   * 문구 조각들을 아무 상자에나 그린다.
   *
   * box      그릴 자리
   * field    'cautions' | 'additional_info'
   * options  {defaults: true, onPick: function (text, name) {}}
   *          onPick 을 주면 누를 때 그 함수가 받는다(의뢰서 창). 안 주면
   *          표시사항 작성 화면의 빠른 입력 버튼처럼 움직인다.
   */
  window.phraseChips = function (box, field, options) {
    load(field, box, options || {});
  };

  window.myPhrasesReload = load;      // 다른 화면에서 담은 뒤 부른다
})();
