# 배포 절차 (PythonAnywhere)

서버: `/home/labeldata/mysite` · 가상환경 `/home/labeldata/.virtualenvs/mysite-env`

## 순서

```bash
cd /home/labeldata/mysite
git pull origin main

# 정적 파일(CSS·JS·이미지)이 바뀌었으면 반드시
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py collectstatic --noinput

# 문제 없는지 확인 (템플릿 검사 포함)
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py check
```

마지막으로 **Web 탭 → Reload**.

## `collectstatic` 을 빠뜨리면

`/static/` 은 `STATIC_ROOT`(`/home/labeldata/mysite/staticfiles`)에서 서빙된다.
소스 트리(`v1/static/`)를 직접 보지 않으므로, **CSS·JS 를 고쳐도 pull 만으로는
반영되지 않는다.** 템플릿(HTML)은 소스에서 바로 읽으므로 즉시 반영된다.

그래서 증상이 헷갈린다 — **화면 구조는 바뀌었는데 스타일만 옛날 그대로**이고,
버튼을 눌러도 새로 추가한 JS 동작이 없다. "CSS가 깨졌다" 로 보이지만 실제로는
새 파일이 아직 서버에 없는 것이다.

새 파일을 추가했을 때뿐 아니라 **기존 파일을 고쳤을 때도** 필요하다.

## Reload 를 빠뜨리면

`DEBUG=False` 라 Django 가 템플릿까지 프로세스에 캐시한다. 파이썬 코드는 물론
템플릿 변경도 Reload 전에는 반영되지 않는다.

## 브라우저 캐시

정적 파일 링크에 `?v={{ STATIC_BUILD_DATE }}` 가 붙어 있어 Reload 하면
주소가 바뀌므로 보통은 저절로 갱신된다. 그래도 안 보이면 강력 새로고침
(Ctrl+F5).

## 확인

```bash
# 서버가 어느 커밋인지
git log --oneline -1

# 정적 파일이 실제로 올라갔는지 (예시)
ls -la /home/labeldata/mysite/staticfiles/css/list_common.css
```

## 마이그레이션

이 저장소는 마이그레이션 그래프가 정리되기 전이라 `migrate` 를 돌리지 않는다.
DB 인덱스가 필요하면 관리 명령으로 만든다.

```bash
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py ensure_search_indexes
```

정기 배치 등록은 `PYTHONANYWHERE_SCHEDULED_TASK_SETUP.md` 참고.
