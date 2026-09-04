# 서버 운영 (PythonAnywhere)

배포 절차와 정기 배치 작업을 한곳에 둔다.

---

## 배포 절차

서버: `/home/labeldata/mysite` · 가상환경 `/home/labeldata/.virtualenvs/mysite-env`

### 순서

```bash
cd /home/labeldata/mysite
git pull origin main

# 정적 파일(CSS·JS·이미지)이 바뀌었으면 반드시
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py collectstatic --noinput

# 문제 없는지 확인 (템플릿 검사 포함)
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py check
```

마지막으로 **Web 탭 → Reload**.

### `collectstatic` 을 빠뜨리면

`/static/` 은 `STATIC_ROOT`(`/home/labeldata/mysite/staticfiles`)에서 서빙된다.
소스 트리(`v1/static/`)를 직접 보지 않으므로, **CSS·JS 를 고쳐도 pull 만으로는
반영되지 않는다.** 템플릿(HTML)은 소스에서 바로 읽으므로 즉시 반영된다.

그래서 증상이 헷갈린다 — **화면 구조는 바뀌었는데 스타일만 옛날 그대로**이고,
버튼을 눌러도 새로 추가한 JS 동작이 없다. "CSS가 깨졌다" 로 보이지만 실제로는
새 파일이 아직 서버에 없는 것이다.

새 파일을 추가했을 때뿐 아니라 **기존 파일을 고쳤을 때도** 필요하다.

### Reload 를 빠뜨리면

`DEBUG=False` 라 Django 가 템플릿까지 프로세스에 캐시한다. 파이썬 코드는 물론
템플릿 변경도 Reload 전에는 반영되지 않는다.

### 브라우저 캐시

정적 파일 링크에 `?v={{ STATIC_BUILD_DATE }}` 가 붙어 있어 Reload 하면
주소가 바뀌므로 보통은 저절로 갱신된다. 그래도 안 보이면 강력 새로고침
(Ctrl+F5).

### 확인

```bash
# 서버가 어느 커밋인지
git log --oneline -1

# 정적 파일이 실제로 올라갔는지 (예시)
ls -la /home/labeldata/mysite/staticfiles/css/list_common.css
```

### 마이그레이션

**서버에서 `migrate` 가 다시 돈다** (2026-08-30 복구). 넉 달 동안 막혀 있었다 —
`.gitignore` 가 `migrations/` 를 빼고 있어서 배포된 곳마다 파일 구성이 갈라졌고,
서버에 없는 파일을 의존하는 바람에 그래프조차 만들어지지 않았다.

배포 전에 계획을 먼저 본다. 실행이 아니라 목록만 보여주므로 안전하다.

```bash
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py migrate --plan
```

`No planned migration operations.` 면 적용할 게 없다는 뜻이다. 뭔가 나오면 그게
무엇인지 확인하고 나서 `migrate` 를 돌린다.

**마이그레이션 파일을 `.gitignore` 에 다시 넣지 말 것.** 그게 이 사고의 원인이었다.
의존 대상이 사라지면 `manage.py check` 가 `migrations.E001` 로 잡는다.

DB 인덱스가 필요하면 관리 명령으로 만든다.

```bash
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py ensure_search_indexes
```

---

## 정기 배치 작업

---

### 📡 부적합·처분 알림 수집 (collect_regulatory_news)

#### 개요
국내 식품안전나라 OpenAPI + 수입식품정보마루 AJAX를 통해 매일 최신 부적합 정보를 수집하고,
내 제품·원료와 AI 매칭합니다.

#### 스케줄 설정

> ℹ️ **PythonAnywhere Tasks 목록에 표시되는 시각은 UTC 입니다.** KST = UTC + 9시간.

현재 하루 두 번 등록돼 있습니다.

| UTC | KST | 비고 |
|---|---|---|
| 21:00 | 06:00 | 1차 |
| 00:10 | 09:10 | 2차 |

**PythonAnywhere Tasks에 등록된 명령:**
```bash
cd /home/labeldata/mysite && /home/labeldata/.virtualenvs/mysite-env/bin/python manage.py collect_regulatory_news
```

> ⚠️ `--source` 옵션은 2025-03 코드 개편 때 제거되었습니다. 이제 인자 없이 실행하면 모든 소스를 한 번에 수집합니다. (`--source all` 등을 붙이면 argparse 에러로 태스크가 실패합니다.)

