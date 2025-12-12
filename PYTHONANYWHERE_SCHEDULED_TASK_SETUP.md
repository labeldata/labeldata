# PythonAnywhere 서버 - 미인증 계정 자동 삭제 설정 가이드

## 개요
가입 후 48시간 이내에 이메일 인증을 하지 않은 계정을 자동으로 삭제하는 배치 작업입니다.

## 삭제 기준
- **기본 기준**: 가입 후 48시간(2일)
- **삭제 대상**: `is_active=False`이고 `email_verification_sent_at`이 48시간 이전인 계정
- **실행 시간**: 매일 오전 1시 권장

---

## PythonAnywhere 설정 방법

### 1. 파일 업로드
다음 파일들을 PythonAnywhere 서버에 업로드:
- `v1/user_management/management/commands/delete_unverified_accounts.py`
- `delete_unverified_accounts.sh`

### 2. Bash 스크립트 수정
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

### 3. 실행 권한 부여
```bash
chmod +x /home/YOUR_USERNAME/labeldata/delete_unverified_accounts.sh
```

### 4. 테스트 실행 (Dry-run)
실제 삭제하지 않고 대상만 확인:

```bash
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py delete_unverified_accounts --dry-run
```

### 5. PythonAnywhere Scheduled Tasks 등록

#### 방법 A: 웹 대시보드에서 등록 (권장)

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

#### 방법 B: 직접 Python 명령 사용

대시보드 Tasks에서:
```bash
cd /home/YOUR_USERNAME/labeldata && source venv/bin/activate && python manage.py delete_unverified_accounts
```

### 6. 로그 기록 설정 (선택사항)

로그 디렉토리 생성:
```bash
mkdir -p /home/YOUR_USERNAME/labeldata/logs
```

Scheduled Task 명령을 다음과 같이 수정:
```bash
cd /home/YOUR_USERNAME/labeldata && source venv/bin/activate && python manage.py delete_unverified_accounts >> logs/delete_unverified_$(date +\%Y\%m\%d).log 2>&1
```

---

## 수동 실행 및 테스트

### SSH/Bash 콘솔에서 실행

#### 1. Dry-run (안전 테스트)
```bash
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py delete_unverified_accounts --dry-run
```

#### 2. 실제 삭제 실행
```bash
cd /home/YOUR_USERNAME/labeldata
source venv/bin/activate
python manage.py delete_unverified_accounts
```

#### 3. 다른 시간 기준으로 실행 (예: 24시간)
```bash
python manage.py delete_unverified_accounts --hours 24 --dry-run
```

---

## PythonAnywhere 제약사항

### 무료 계정
- **Scheduled Tasks**: 1개만 사용 가능
- 이미 다른 스케줄 작업이 있다면 하나의 스크립트로 통합 필요

### 통합 스크립트 예시
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

## 모니터링 및 확인

### 1. 로그 확인
```bash
# 최근 로그 확인
tail -f /home/YOUR_USERNAME/labeldata/logs/delete_unverified_$(date +\%Y\%m\%d).log

# 전체 로그 보기
cat /home/YOUR_USERNAME/labeldata/logs/delete_unverified_*.log
```

### 2. Task 실행 이력 확인
PythonAnywhere 대시보드 > Tasks 탭에서 실행 이력 확인 가능

### 3. 수동 확인
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

## 시간대 설정 확인

### settings.py 확인
```python
# PythonAnywhere는 UTC 기준
TIME_ZONE = 'UTC'  # 또는 'Asia/Seoul'
USE_TZ = True
```

### 한국 시간 기준으로 실행하려면
- UTC 기준: 오전 1시 KST = 오후 4시 전날 UTC
- PythonAnywhere Task에서 Hour를 16(UTC)으로 설정

---

## 문제 해결

### 스크립트가 실행되지 않을 때
1. 실행 권한 확인: `chmod +x delete_unverified_accounts.sh`
2. 경로 확인: 절대 경로 사용
3. 가상환경 경로 확인: `which python` 명령으로 확인

### 로그에 에러가 있을 때
```bash
# 에러 로그 확인
tail -100 /home/YOUR_USERNAME/labeldata/logs/delete_unverified_*.log | grep -i error
```

### Task가 실행 안 될 때
- PythonAnywhere 대시보드 > Tasks에서 상태 확인
- 무료 계정은 1개만 가능 - 기존 Task 확인

---

## 삭제 정책 변경

### 24시간으로 변경
1. 명령어에 `--hours 24` 옵션 추가
2. `signup_done.html` 문구 수정:
   ```html
   <li>가입된 아이디는 가입 후 24시간 이내에 인증이 되지 않을 시 자동 삭제 처리됩니다.</li>
   ```

### 72시간(3일)로 변경
1. 명령어에 `--hours 72` 옵션 추가
2. `signup_done.html` 문구 수정:
   ```html
   <li>가입된 아이디는 가입 후 72시간(3일) 이내에 인증이 되지 않을 시 자동 삭제 처리됩니다.</li>
   ```

---

## 빠른 시작 체크리스트

- [ ] 파일 업로드 완료
- [ ] `delete_unverified_accounts.sh` 사용자명 수정
- [ ] 실행 권한 부여 (`chmod +x`)
- [ ] Dry-run으로 테스트
- [ ] PythonAnywhere Tasks에 등록
- [ ] `signup_done.html` 문구 수정 (48시간)
- [ ] 첫 실행 후 로그 확인

---

## 직접 SQL 쿼리 (비권장)

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
