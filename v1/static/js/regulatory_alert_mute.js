/**
 * 알림 사유를 그 자리에서 끄기 — 부적합·행정처분·수거검사 세 탭 공통.
 *
 * 같은 단추가 세 곳(목록의 뉴스 상세 패널, 목록의 수거검사 상세 패널, 상세
 * 독립 페이지)에 나온다. 인라인 스크립트로 두면 뉴스가 선택됐을 때만 정의돼
 * 수거검사 패널에서는 죽은 단추가 되고, 세 벌로 복사해 두면 문구 하나 고칠 때
 * 세 곳을 고쳐야 한다. 그래서 파일 하나로 둔다.
 *
 * 주소를 {% url %} 대신 적어 두는 이유: 이 파일은 정적 파일이라 템플릿 태그를
 * 쓸 수 없다. v1/regulatory/urls.py 의 경로와 짝이므로 한쪽을 고치면 다른
 * 쪽도 고쳐야 한다.
 */
(function () {
  'use strict';

  var API_MUTE = '/regulatory/api/alert-mutes/';
  var API_RULE_DELETE = '/regulatory/api/alert-rules/{id}/delete/';

  var SCOPE_LABEL = {
    keyword:    '키워드',
    ingredient: '내 원료',
    company:    '업체',
  };

  function csrf() {
    var m = document.cookie.split('; ').find(function (r) {
      return r.indexOf('csrftoken=') === 0;
    });
    return m ? m.split('=')[1] : '';
  }

  function toast(msg, kind) {
    if (typeof window.showSnackbar === 'function') window.showSnackbar(msg, kind);
    else if (kind === 'error') alert(msg);
  }

  function refreshBadge(unread) {
    var b = document.getElementById('regAlertBadge');
    if (b && typeof unread === 'number') {
      b.textContent = unread > 9 ? '9+' : unread;
      b.style.display = unread > 0 ? '' : 'none';
    }
    if (typeof window.fetchNotifications === 'function') window.fetchNotifications();
  }

  /**
   * "이 키워드/원료/업체 때문에 오는 알림은 그만".
   *
   * 서버가 규칙을 남기는 동시에 이미 쌓인 같은 이유의 알림도 함께 치우고,
   * 몇 건을 치웠는지 돌려준다. 그 숫자를 그대로 말해 준다 — 눌러도 화면이
   * 그대로면 "안 먹었나" 싶어 같은 것을 또 누르기 때문이다.
   */
  function muteAlert(scope, value) {
    var what = SCOPE_LABEL[scope] || '키워드';
    var ok = confirm(
      what + ' ‘' + value + '’ (으)로 걸리는 알림을 앞으로 받지 않습니다.\n' +
      '이미 와 있는 같은 이유의 알림도 함께 정리됩니다.\n\n' +
      '알림 설정 > 받지 않기 에서 언제든 되돌릴 수 있습니다.');
    if (!ok) return;

    fetch(API_MUTE, {
      method: 'POST',
      headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/json'},
      body: JSON.stringify({scope: scope, value: value}),
    })
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (res) {
        if (!res.ok || !res.d.success) {
          toast(res.d.error || '처리하지 못했습니다.', 'error');
          return;
        }
        var parts = [];
        if (res.d.hidden) parts.push('기존 ' + res.d.hidden + '건 정리');
        // 앱 푸시는 일 3회 배치로 나간다 — 아직 안 나간 것을 거뒀다는 사실을
        // 말해 줘야 "껐는데 낮에 또 울리려나" 하는 걱정이 남지 않는다.
        if (res.d.push_cancelled) parts.push('예약 푸시 ' + res.d.push_cancelled + '건 취소');
        toast(what + ' ‘' + value + '’ 알림을 껐습니다' +
              (parts.length ? ' · ' + parts.join(' · ') : '') + '.', 'success');
        refreshBadge(res.d.unread);
        setTimeout(function () { window.location.reload(); }, 600);
      })
      .catch(function () { toast('처리하지 못했습니다.', 'error'); });
  }

  /**
   * 상세에서 바로 알림 키워드(AlertRule) 지우기.
   * 예전에는 설정 모달을 열어 등록해 둔 키워드 목록에서 같은 말을 눈으로
   * 찾아야 했다 — 비슷한 키워드가 여럿이면 어느 것인지 알 수 없다.
   */
  function deleteKeywordFromDetail(ruleId, keyword) {
    var ok = confirm(
      '‘' + keyword + '’ 키워드를 삭제합니다.\n' +
      '앞으로 이 키워드로는 알림이 오지 않습니다. (연결된 모든 기기에서 삭제)');
    if (!ok) return;

    fetch(API_RULE_DELETE.replace('{id}', ruleId), {
      method: 'POST',
      headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/json'},
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.success) { toast(d.error || '삭제하지 못했습니다.', 'error'); return; }
        document.querySelectorAll('#kw-log-rule-' + ruleId).forEach(function (el) {
          el.style.opacity = '0.3';
          setTimeout(function () { el.remove(); }, 400);
        });
        toast('‘' + keyword + '’ 키워드를 삭제했습니다.', 'success');
        setTimeout(function () { window.location.reload(); }, 700);
      })
      .catch(function () { toast('삭제하지 못했습니다.', 'error'); });
  }

  window.muteAlert = muteAlert;
  window.deleteKeywordFromDetail = deleteKeywordFromDetail;
}());