**수집 대상:**
- `I2620` — 국내 검사부적합 (식품)
- `I2640` — 국내 검사부적합 (농산물)
- `I0490` — 국내 회수·판매중지
- `I0470` — 국내 행정처분
- `I0480` — 국내 행정처분 (제조가공업)
- `I0482` — 수입판매업 행정처분
- 수입식품정보마루 회수·판매중지 — 로컬 스크립트(`local_uploader/import_scraper.py`)가 올린 `new_import_data.json` 파일이 있으면 자동 반영
- 수입식품정보마루 검사부적합(imp_insp) — 동일 파일에서 자동 반영 (파일 없으면 조용히 스킵)
- 전국 지자체 행정처분 — 로컬 스크립트(`local_uploader/saol_uploader.py`)가 올린 `new_saol_data.json` 파일이 있으면 자동 반영

> ℹ️ 수입 부적합/회수와 지자체 행정처분은 해외 IP 차단 사이트라 서버가 직접 수집하지 못합니다. 한국 IP 로컬 PC에서 위 로컬 스크립트를 실행해 JSON을 서버로 올려야 이 배치가 읽어 DB에 넣습니다. (자세한 내용은 아래 "수입 부적합 로컬 수집" 섹션 참고)

#### 수동 실행

```bash
cd /home/labeldata/mysite
PY=/home/labeldata/.virtualenvs/mysite-env/bin/python

# 전체 수집 + 파싱 + 매칭 (기본)
$PY manage.py collect_regulatory_news

# AI 파싱만 (수집 생략)
$PY manage.py collect_regulatory_news --parse-only

# 매칭만 재실행
$PY manage.py collect_regulatory_news --match-only

# 테스트 (서비스당 100건 제한)
$PY manage.py collect_regulatory_news --limit 100
```

---

### 📊 제품 조회 첫 화면 통계 갱신 (refresh_product_intro)

#### 개요
제품 조회 메뉴를 검색어 없이 열면 나오는 안내 화면(국내/수입 건수 + 많이 등록된 식품유형)의
숫자를 미리 계산해 `data/product_search_intro.json` 에 찍어둡니다.

이 숫자는 `COUNT(*)` 2개 + `GROUP BY` 2개로 만들어져 **행 수에 선형으로 비쌉니다.**
요청 중에 계산하면 그날 처음 메뉴를 누른 사람이 그 비용을 전부 부담해서
"메뉴 최초 클릭이 느리다"는 증상이 생깁니다. 그래서 배치로 옮겼습니다.

품목제조보고는 하루 1회 수집이므로 **하루 지난 숫자로 충분합니다.**
화면에도 `2026-08-26 기준` 처럼 기준일이 함께 표기됩니다.

#### 스케줄 설정

> ℹ️ **PythonAnywhere Tasks 목록에 표시되는 시각은 UTC 입니다.** KST = UTC + 9시간.
> (예: `delete_unverified_accounts` 가 16:00 으로 등록돼 있고, 이는 KST 오전 1시입니다.)

품목보고 수집(`call_api_endpoints`)은 하루 두 번, 아래 순서로 돌고 있습니다.

| UTC | KST | 태스크 |
|---|---|---|
| 15:05 ~ 15:45 | 00:05 ~ 00:45 | `--id 1, 2, 3, 7, 8` (1차) |
| 17:05 ~ 17:45 | **02:05 ~ 02:45** | `--id 1, 2, 3, 7, 8` (2차, **마지막**) |

따라서 통계 갱신은 **마지막 수집(17:45 UTC / 02:45 KST) 뒤**에 돌아야 합니다.

##### 방법 A: 마지막 수집 태스크에 이어붙이기 (권장)

`--id 8` 이 얼마나 걸리는지 몰라도 되고, 순서가 확실히 보장되며, 태스크 슬롯도 쓰지 않습니다.
**17:45 태스크의 명령**을 아래로 바꾸면 됩니다.

```bash
cd /home/labeldata/mysite && /home/labeldata/.virtualenvs/mysite-env/bin/python manage.py call_api_endpoints --id 8 && /home/labeldata/.virtualenvs/mysite-env/bin/python manage.py refresh_product_intro
```

> 수집이 실패하면(`&&` 이므로) 갱신도 건너뜁니다. 이 경우 스냅샷은 전날 값이 하루 더 유지될
> 뿐이라 장애가 아닙니다. 수집 성공 여부와 무관하게 항상 갱신하고 싶으면 `&&` 대신 `;` 를 씁니다.

##### 방법 B: 별도 태스크로 등록

1. PythonAnywhere 대시보드 → **Tasks** 탭
2. **Hour `18`, Minute `30`** (UTC) = KST 오전 3시 30분 — 마지막 수집 시작 후 45분 여유

```bash
cd /home/labeldata/mysite && /home/labeldata/.virtualenvs/mysite-env/bin/python manage.py refresh_product_intro
```

> 수집이 45분 안에 끝나지 않으면 그날 통계는 하루 전 값이 됩니다(다음 날 정상화).
> 수집 소요 시간이 들쭉날쭉하면 방법 A 를 쓰세요.

