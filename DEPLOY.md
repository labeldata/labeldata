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

**서버에서 `migrate` 가 다시 돈다** (2026-08-30 복구). 넉 달 동안 막혀 있었다 —
`.gitignore` 가 `migrations/` 를 빼고 있어서 배포된 곳마다 파일 구성이 갈라졌고,
서버에 없는 파일을 의존하는 바람에 그래프조차 만들어지지 않았다.

배포 전에 계획을 먼저 본다. 실행이 아니라 목록만 보여주므로 안전하다.

```bash
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py migrate --plan
```

`No planned migration operations.` 면 적용할 게 없다는 뜻이다. 뭔가 나오면 그게
무엇인지 확인하고 나서 `migrate` 를 돌린다.

상태가 의심스러우면 읽기 전용 진단을 쓴다.

```bash
python manage.py check_migration_state          # 요약
python manage.py check_migration_state --files  # 앱별 파일·기록 이름까지
```

**마이그레이션 파일을 `.gitignore` 에 다시 넣지 말 것.** 그게 이 사고의 원인이었다.
의존 대상이 사라지면 `manage.py check` 가 `migrations.E001` 로 잡는다.

DB 인덱스가 필요하면 관리 명령으로 만든다.

```bash
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py ensure_search_indexes
```

정기 배치 등록은 `PYTHONANYWHERE_SCHEDULED_TASK_SETUP.md` 참고.
