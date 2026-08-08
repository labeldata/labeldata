# 법령 개정 모니터링 기능 이식 계획

> 작성 기준: 2026-08-06
> 소스: Google AI Studio로 제작한 Node/TS 기반 "법규 API 모니터링" 프로토타입
> 대상: `labeldata` Django 백엔드 (`v1/regulatory/` 앱)
> 상태: 계획 단계 (구현 착수 전) — 1번(API 키), 9번(알림 정책) 결정 필요

---

## 목차

1. [배경 및 목적](#1-배경-및-목적)
2. [소스 앱(프로토타입) 구조 분석](#2-소스-앱프로토타입-구조-분석)
3. [기존 labeldata 파이프라인과의 관계](#3-기존-labeldata-파이프라인과의-관계)
4. [국가법령정보 Open API 연동 사양](#4-국가법령정보-open-api-연동-사양)
5. [Django 데이터 모델 설계](#5-django-데이터-모델-설계)
6. [수집기(collector) 설계](#6-수집기collector-설계)
7. [변경 감지 로직 (해시 비교)](#7-변경-감지-로직-해시-비교)
8. [초기 감시 대상 카테고리 (시드 데이터)](#8-초기-감시-대상-카테고리-시드-데이터)
9. [알림/매칭 정책 — 결정 필요](#9-알림매칭-정책--결정-필요)
10. [UI 설계](#10-ui-설계)
11. [마이그레이션 및 배포 안전 수칙](#11-마이그레이션-및-배포-안전-수칙)
12. [단계별 실행 로드맵](#12-단계별-실행-로드맵)
13. [리스크 및 미결정 사항](#13-리스크-및-미결정-사항)
14. [부록: 제품설명서 자동화(GAS) 기능 자체 사이트 이식 검토](#14-부록-제품설명서-자동화gas-기능-자체-사이트-이식-검토)

---

## 1. 배경 및 목적

사용자가 Google AI Studio에서 국가법령정보 Open API를 연동해 "식품 관련 법령/고시의 개정 여부를 자동 감시"하는 프로토타입(Node/TS, 파일 기반 JSON DB)을 만들었다. 이를 `labeldata`의 기존 규제 모니터링 시스템(`v1/regulatory/`, 부적합·처분·수거검사 등을 이미 수집·매칭·푸시하는 파이프라인)에 통합해, **법령/고시 개정 사실도 같은 방식으로 수집 → 감지 → 알림**되도록 만드는 것이 목표다.

핵심 가치: 사용자가 등록한 제품/원료와 관련된 법령이 바뀌면(예: 표시기준 개정, 소비기한 설정기준 변경) 놓치지 않고 알 수 있게 한다.

---

## 2. 소스 앱(프로토타입) 구조 분석

### 2-1. 기술 스택

- Node.js + TypeScript
- **파일 기반 JSON DB** (`data/law_monitor_db.json`) — `Repository` 클래스가 read/write 전담, 메모리 캐시 병행
- 프론트엔드는 미확인 (백엔드/데이터 계층만 전달받음)

### 2-2. 데이터 스키마 (`DatabaseSchema`)

```ts
{
  categories: MonitoredCategory[];       // 감시 대상 법령/행정규칙 목록
  snapshots: Record<string, SnapshotItem>; // stableId → 최신 스냅샷
  changeHistory: ChangeHistory[];        // 개정 감지 이력
  executionLogs: ExecutionLog[];         // 실행 로그
  notifications: NotificationItem[];     // 알림 큐
  meta: { lastChecked, isFirstRun, lastCheckStatus, lastErrorCount, lawApiOc };
}
```

- **`categories`**: 법률 7개(`L...`) + 행정규칙/고시 7개(`A...`) = 총 14개 카테고리. 각 카테고리는 법제처가 부여한 **분류코드(`vcode`)**를 키로 가짐.
- **`snapshots`**: 카테고리별로 여러 개의 "법령 단위"(법률/시행령/시행규칙 각각 별도)가 `stableId`(예: `LAW_10891_ACT`, `LAW_10891_DECREE`, `LAW_10891_RULE`)로 나뉘어 저장됨. 즉 카테고리 1개가 실제로는 3~10개의 개별 법령/고시를 포함.
- **변경 감지의 핵심**: `dataHash`(SHA-256) — `stableId + revisionId + 법령명 + 공포일자 + 시행일자 + 제개정구분 + 개정문내용 + 제개정이유내용`을 이어붙여 해시. 재조회 시 이 해시가 다르면 "개정 발생"으로 판단.

### 2-3. `computeHash()` 로직

```ts
function computeHash(record: any): string {
  const payload = [
    record.stableId, record.revisionId,
    record.법령명_한글 || record.법령명,
    record.공포일자, record.시행일자, record.제개정구분,
    record.개정문내용 || "", record.제개정이유내용 || "",
  ].join("||");
  return crypto.createHash("sha256").update(payload).digest("hex");
}
```

### 2-4. `LawApiClient` — 실제 API 호출기

- **Base URL**: `https://www.law.go.kr`
- **인증**: `OC` 파라미터 (law.go.kr 회원가입 시 사용하는 **이메일 ID**, 별도 API 키 발급 절차 없음). 환경변수(`LAW_API_OC`) 우선, 없으면 DB(`meta.lawApiOc`) 사용.
- **목록 조회**: `GET /DRF/lawSearch.do?target={couseLs|couseAdmrul}&vcode={분류코드}&display=100&page=N&type=JSON&OC={oc}`
  - `couseLs`: 법률 목록 (L코드)
  - `couseAdmrul`: 행정규칙/고시 목록 (A코드)
  - 페이지네이션 지원 (최대 5페이지 = 500건까지만 순회)
- **상세 조회**: `GET /DRF/lawService.do?target={law|admrul}&MST={mst}&OC={oc}` — 목록 API엔 **개정문내용/제개정이유내용이 없어서**, 이 상세 API를 별도 호출해야 채워짐 (2단계 호출 구조).
- **재시도**: HTTP 429/5xx 시 `[1000ms, 3000ms]` 지수 백오프, 최대 2회 재시도, 요청당 8초 타임아웃.
- **Graceful Fallback**: OC 미설정이거나 API 호출 실패 시 **내장 샘플 데이터**(`SAMPLE_LAW_RECORDS`, `INITIAL_BASELINE_SNAPSHOTS`)로 대체 — 데모/개발 환경에서도 동작하게 하는 설계. *(labeldata 이식 시엔 이 fallback은 불필요 — 운영 환경이므로 API 실패 시 그냥 스킵하고 로그만 남기면 됨)*
- **진단 기능**: `runDiagnostics()` — OC 설정 여부, L코드/A코드 각 1건 실제 조회 테스트를 순차 실행해 결과 리포트.

### 2-5. `repository.ts` — 저장 계층

- 최초 실행 시 `DEFAULT_CATEGORIES`(14개) + `createBaselineSnapshots()`(시드 스냅샷)로 DB 파일 초기화.
- 기존 DB 로드 시, 코드에 정의된 `DEFAULT_CATEGORIES`/베이스라인과 diff 검사해서 누락된 카테고리·스냅샷을 자동 보강(sync).
- `updateCategoryStatus()`: 카테고리별 마지막 조회 상태(정상/오류), 조회 시각, 건수, 에러 메시지 기록.
- `addChangeHistory()`: `(stableId, currentRevisionId, changeType)` 조합 중복 방지 후 이력 추가.

---

## 3. 기존 labeldata 파이프라인과의 관계

`REGULATORY_SYSTEM_ANALYSIS.md`에 정리된 기존 흐름:

```
[공공 API/크롤링] → collector.py → RegulatoryNews (DB)
                                        │
                                  ai_parser.py (GPT-4o-mini)
                                        │
                                   matcher.py (BOM/원료/제품/업체 매칭)
                                        │
                        NewsProductMatch / NewsIngredientMatch / InspectionMatch
                                        │
                                 push_service.py (FCM)
```

법령 개정 모니터링은 이 파이프라인에서 **수집~감지까지는 거의 동일한 패턴**(수거검사 `InspectionResult`와 구조적으로 가장 유사 — "원본 데이터 저장 + 변경분 감지 + 매칭 + 알림"), 다만 **AI 파싱 단계는 불필요**(법제처 API가 이미 구조화된 개정문/이유를 제공하므로) 하고, **매칭 로직은 새로 설계**해야 한다(법령은 BOM 원료 단위가 아니라 "카테고리/식품유형" 단위로 걸림).

| 대응 관계 | 기존 | 법령 모니터링 |
|---|---|---|
| 원본 저장 | `InspectionResult` | `LawRevision` (신규) |
| 변경 감지 | `jdgmnt_cd_nm` 변경 비교 | `data_hash` 비교 (이식) |
| 매칭 결과 | `InspectionMatch` | `LawRevisionMatch` (신규, 설계 필요) |
| 알림 발송 | `push_service.py` 재사용 | 재사용 |
| AI 파싱 | `ai_parser.py` | **불필요** (구조화 데이터 이미 제공) |

---

## 4. 국가법령정보 Open API 연동 사양

### 인증

- `OC` 파라미터 = law.go.kr 회원가입 이메일 ID (예: `example@email.com` → `OC=example`)
- **무료, 별도 심사 없음.** `settings.py`에 추가:
  ```python
  LAW_API_OC = config('LAW_API_OC', default='')
  ```
  `.env`에 `LAW_API_OC=<이메일ID>` 설정.

### 엔드포인트

| 용도 | Method | URL | 필수 파라미터 |
|---|---|---|---|
| 법률 목록 | GET | `/DRF/lawSearch.do` | `target=couseLs`, `vcode`, `OC`, `type=JSON`, `display`, `page` |
| 행정규칙 목록 | GET | `/DRF/lawSearch.do` | `target=couseAdmrul`, `vcode`, `OC`, `type=JSON`, `display`, `page` |
| 법률 상세(개정문 포함) | GET | `/DRF/lawService.do` | `target=law`, `MST`, `OC` |
| 행정규칙 상세 | GET | `/DRF/lawService.do` | `target=admrul`, `ID`, `OC` |

### 응답 필드 매핑 (목록 API)

| 법제처 필드 | 의미 | 우리 모델 필드 |
|---|---|---|
| `법령ID`/`행정규칙ID` | 고정 식별자 | `stable_id` |
| `법령일련번호`(MST)/`행정규칙일련번호` | 개정판 식별자 | `revision_id` |
| `법령명한글`/`행정규칙명` | 명칭 | `law_name` |
| `공포일자`/`발령일자` | 공포일 | `promulgated_date` |
| `시행일자` | 시행일 | `enforced_date` |
| `제개정구분명` | 제/개정 구분 | `revision_type` |
| `법령구분명`/`행정규칙구분명` | 법률/시행령/고시 등 | `law_kind` |
| `소관부처명` | 소관부처 | `dept_name` |
| `법령상세링크`/`행정규칙상세링크` | 상세 URL | `detail_url` |

상세 API(`lawService.do`)에서만 얻을 수 있는 필드: **개정문내용**(`개정문내용`/`개정문`), **제개정이유내용**(`제개정이유내용`/`제개정이유`).

---

## 5. Django 데이터 모델 설계

`v1/regulatory/models.py`에 추가 (기존 `InspectionResult`/`InspectionMatch` 바로 아래 배치 권장):

```python
class LawCategory(models.Model):
    """감시 대상 법령/행정규칙 카테고리 (법제처 분류코드 단위)."""
    LAW = 'LAW'
    ADMIN_RULE = 'ADMIN_RULE'
    TYPE_CHOICES = [(LAW, '법률'), (ADMIN_RULE, '행정규칙/고시')]

    code       = models.CharField(max_length=32, unique=True, verbose_name='분류코드(vcode)')
    name       = models.CharField(max_length=200, verbose_name='카테고리명')
    law_type   = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='구분')
    enabled    = models.BooleanField(default=True, verbose_name='감시 활성화')

    last_checked_at = models.DateTimeField(null=True, blank=True, verbose_name='마지막 조회 시각')
    last_item_count = models.IntegerField(default=0, verbose_name='마지막 조회 건수')
    last_error      = models.TextField(blank=True, verbose_name='마지막 오류')

    class Meta:
        db_table = 'law_category'
        verbose_name = '법령 감시 카테고리'
        verbose_name_plural = '법령 감시 카테고리 목록'

    def __str__(self):
        return f"[{self.get_law_type_display()}] {self.name}"


class LawRevision(models.Model):
    """카테고리 산하 개별 법령/고시의 최신 스냅샷."""
    category = models.ForeignKey(LawCategory, on_delete=models.CASCADE, related_name='revisions')

    stable_id   = models.CharField(max_length=100, verbose_name='법령/행정규칙 고정ID')
    revision_id = models.CharField(max_length=100, verbose_name='개정판 식별자(MST/일련번호)')

    law_name          = models.CharField(max_length=300, verbose_name='법령명')
    law_kind          = models.CharField(max_length=50, blank=True, verbose_name='법종구분')
    dept_name         = models.CharField(max_length=100, blank=True, verbose_name='소관부처명')
    promulgated_date  = models.CharField(max_length=20, blank=True, verbose_name='공포일자')
    enforced_date     = models.CharField(max_length=20, blank=True, verbose_name='시행일자')
    revision_type     = models.CharField(max_length=50, blank=True, verbose_name='제개정구분')
    amendment_content = models.TextField(blank=True, verbose_name='개정문내용')
    amendment_reason  = models.TextField(blank=True, verbose_name='제개정이유내용')
    detail_url        = models.URLField(max_length=500, blank=True, verbose_name='상세링크')

    data_hash = models.CharField(max_length=64, verbose_name='변경감지 해시')

    first_seen_at     = models.DateTimeField(auto_now_add=True, verbose_name='최초 발견')
    last_confirmed_at = models.DateTimeField(auto_now=True, verbose_name='마지막 확인')

    class Meta:
        db_table = 'law_revision'
        verbose_name = '법령 개정 스냅샷'
        verbose_name_plural = '법령 개정 스냅샷 목록'
        constraints = [
            models.UniqueConstraint(fields=['category', 'stable_id'], name='uniq_law_revision'),
        ]
        indexes = [models.Index(fields=['stable_id'])]

    def __str__(self):
        return f"{self.law_name} ({self.revision_id})"


class LawChangeEvent(models.Model):
    """해시 비교로 감지된 개정 이력 (changeHistory 대응)."""
    revision       = models.ForeignKey(LawRevision, on_delete=models.CASCADE, related_name='change_events')
    prev_hash      = models.CharField(max_length=64, blank=True)
    new_hash       = models.CharField(max_length=64)
    prev_revision_id = models.CharField(max_length=100, blank=True)
    detected_at    = models.DateTimeField(auto_now_add=True)
    notified       = models.BooleanField(default=False)

    class Meta:
        db_table = 'law_change_event'
        ordering = ['-detected_at']
        verbose_name = '법령 개정 이력'
        verbose_name_plural = '법령 개정 이력 목록'
```

> `LawRevisionMatch`(사용자 매칭/알림 대상)는 [9. 알림 정책](#9-알림매칭-정책--결정-필요) 결정 후 설계.

---

## 6. 수집기(collector) 설계

`v1/regulatory/services/collector.py`에 함수 추가 (기존 `collect_inspection_data()` 바로 아래 배치).

```python
LAW_API_BASE = 'https://www.law.go.kr/DRF'

def collect_law_revisions(skip_trigger: bool = False) -> dict:
    """활성화된 LawCategory를 순회하며 법제처 API로 개정 여부를 확인하고
    LawRevision을 갱신, 변경분은 LawChangeEvent로 기록한다."""
    from v1.regulatory.models import LawCategory, LawRevision, LawChangeEvent

    oc = getattr(settings, 'LAW_API_OC', '')
    if not oc:
        logger.error('[법령 수집] LAW_API_OC 미설정')
        return {'created': 0, 'updated': 0, 'changed': 0, 'errors': 0}

    counts = {'created': 0, 'updated': 0, 'changed': 0, 'errors': 0}

    for category in LawCategory.objects.filter(enabled=True):
        try:
            items = _fetch_law_category_items(category, oc)
            category.last_item_count = len(items)
            category.last_checked_at = timezone.now()
            category.last_error = ''
        except Exception as exc:
            category.last_error = str(exc)
            counts['errors'] += 1
            logger.error(f'[법령 수집] {category.name} 조회 실패: {exc}')
            category.save(update_fields=['last_error', 'last_checked_at'])
            continue

        for item in items:
            new_hash = _compute_law_hash(item)
            try:
                rev = LawRevision.objects.get(category=category, stable_id=item['stable_id'])
                if rev.data_hash != new_hash:
                    LawChangeEvent.objects.create(
                        revision=rev, prev_hash=rev.data_hash, new_hash=new_hash,
                        prev_revision_id=rev.revision_id,
                    )
                    counts['changed'] += 1
                    if not skip_trigger:
                        _trigger_law_change_notification(rev, item)
                for k, v in item.items():
                    if k != 'stable_id':
                        setattr(rev, k, v)
                rev.data_hash = new_hash
                rev.save()
                counts['updated'] += 1
            except LawRevision.DoesNotExist:
                LawRevision.objects.create(category=category, data_hash=new_hash, **item)
                counts['created'] += 1

        category.save(update_fields=['last_item_count', 'last_checked_at', 'last_error'])

    logger.info(f'[법령 수집] 완료: {counts}')
    return counts


def _fetch_law_category_items(category, oc: str) -> list[dict]:
    """목록 조회 + 상세 조회(개정문/이유) 2단계 호출."""
    target = 'couseLs' if category.law_type == 'LAW' else 'couseAdmrul'
    results = []
    page = 1
    while page <= 5:  # 최대 500건
        resp = requests.get(f'{LAW_API_BASE}/lawSearch.do', params={
            'OC': oc, 'target': target, 'vcode': category.code,
            'display': 100, 'page': page, 'type': 'JSON',
        }, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # couseLs/couseAdmrul 응답 구조 파싱 (키명이 소스마다 다를 수 있어 방어적으로 처리)
        node = data.get('couseLsSearch') or data.get('couseAdmrulSearch') or data
        items = node.get('couseLs') or node.get('couseAdmrul') or []
        if isinstance(items, dict):
            items = [items]
        if not items:
            break

        for raw in items:
            stable_id = raw.get('법령ID') or raw.get('행정규칙ID') or ''
            mst = raw.get('법령일련번호') or raw.get('행정규칙일련번호') or ''
            if not stable_id or not mst:
                continue

            detail = _fetch_law_detail(target, mst, oc)

            results.append({
                'stable_id':         stable_id,
                'revision_id':       mst,
                'law_name':          raw.get('법령명한글') or raw.get('행정규칙명') or '',
                'law_kind':          raw.get('법령구분명') or raw.get('행정규칙구분명') or '',
                'dept_name':         raw.get('소관부처명') or '',
                'promulgated_date':  raw.get('공포일자') or raw.get('발령일자') or '',
                'enforced_date':     raw.get('시행일자') or '',
                'revision_type':     raw.get('제개정구분명') or '',
                'amendment_content': detail.get('text') or '',
                'amendment_reason':  detail.get('reason') or '',
                'detail_url':        raw.get('법령상세링크') or raw.get('행정규칙상세링크') or '',
            })

        total = int(node.get('totalCnt') or 0)
        if page * 100 >= total or len(items) < 100:
            break
        page += 1
        time.sleep(0.3)

    return results


def _fetch_law_detail(target: str, mst: str, oc: str) -> dict:
    """개정문/이유 상세 조회. 실패해도 목록 데이터는 살리기 위해 예외를 삼킨다."""
    try:
        svc_target = 'law' if target == 'couseLs' else 'admrul'
        resp = requests.get(f'{LAW_API_BASE}/lawService.do', params={
            'OC': oc, 'target': svc_target,
            **({'MST': mst} if svc_target == 'law' else {'ID': mst}),
        }, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        node = data.get('LawService') or data.get('AdmrulService') or data
        return {
            'text':   node.get('개정문내용') or node.get('개정문') or '',
            'reason': node.get('제개정이유내용') or node.get('제개정이유') or '',
        }
    except Exception as exc:
        logger.warning(f'[법령 상세] {mst} 조회 실패: {exc}')
        return {'text': '', 'reason': ''}


def _compute_law_hash(item: dict) -> str:
    payload = '||'.join([
        item['stable_id'], item['revision_id'], item['law_name'],
        item['promulgated_date'], item['enforced_date'], item['revision_type'],
        item['amendment_content'], item['amendment_reason'],
    ])
    return hashlib.sha256(payload.encode()).hexdigest()
```

원본 TS의 `computeHash()`와 동일한 필드 조합·순서를 유지해, 나중에 두 시스템 데이터를 비교/검증하기 쉽게 했다.

---

## 7. 변경 감지 로직 (해시 비교)

원본 로직을 그대로 승계:

1. 목록 조회 → 상세 조회로 항목별 8개 필드 확보
2. 필드 조합 → SHA-256 해시
3. `LawRevision.data_hash`와 다르면 `LawChangeEvent` 생성 (개정 발생)
4. `revision_id`(MST)가 바뀌었는지도 `LawChangeEvent.prev_revision_id`에 기록 — 완전히 새 개정판이 나온 것인지, 단순 오탈자 수정인지 구분하는 데 참고

> **오늘 InspectionResult 사고에서 얻은 교훈 적용**: `stable_id`를 카테고리 내에서 unique로 잡되(`category`+`stable_id` 복합), 절대로 `revision_id`(MST) 단독을 키로 쓰지 않는다 — MST도 법제처 내부 일련번호라 이론상 충돌 가능성을 배제할 수 없음.

---

## 8. 초기 감시 대상 카테고리 (시드 데이터)

프로토타입의 `DEFAULT_CATEGORIES` 그대로 이식 (총 14개):

**법률 (7개)**

| 분류코드 | 명칭 |
|---|---|
| L0000000010891 | 식품위생법 |
| L0000000010899 | 축산물위생관리법 |
| L0000000010911 | 식품등의표시광고에관한법률 |
| L0000000010895 | 어린이식생활안전관리특별법 |
| L0000000010903 | 수입식품안전관리특별법 |
| L0000000010915 | 농수산물의원산지표시에관한법률 |
| L0000000010919 | 자원의절약과재활용촉진에관한법률 |

**행정규칙/고시 (7개)**

| 분류코드 | 명칭 |
|---|---|
| A0000000010927 | 식품위생법(고시) — 식품의 기준 및 규격, 첨가물 기준 등 10개 하위 고시 포함 |
| A0000000010931 | 축산물위생관리법(고시) |
| A0000000010935 | 식품등의표시광고에관한법률(고시) — **식품등의 표시기준**(2026.05.12 개정, 2028.01.01 시행) 등 6개 하위 고시 포함 |
| A0000000010943 | 어린이식생활안전관리특별법(고시) |
| A0000000010939 | 수입식품안전관리특별법(고시) |
| A0000000010947 | 자원의절약과재활용촉진에관한법률(고시) |
| A0000000010951 | 농수산물의원산지표시에관한법률(고시) |

초기 마이그레이션 시 `data_migration`으로 `LawCategory` 14건 삽입 (Django `migrations.RunPython` 사용).

---

## 9. 알림/매칭 정책 — 결정 필요

법령 개정은 "제품 1건"이 아니라 "카테고리/식품유형 전체"에 영향을 주므로, 기존 `matcher.py`(BOM 원료 기반 퍼지매칭)를 그대로 쓸 수 없다. 세 가지 안 중 선택 필요:

| 안 | 설명 | 구현 난이도 | 장단점 |
|---|---|---|---|
| **A. 전체 공지형** | 개정 발생 시 전체 사용자에게 알림 (또는 관리자 대시보드에만 표시, 사용자 푸시는 안 함) | 낮음 | 가장 빠르게 배포 가능. 다만 무관한 사용자에게도 노출될 수 있음 |
| **B. 카테고리 구독형** | 사용자가 "표시광고법만 받기"처럼 카테고리 단위 구독 | 중간 | `LawSubscription` 모델 1개 추가로 충분. 사용자 설정 UI 필요 |
| **C. 자동 매칭형** | BOM 원료/식품유형 키워드로 관련 법령만 선별 알림 | 높음 | 가장 정교하지만 "이 법령이 이 원료와 관련있다"는 매핑 규칙을 별도로 설계해야 함 |

**권장**: 1차는 **A(전체 공지형)**으로 빠르게 배포해 데이터 축적·검증하고, 이후 사용자 요청이 쌓이면 **B(구독형)**로 확장. C는 데이터가 충분히 쌓인 뒤 검토.

이 결정에 따라 `LawRevisionMatch`(또는 `LawSubscription`) 모델과 `push_service.py` 연동 함수를 설계.

---

## 10. UI 설계

### 관리자 (Django Admin)

- `LawCategoryAdmin`: on/off 토글, 마지막 조회 상태·건수·오류 표시, "지금 재조회" 커스텀 액션
- `LawRevisionAdmin`: 카테고리별 필터, 최근 개정 순 정렬
- `LawChangeEventAdmin`: 감지된 개정 이력, "알림 발송 여부" 필터

### 사용자 화면

- 기존 `v1/templates/regulatory/news_list.html`에 **"법령 개정"** 탭 추가 (수거검사 탭과 같은 패턴)
- 목록: 법령명 / 제개정구분 / 공포일자 / 시행일자 / 개정문 요약(펼치기) / 상세링크
- 최근 N일 이내 개정만 강조 표시 (기존 부적합 리스트의 "신규" 뱃지 패턴 재사용)

---

## 11. 마이그레이션 및 배포 안전 수칙

오늘(2026-08-06) `InspectionResult` 작업에서 겪은 문제를 이 기능에서 재현하지 않기 위한 체크리스트:

- [ ] **첫 마이그레이션부터 git 추적**: `git add -f v1/regulatory/migrations/00XX_law_monitor_models.py` 즉시 실행, 커밋 누락 없도록
- [ ] **unique key는 외부 재사용 가능성 있는 값 단독으로 걸지 않기**: `stable_id`는 `category`와 묶어서 복합 unique
- [ ] **로컬에서 마이그레이션 만들고 바로 서버에 pull → migrate까지 한 세션에서 검증** (오늘처럼 세션이 끊긴 채 방치하지 않기)
- [ ] **서버에 마이그레이션 적용 전, 항상 `showmigrations`로 그래프 확인** 후 `migrate` 실행
- [ ] 배포 전 **로컬 dev DB와 서버 DB가 다른 마이그레이션 이력을 가질 수 있음을 전제**하고, 서버에서 최종 확인

---

## 12. 단계별 실행 로드맵

| 단계 | 내용 | 산출물 |
|---|---|---|
| 1 | `LAW_API_OC` 확보 및 `settings.py` 반영, 서버에서 API 호출 가능 여부 테스트 (해외 IP 차단 이력 있으므로 사전 확인 필수) | `.env` 설정, 테스트 로그 |
| 2 | 모델 3종(`LawCategory`, `LawRevision`, `LawChangeEvent`) 추가 + 마이그레이션 (git 추적 확실히) | 모델 코드, 마이그레이션 파일 |
| 3 | 카테고리 14개 시드 데이터 삽입 (data migration) | `LawCategory` 14건 |
| 4 | 수집기 함수 3종(`collect_law_revisions`, `_fetch_law_category_items`, `_fetch_law_detail`) 포팅 + `skip_trigger=True`로 1차 전체 수집 테스트 | `collector.py` 변경분 |
| 5 | 관리자 커맨드 추가 (`manage.py collect_law_revisions` 또는 기존 `collect_regulatory_news`에 옵션 추가) + 스케줄 등록 | 커맨드 파일 |
| 6 | Django Admin 화면 구성 | `admin.py` 변경분 |
| 7 | 알림 정책 결정 ([9번](#9-알림매칭-정책--결정-필요)) 후 매칭/푸시 연동 | 정책 문서 + 코드 |
| 8 | 사용자 UI 탭 추가 | 템플릿/뷰 변경분 |
| 9 | 운영 배포 + 실 데이터로 1주일 모니터링 (오탐/누락 확인) | 배포 로그 |

---

## 13. 리스크 및 미결정 사항

- **API 접근성**: `REGULATORY_SYSTEM_ANALYSIS.md`에 "PythonAnywhere 해외 IP 일부 API 접근 제한" 기록이 있음 — law.go.kr이 여기 해당하는지 사전 확인 필요. 막혀 있으면 로컬(국내 IP) 실행 후 결과만 업로드하는 우회 방식(기존 시스템에 이미 있는 패턴)을 재사용해야 함.
- **상세 API 호출량**: 카테고리당 최대 100건 × 카테고리 14개 = 최대 1,400건, 각 건마다 상세 API 1회 추가 호출 → 총 최대 2,800회 API 호출. law.go.kr Open API에 별도 쿼터 제한이 있는지 확인 필요 (식약처 오픈API처럼 일일 쿼터가 있을 수 있음 — 오늘 겪은 `INFO-300` 사례 참고).
- **알림 정책 미결정**: 9번 항목, 사용자 결정 필요.
- **`법령등의 표시기준` 같은 장기 유예 항목 처리**: 시행일자가 공포일자보다 훨씬 뒤(예: 2026.05.12 개정 → 2028.01.01 시행)인 경우가 있음 — 알림 시 "지금 당장 적용" vs "예정" 구분 표시가 필요해 보임 (UI 설계에 반영 권장).

---

*문의: 이 문서는 계획 단계이며, 1번(API 키 확보 여부)과 9번(알림 정책) 결정 후 실제 구현에 착수한다.*

---

## 14. 부록: 제품설명서 자동화(GAS) 기능 자체 사이트 이식 검토

> 작성 기준: 2026-08-08
> 소스: 사용자가 구글 스프레드시트(GAS, `Code.gs`)로 운영 중인 "제품설명서 자동화 시스템"
> 상태: 검토 단계 (구현 미착수) — 나중에 필요할 때 개발 참고용

법령 모니터링과 직접 관련은 없지만, **식약처 OpenAPI를 외부(GAS)가 직접 호출하는 구조가 불안정하다는 문제의식이 동일**하고 우리 서버가 대신 데이터를 제공하는 방향으로 이미 첫 단계(품목제조보고 export API)를 진행했기에, 후속 개발 검토사항을 이 문서에 함께 남긴다.

### 14-1. 배경

GAS 스프레드시트가 하는 일:

1. **문서관리대장** — 품목 목록을 시트 행으로 관리 (No, ERP코드, 품목제조보고번호, 제품명, 식품유형, 제조라인, 보관유형, 알레르기, 작성자, 작성일, 상태, 성상, 보고일/변경일, 소비기한, 포장재질, 제품용도, 원재료명, 포장단위/방법, 보관/유통/섭취방법, 관리번호)
2. **기준정보 마스터** — 완제품규격(식품유형/제조라인별 검사항목·규격·주기), 공통항목(보관유형별 소비기한/보관방법/유통방법/섭취방법 템플릿, 포장재질·제품용도·표시사항 등 선택지), 작성자, 회사코드
3. **신규 작성 다이얼로그** — 품목제조보고번호 입력 → 식약처 API(C002/I1250, 축산물은 C006/I1310) 조회 → 제품명·식품유형·원재료·보고일 등 자동 채움 → 기준정보 프리셋(식품유형/라인/보관유형/알레르기) 선택
4. **제품설명서 시트 생성** — 위 데이터를 정해진 셀 서식·병합 양식에 채워 넣고 대장에 등록
5. **PDF 저장 / 전체 재조회(변경감지) / 선택 항목 일괄생성**

핵심 불편: 식약처 OpenAPI(I1250 등)는 별도 서비스 신청이 필요하거나 응답이 불안정해서, GAS가 매번 직접 호출하면 실패율이 높다.

### 14-2. 1단계 진행 상황 (완료)

`v1/products/views.py: product_export_api` — `GET /products/api/export/?report_no=...`

- 우리 DB(`MyLabel`)에 이미 저장된 라벨 데이터를 기준으로, 계정 구분 없이 `prdlst_report_no` 일치 + 최신 수정본 1건을 JSON으로 반환
- 인증은 수거검사 export API와 동일한 `X-Api-Key`(`settings.INSPECTION_EXPORT_API_KEY`) 공유
- 반환 필드: `report_no, prdt_nm, food_type, bssh_name, sobigihan, packaging, rawmtrl_nm, storage_method, allergens, updated_datetime`
- **한계**: `MyLabel`에 없는 필드(성상/제품용도/품목제조보고일/품목제조변경일)는 응답에서 제외됨. 우리 DB에 등록되지 않은 신규 품목은 조회 불가(식약처 API처럼 임의 보고번호를 즉석 조회하지 못함)

### 14-3. 완전 이식 시 항목별 난이도

| GAS 항목 | 이식 방식 | 난이도 |
|---|---|---|
| 1. 문서관리대장 | 이미 `products` 앱(제품 탐색기/폴더/상태)이 사실상 동일 역할 — 신규 개발 불필요, 컬럼 보강 정도 | 낮음 |
| 2. 기준정보 마스터 | 신규 모델 필요: `QualitySpec`(완제품규격, 식품유형/라인 Key), `StorageTemplate`(보관유형별 템플릿), `CommonItem`(포장재질·용도·표시사항 등 선택지) | 중간 |
| 3. 신규 작성 다이얼로그 | `product_export_api` 호출하는 프론트 모달/폼으로 대체 가능하나, 신규(미등록) 품목은 지원 불가 — 별도 정책 필요 | 중간 |
| 4. 제품설명서 시트(문서 생성) | 스프레드시트 셀 서식을 그대로 옮기기보다 **PDF/HTML 템플릿 기반 문서 생성**으로 재설계 권장 (`ProductDocument` 모델·기존 PDF 렌더링 인프라 재사용) | 높음 — 사실상 신규 기능 |
| 5. PDF 저장/재조회/일괄생성 | 4번을 문서 생성 방식으로 바꾸면 PDF 저장은 자동 해결. 재조회(변경감지)는 원본이 우리 DB이므로 대부분 불필요 | 낮음~중간 |

### 14-4. 미해결 이슈

- **누락 필드 4종**: 성상(`appearance`/`DISPOS`), 제품용도(`usage`/`USAGE`), 품목제조보고일(`reportDate`/`PRMS_DT`), 품목제조변경일(`changeDate`/`CHNG_DT`). `MyLabel`에 컬럼을 추가해 사용자가 직접 입력하게 하거나, 최초 등록 시 식약처 API로 1회 백필하는 방식 검토 필요.
- **미등록 품목 조회**: 우리 DB에 없는 보고번호는 지금 구조로는 응답 불가. "우리 사이트에도 없으면 식약처 API로 폴백" 같은 하이브리드 방식을 쓸지, 아니면 신규 품목은 반드시 우리 사이트에 먼저 라벨을 등록하게 강제할지 정책 결정 필요.
- **기준정보 마스터 스키마 확정**: `QualitySpec`(생물학적/화학적 vs 물리적, 식품유형 Key vs 라인 Key 이원 구조), `StorageTemplate`(보관유형별 소비기한/보관/유통/섭취방법 템플릿 문구) 필드 설계를 실제 착수 시점에 다시 검토.
- **문서 생성 방식**: 스프레드시트 시트 복제 방식을 그대로 유지할지, PDF 템플릿 생성으로 전환할지 — 사용자(작성자) 워크플로우 선호도 확인 필요.

### 14-5. 제안 로드맵 (착수 시)

1. (완료) 품목제조보고 export API
2. 기준정보 마스터를 Django 모델로 이전 + 관리 화면
3. "제품설명서" 문서 타입을 `DocumentType`에 등록, 라벨 데이터 + 기준정보 조합해 PDF 생성하는 뷰 추가
4. 문서관리대장 역할은 기존 제품 탐색기 목록에 상태/작성자 컬럼 보강으로 대체
5. 누락 필드 4종 처리 정책 확정 후 `MyLabel` 컬럼 추가 여부 결정