#### 수동 실행

```bash
cd /home/labeldata/mysite

# 갱신
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py refresh_product_intro

# 계산만 해보고 기록하지 않음
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py refresh_product_intro --dry-run
```

**정상 출력 예시**
```
국내 18,857건 / 수입 22,448건 (집계 0.0초)
  국내 상위 유형: 소스, 포장육, 빵류, 양념육, 기타가공품
  수입 상위 유형: 과자류, 농.임산물가공품, 음료, 면류, 캔디류
스냅샷 기록 완료: /home/labeldata/mysite/data/product_search_intro.json
FULLTEXT 인덱스 캐시 워밍: food_item, imported_food
```

#### 배치를 깜빡했거나 실패하면?

장애로 이어지지 않습니다. 동작은 이렇습니다.

| 상황 | 동작 |
|---|---|
| 스냅샷 파일 있음 (정상) | 파일만 읽음. DB 쿼리 0개, 0.2ms |
| 스냅샷이 낡음 | **다시 계산하지 않음.** 낡은 숫자를 그대로 보여주고 기준일을 표기 |
| 스냅샷 파일 없음 (최초 배포·크론 누락) | 그때 한 번만 계산해 파일로 굳힘. 이후 요청은 정상 속도. `django_errors.log` 에 경고 기록 |

`data/` 디렉터리는 배치가 알아서 만들고, 런타임 생성물이라 `.gitignore` 에 있습니다.

#### 확인 방법

```bash
# 언제 어떤 값이 찍혔는지 바로 보인다
cat /home/labeldata/mysite/data/product_search_intro.json
```

---

### 🗑️ 미인증 계정 자동 삭제 설정 가이드

### 개요
가입 후 48시간 이내에 이메일 인증을 하지 않은 계정을 자동으로 삭제하는 배치 작업입니다.

### 삭제 기준
- **기본 기준**: 가입 후 48시간(2일)
- **삭제 대상**: `is_active=False`이고 `email_verification_sent_at`이 48시간 이전인 계정
- **실행 시간**: 매일 오전 1시 권장

---

### PythonAnywhere 설정 방법

#### 1. 파일 업로드
다음 파일들을 PythonAnywhere 서버에 업로드:
- `v1/user_management/management/commands/delete_unverified_accounts.py`
- `delete_unverified_accounts.sh`

#### 2. Bash 스크립트 수정
`delete_unverified_accounts.sh` 파일을 편집하여 사용자명 수정:

```bash
nano /home/YOUR_USERNAME/labeldata/delete_unverified_accounts.sh
```

**수정 내용:**
```bash
# YOUR_USERNAME을 실제 PythonAnywhere 사용자명으로 변경
cd /home/YOUR_USERNAME/labeldata

# 가상환경 경로도 확인
source venv/bin/activate  # 또는 실제 가상환경 경로
```

#### 3. 실행 권한 부여
```bash
chmod +x /home/YOUR_USERNAME/labeldata/delete_unverified_accounts.sh
```

#### 4. 테스트 실행 (Dry-run)
실제 삭제하지 않고 대상만 확인:

```bash
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py delete_unverified_accounts --dry-run
```

#### 5. PythonAnywhere Scheduled Tasks 등록

##### 방법 A: 웹 대시보드에서 등록 (권장)

1. PythonAnywhere 대시보드 접속
2. **"Tasks"** 탭 클릭
3. **"Create a new scheduled task"** 클릭
4. 다음 정보 입력:
   - **Hour**: `1` (오전 1시)
   - **Minute**: `0`
   - **Command**: 
     ```bash
     /home/YOUR_USERNAME/labeldata/delete_unverified_accounts.sh
     ```
   또는 직접 실행:
     ```bash
     cd /home/YOUR_USERNAME/labeldata && source venv/bin/activate && python manage.py delete_unverified_accounts
     ```
5. **"Create"** 클릭

##### 방법 B: 직접 Python 명령 사용

대시보드 Tasks에서:
```bash
cd /home/YOUR_USERNAME/labeldata && source venv/bin/activate && python manage.py delete_unverified_accounts
```

#### 6. 로그 기록 설정 (선택사항)

로그 디렉토리 생성:
```bash
mkdir -p /home/YOUR_USERNAME/labeldata/logs
```

Scheduled Task 명령을 다음과 같이 수정:
```bash
cd /home/YOUR_USERNAME/labeldata && source venv/bin/activate && python manage.py delete_unverified_accounts >> logs/delete_unverified_$(date +\%Y\%m\%d).log 2>&1
```

---

### 수동 실행 및 테스트

#### SSH/Bash 콘솔에서 실행

##### 1. Dry-run (안전 테스트)
```bash
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py delete_unverified_accounts --dry-run
```

##### 2. 실제 삭제 실행
```bash
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py delete_unverified_accounts
```

##### 3. 다른 시간 기준으로 실행 (예: 24시간)
```bash
python manage.py delete_unverified_accounts --hours 24 --dry-run
```

---

### PythonAnywhere 제약사항

#### 무료 계정
- **Scheduled Tasks**: 1개만 사용 가능
- 이미 다른 스케줄 작업이 있다면 하나의 스크립트로 통합 필요

#### 통합 스크립트 예시
여러 작업을 하나의 스크립트로 통합:

```bash
#!/bin/bash
# daily_tasks.sh

cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate

# 미인증 계정 삭제
python manage.py delete_unverified_accounts

# 다른 정기 작업 추가 가능
# python manage.py other_task
```

---

### 모니터링 및 확인

#### 1. 로그 확인
```bash
# 최근 로그 확인
tail -f /home/YOUR_USERNAME/labeldata/logs/delete_unverified_$(date +\%Y\%m\%d).log

# 전체 로그 보기
cat /home/YOUR_USERNAME/labeldata/logs/delete_unverified_*.log
```

#### 2. Task 실행 이력 확인
PythonAnywhere 대시보드 > Tasks 탭에서 실행 이력 확인 가능

#### 3. 수동 확인
Django shell에서 미인증 계정 확인:
```python
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py shell

>>> from django.contrib.auth.models import User
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> cutoff = timezone.now() - timedelta(hours=48)
>>> User.objects.filter(is_active=False, profile__email_verification_sent_at__lt=cutoff).count()
```

---

### 시간대 설정 확인

#### settings.py 확인
```python
# PythonAnywhere는 UTC 기준
TIME_ZONE = 'UTC'  # 또는 'Asia/Seoul'
USE_TZ = True
```

#### 한국 시간 기준으로 실행하려면
- UTC 기준: 오전 1시 KST = 오후 4시 전날 UTC
- PythonAnywhere Task에서 Hour를 16(UTC)으로 설정

---

### 문제 해결

#### 스크립트가 실행되지 않을 때
1. 실행 권한 확인: `chmod +x delete_unverified_accounts.sh`
2. 경로 확인: 절대 경로 사용
3. 가상환경 경로 확인: `which python` 명령으로 확인

#### 로그에 에러가 있을 때
```bash
# 에러 로그 확인
tail -100 /home/YOUR_USERNAME/labeldata/logs/delete_unverified_*.log | grep -i error
```

#### Task가 실행 안 될 때
- PythonAnywhere 대시보드 > Tasks에서 상태 확인
- 무료 계정은 1개만 가능 - 기존 Task 확인

---

### 삭제 정책 변경

#### 24시간으로 변경
1. 명령어에 `--hours 24` 옵션 추가
2. `signup_done.html` 문구 수정:
   ```html
   <li>가입된 아이디는 가입 후 24시간 이내에 인증이 되지 않을 시 자동 삭제 처리됩니다.</li>
   ```

#### 72시간(3일)로 변경
1. 명령어에 `--hours 72` 옵션 추가
2. `signup_done.html` 문구 수정:
   ```html
   <li>가입된 아이디는 가입 후 72시간(3일) 이내에 인증이 되지 않을 시 자동 삭제 처리됩니다.</li>
   ```

---

### 빠른 시작 체크리스트

- [ ] 파일 업로드 완료
- [ ] `delete_unverified_accounts.sh` 사용자명 수정
- [ ] 실행 권한 부여 (`chmod +x`)
- [ ] Dry-run으로 테스트
- [ ] PythonAnywhere Tasks에 등록
- [ ] `signup_done.html` 문구 수정 (48시간)
- [ ] 첫 실행 후 로그 확인

---

### 직접 SQL 쿼리 (비권장)

**주의**: Django ORM 사용을 권장하지만, 필요 시 참고용:

```sql
-- 삭제 대상 조회
SELECT u.id, u.email, p.email_verification_sent_at
FROM auth_user u
INNER JOIN user_management_userprofile p ON u.id = p.user_id
WHERE u.is_active = 0
  AND p.is_email_verified = 0
  AND p.email_verification_sent_at < NOW() - INTERVAL 48 HOUR;

-- 삭제 (CASCADE로 profile도 자동 삭제)
DELETE u FROM auth_user u
INNER JOIN user_management_userprofile p ON u.id = p.user_id
WHERE u.is_active = 0
  AND p.is_email_verified = 0
  AND p.email_verification_sent_at < NOW() - INTERVAL 48 HOUR;
```

**Django ORM이 더 안전하므로 관리 명령 사용을 권장합니다.**
