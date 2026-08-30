# 표시사항 개선 작업 현황

최종 갱신: 2026-08-30 (2차) · 기준 커밋 `73cbca2`

`LABEL_PROCESS_ANALYSIS.md`(2026-08-29, 저장소 밖 문서)의 제안을 코드로 재검증하고
일부를 반영한 결과. **분석 문서의 결론 중 일부는 실제 코드와 달랐고, 그 정정 내용도
여기에 함께 적는다.**

---

## 0. 오늘(2026-08-30) 작업 목록

이날 새로 확인된 두 건(**필수 입력 미검증**, **제품 관리 탭 디자인 편차**)을
기존 목록에 합쳐 우선순위를 다시 매긴 것. 상세는 각 항목이 가리키는 절에 있다.

| # | 작업 | 규모 | 상태 | 절 |
|---|---|---|---|---|
| 1 | **필수 입력 항목 검증** — 비어 있어도 "적합"이 나오는 구멍 | 반나절 | **구현 완료 · 미커밋** | 3장 P4 |
| 2 | 운영 확인 — AI검증 판정 품질(`check_openai --label`) | 30분 | 대기 | 2-1 |
| 3 | 운영 확인 — 수거검사 알림 보존 / 자동저장 / 원재료 순서 | 30분 | 대기 | 2-2~2-4 |
| 4 | **제품 관리 탭 디자인 통일·공간 효율** | 1~2일 | 신규 | 3장 P8 |
| 5 | 식품유형별 필수항목 자동 세팅(B1) — 1번의 근거 보강 | 1일 | 미착수 | 3장 P4-4 |
| 6 | 원료 중복 방지 + 검색 상한 | 반나절 | 미착수 | 3장 P5 |
| 7 | AI 한도 카운터를 캐시 → DB | 반나절 | 미착수 | 3장 P7 |
| 8 | AI 서류 추출 → 원재료 연결 | 3~5일 | 선행결정 대기 | 3장 P6 |
| 9 | 마이그레이션 그래프 복구 ★ | 미정 | 별건 | 4-1 |

1번과 4번이 오늘 새로 들어온 것이다. 1번은 **오탐 위험이 거의 없고 반나절이면
끝나는데 지금 실제로 잘못된 판정을 내고 있어** 목록 맨 위에 둔다.

---

## 1. 완료 (커밋 8개)

| 커밋 | 내용 |
|---|---|
| `03cd6c2` | 라벨 저장 때마다 수거검사 알림을 지우고 푸시를 다시 보내던 문제 |
| `8be1660` | 원재료 팝업이 열릴 때마다 농수축산물 1만 건을 싣던 것을 검색으로 대체 |
| `80f1b20` | 배합비 순서·첨가물 표시명 검사 추가 |
| `4b6f13d` | 없어진 함수를 부르던 V2 동기화 코드 7곳 제거 |
| `64ad289` | 표시사항 작성 화면에 자동저장과 이탈 경고 추가 |
| `c816f12` | 원재료명 순서를 생성기에서 맞추고, 오탐 나던 순서 검사를 걷어냄 |
| `fb281da` | AI검증이 응답을 무한정 기다리다 500 으로 죽던 문제 수정 |
| `54e3259` | 진단 커맨드에 실제 라벨로 전 구간을 재보는 옵션 추가 |

주요 수치:

| | 전 | 후 |
|---|---|---|
| 원재료 팝업 페이지 | 571.9 KB | 86.6 KB |
| 내원료 상세 페이지 | 589.6 KB | 104.3 KB |
| AI검증 OpenAI 호출 | 순차 4회, 타임아웃 없음(최대 30분) | 독립 3개 병렬 + 요약, 20초 상한 |
| AI검증 소요(계측, 호출당 1초 가정) | 4.0초 | 2.02초 |
| 표시사항 회귀 테스트 | 0개 | 36개 |

---

## 2. 운영 확인이 남은 것

배포는 끝났고 `check_openai` 기본 점검도 통과했다(3/3 성공, 평균 1.11초).
아래는 **아직 눈으로 확인하지 않은 항목**이다.

### 2-1. AI검증이 쓸 만한 판정을 내는가 ★

```bash
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py check_openai --label <라벨번호>
```

라벨번호는 편집 화면 URL 의 숫자(`/label/label-creation/123/` → `123`).
항목별 판정·실제 지적 내용·AI 요약이 그대로 출력된다. 웹 요청이 아니라
PythonAnywhere 300초 제한에 걸리지 않는다. 실제 검증 1회라 해당 계정의
일일 사용 횟수를 1회 쓴다.

이 결과에 따라 다음 작업이 갈린다.
- 판정이 쓸 만하다 → 3장 P5 로
- 판정이 엉뚱하다 → 프롬프트·판정 로직 손보기가 먼저
- 4초보다 훨씬 느리다 → 출력에 구간별 시간이 나오므로 그걸 보고 결정

### 2-2. P0 — 수거검사 알림이 보존되는가

화면에 아무것도 드러나지 않아 로그·알림함으로만 확인된다.

1. 알림함에서 기존 알림(특히 부적합 판정 건) 건수를 적어둔다
2. 표시사항 하나를 열어 아무 필드나 바꾸고 저장한다
3. 알림함 새로고침 → **건수와 읽음 상태가 그대로**여야 한다

수정 전에는 이 단계에서 부적합 알림이 사라지고 읽음 표시가 풀렸다.
서버 로그에서 `[I0460 소급]` 이 **안 찍혀야** 정상이다(품목보고번호를 실제로
바꿔 저장할 때만 찍힌다).

```bash
tail -f /var/log/labeldata.pythonanywhere.com.server.log | grep 'I0460 소급'
```

### 2-3. P3 — 자동저장·이탈 경고

| 동작 | 기대 |
|---|---|
| 아무 칸이나 고치고 30초 대기 | 저장 버튼 옆 "자동 저장됨 HH:MM" |
| 고친 뒤 바로 탭 닫기 | 브라우저 이탈 경고 |
| 아무것도 안 고치고 탭 닫기 | 경고 **없음** (더티 체크) |
| 라벨명을 비우고 저장 | "통신오류" 아닌 정상 실패 표시 (500 수정 확인) |

### 2-4. 원재료명 순서 일치

배합비가 들어간 제품에서 **BOM 등록 화면의 원재료명 요약**과 **표시사항 작성
화면의 원재료명(표로입력) 칸**의 원재료 순서가 같아야 한다. 예전에는 달랐다.

---

## 3. 남은 작업

### P4. 필수 입력 항목 검증 — 반나절 (신규, 최우선)

**증상**: 필수 항목이 통째로 비어 있는 표시사항에 AI검증을 돌리면
"검증한 7개 항목 모두 표시 규정에 적합합니다"가 나온다.

**원인**: 검사 함수 7개가 전부 "값이 있을 때만" 본다.

```python
# validation_service.py — 모든 검사가 같은 모양이다
def check_content_weight(label):
    content_weight = (label.content_weight or '').strip()
    if not content_weight:
        return []          # <- 비어 있으면 "문제 없음"
```

`check_farm_seafood_content`(제품명 없으면 `[]`),
`check_allergens`/`check_origin_missing`(원재료명 없으면 `[]`),
`check_recycling_mark`(포장재질 없으면 `[]`) 전부 같다. AI 쪽도 마찬가지로
`REASON_NO_INPUT`이면 `checked=False`가 되고, `run_full_review`가 그 행을
**표에서 아예 지운다**(적합으로 오인되지 않게 하려던 처리인데, 결과적으로
남은 행이 전부 ok 라서 `ok=all(...)` 이 True 가 된다).

즉 **아무것도 입력하지 않은 라벨이 가장 깨끗한 라벨로 판정된다.** 지금
서버·클라이언트 어디에도 "이 항목은 비면 안 된다"는 검사가 한 줄도 없다
(`label_preview.js`의 `validateBasicFields()`도 값이 있을 때만 단위를 본다).

**실측** (로컬 개발 DB, 활성 라벨 45건 — 체크박스는 켜져 있는데 값이 빈 건수):

| 항목 | 건수 | 항목 | 건수 |
|---|---|---|---|
| 소비기한 | 36 | 품목보고번호 | 14 |
| 내용량 | 33 | 포장재질 | 14 |
| 원재료명(표시) | 18 | 주의사항 | 14 |
| 제조원 소재지 | 10 | 식품유형 | 10 |
| 제품명 | 8 | | |

45건 중 최대 36건이 지금도 "적합"을 받을 수 있는 상태다.

#### P4-1. 어느 단계에서 관리할 것인가 — 결론

세 군데 중 **검증 단계(서버 규칙 기반)가 정본**이고, 초기 세팅은 보조,
AI 는 게이트만 건다.

| 단계 | 역할 | 왜 |
|---|---|---|
| 초기 세팅 (식품유형 선택) | *무엇이* 필수인지 결정 | 식품유형이 정해져야 필수 범위가 정해진다. 다만 여기서 막으면 "작성 중 저장"이 불가능해져 자동저장(P3)과 충돌한다 |
| **저장·검증 (서버)** | ***채워졌는지* 판정 — 정본** | 이미 `validate_label()`이 신뢰 경계다. 우회 불가, 무료, 0.01초, AI 불필요 |
| AI검증 | 볼 입력이 없으면 **호출 전 차단** | 빈 라벨은 원래도 OpenAI 를 부르지 않는다(입력이 없어 3개 검사가 조기 반환). 그런데 일일 할당량은 깎였고, 필수 검사가 붙으면 요약용 호출이 새로 생긴다 |

**저장 자체는 막지 않는다.** 표시사항은 여러 번에 나눠 채우는 문서이고
자동저장(`64ad289`)이 이미 들어가 있다. 저장을 막으면 자동저장이 매번
실패한다. 대신 **"완성"과 "적합"을 판정하는 지점에서만** 막는다.

#### P4-2. 무엇을 필수로 볼 것인가 — 근거가 두 개다

| 근거 | 현재 상태 |
|---|---|
| `MyLabel.chckd_*` (체크박스 18개) | 살아 있다. 화면·미리보기가 이걸로 돈다 |
| `FoodType`의 Y/D/N 컬럼 293행 | 데이터는 있는데 **라벨에 반영되는 경로가 끊겨 있다**(B1) |

`label_creation.js:1448`이 `/label/food-type-settings/`를 부르는데 그 URL 이
`v1/label/urls.py`에 없다 -> 404 -> `.catch(console.error)`로 삼켜진다. 그래서
식품유형을 무엇으로 고르든 체크박스는 **모델 기본값**(`chckd_prdlst_dcnm`,
`prdlst_nm`, `content_weight`, `prdlst_report_no`, `frmlc_mtrqlt`, `bssh_nm`,
`pog_daycnt`, `rawmtrl_nm_display`, `cautions` = 기본 'Y')으로만 시작한다.

두 근거는 **서로 어긋난다**(실측):

```
FoodType.cautions        N 288 / D 5      <- 마스터는 주의사항을 필수로 안 본다
MyLabel.chckd_cautions   기본값 'Y'        <- 화면은 필수로 켜 둔다
FoodType.storage_method  N 288 / Y 5
FoodType.pog_daycnt      Y/N/D 가 아니라 텍스트('소비기한', '제조연월일', ...)
```

-> **1차는 `chckd_*`(현행 화면 동작)를 정본으로 삼는다.** `FoodType`은
"Y 인데 체크가 꺼져 있다"를 *안내*하는 데만 쓰고, 켜진 체크를 끄지는 않는다.
마스터를 그대로 필수 근거로 바꾸면 주의사항·보관방법이 조용히 필수에서
빠지는 회귀가 난다.

#### P4-3. 한 일 (구현 완료 · 미커밋)

1. `validation_service.py` — `check_required_fields(label)` 추가, `_CHECKS`
   **맨 앞**에 배치. `chckd_*` 18개를 돌며 `'Y'` 인데 대응 필드가 공백이면
   항목별로 issue 하나씩. 화면 표기는 `MyLabel._meta.get_field().verbose_name`
   을 재사용해 한글 라벨을 두 번 적지 않는다.
   `_LEGAL_BASIS['required_missing']` 추가(법령명 단위 인용, 조항 번호 미특정).
   - 매핑은 `chckd_` 접두어만 떼면 18개 전부 그대로 모델 필드명이다.
     단 화면 쪽 이름과는 다르다 — `chk_manufacturer_info` = `chckd_bssh_nm`
     (5장 B1 주의사항과 같은 함정)
2. `ai_validation_service.py` — `_CATEGORY_LABELS['required_missing']`,
   그리고 **제품명과 원재료명이 둘 다 비면** `check_rate_limit()` 앞에서 조기
   반환. AI 검사 셋이 어차피 전부 `REASON_NO_INPUT` 인 경우라 OpenAI 를 부를
   이유가 없는데도 지금까지 일일 한도가 1회 깎였다. 요약도 새로 뺀
   `deterministic_summary()`(기존 폴백을 함수로 추출)를 써서 OpenAI 를 아예
   부르지 않는다.
   - `ok` 계산과 행 제거 로직은 손대지 않았다. 제거 대상이
     `ingredient_order`/`name_ingredient_match` 둘로 한정돼 있어
     `required_missing` 행은 그대로 남고 `ok=all(...)` 에 반영된다.
3. `ai_rate_limit.py` — `_content_fingerprint()` 에 `chckd_*` 18개와 대응 필드
   18개 추가. **이게 없으면 소비기한을 채우고 다시 검증해도 캐시 TTL(15분)
   동안 "미입력" 결과가 그대로 나온다.**
4. `label/views.py` — `validate_label_server()` 요약 문구가 미입력 건수를 먼저 말한다.
5. 회귀 테스트 15개 추가 — `RequiredFieldTests` 6, `RequiredFieldAiGateTests` 3,
   신규 `v1/products/tests.py` 의 `ConfirmValidationGateTests` 6.
   전체 51개 통과, `manage.py check` 통과.

**표시사항 작성 화면·커맨드는 손대지 않았다.** `showAiValidationModal()` 과
`check_openai --label` 이 `categories`/`ok` 를 그대로 그리므로 새 항목이
자동으로 표시된다.

#### P4-3-1. 확정 단계에서 무엇을 요구하는가

승인 게이트(`products/views.py` 의 `product_update_status`)가 같은
`validate_label()` 을 쓰므로 확정도 함께 걸린다. 다만 **막는 방식이 제품에
검토·승인 역할이 배정돼 있는지에 따라 갈리도록** 고쳤다.

| 이 제품의 담당자 | 확정 시도 시 | 활동 로그 |
|---|---|---|
| 검토자·승인자 배정됨 (`SharePermission.role_code` 가 `REVIEWER`/`APPROVER`, 공유 유효) | 누락 목록을 보여주고 **사유를 받는다** → "사유 남기고 승인" | `override_reason` |
| 배정 없음 (혼자 쓰는 제품) | 누락 목록을 보여주고 **확인만 받는다** → "확인하고 계속" | `override_acknowledged` |

자기가 쓴 것을 자기에게 해명하게 만드는 절차는 값이 없어서 갈랐다. 대신
**어느 쪽이든 첫 요청은 목록을 돌려주고 멈춘다** — 무엇이 빠졌는지 못 본 채로
확정되는 경로는 두지 않는다. 판단은 서버가 한다(`requires_reason` 를 응답에
실어 보내고, 화면은 그에 맞춰 사유 입력칸을 감춘다).

- 비어 있는 필수 항목은 모달에서 나머지 지적과 **따로 묶어** 맨 위에 보여준다
  (성격이 다르다 — 아예 판정이 안 된 칸이다). 이를 위해 `required_missing`
  issue 에 `field` / `field_label` 을 실었다.
- 넘긴 경우 활동 로그에 **어떤 항목을 비운 채 넘겼는지**(`override_missing_required`)
  까지 남긴다. 예전에는 사유 문구만 남았다.
- 만료된 공유의 담당자는 배정된 것으로 보지 않는다(안 그러면 담당자가 사라진
  제품이 영원히 사유를 요구한다).

**운영 영향**: 로컬 활성 라벨 45건이 전부 "확인 필요"로 바뀐다(전에는 이 중
상당수가 "적합"이었다). 담당자가 배정되지 않은 제품은 확인 한 번으로 넘어가므로
확정이 실제로 막히는 건 검토·승인 절차를 쓰는 제품뿐이다.

#### P4-4. 다음 단계 (별건, 1일)

`/label/food-type-settings/` 뷰 구현 = 5장 B1. 이걸 해야 "식품유형상 필수인데
체크가 꺼져 있다"를 말할 수 있다. **착수 전에 5장 B1 절의 함정 3가지**
(존재하지 않는 `chk_` id 4개, `pog_daycnt` 텍스트 분리, `D` 처리)를 먼저 정리할 것.

화면 표시(완성도 %·미입력 배지)는 그 다음이다. 제품 관리 목록이 이미
문서 슬롯으로 같은 UX 를 쓰고 있으므로(`products/views.py`의 `document_stats`
— `filled/total` 비율) 그 패턴을 그대로 가져오면 된다.

### P5. 원료 중복 방지 + 검색 상한 — 반나절

- `search_ingredient_add_row` (`v1/label/views.py`): `icontains` 다중 필터에
  **LIMIT 없음, 정렬 없음**. 넓은 검색어 하나로 전체 행 반환 가능.
  → `order_by(...)[:50]` + 총건수 표기
- `quick_register_ingredient` / `save_ingredients_to_label`: 같은 원료를 매번
  새 `MyIngredient` 로 생성. → `(user, prdlst_nm, prdlst_report_no, prdlst_dcnm)`
  키로 `get_or_create`
- `save_ingredients_to_label` 전체가 **트랜잭션 밖**. relation 을 먼저 전량
  DELETE 하므로 중간 실패 시 원재료가 통째로 날아간다.
  → `transaction.atomic()` (데코레이터 한 줄)

**현재 규모**: MyIngredient 203행, 중복 원료명 그룹 1개.
지금은 거의 발생하지 않지만 트랜잭션 부재는 데이터 유실 위험이라 값이 싸다.
*로컬 개발 DB 기준 수치이므로 운영 건수를 먼저 확인할 것.*

### P6. AI 서류 추출 결과가 원재료로 이어지지 않는 문제 — 3~5일

`document_ai_apply_to_bom` (`v1/products/views.py`)이 만든 BOM 행은
`source_ingredient` 가 비어 있다. `bom_save_api` 의 `LabelIngredientRelation`
동기화는 `source_ingredient` 가 있는 행만 처리하므로, AI 로 뽑은 배합비가
라벨 쪽으로 넘어가지 않는다.

```
ProductBOM(active) 74행, 배합비 56행, source_ingredient 34행
```

`카사타 티라미수` 계열 라벨들이 BOM 에 배합비 5개씩 있는데 relation 엔 0개다.

고치려면 `document_ai_apply_to_bom` 이 `MyIngredient` 를 만들거나 매칭해야
하는데, 이는 원 분석의 **AI-1(서류 → 원재료 표 자동 생성)** 과 같은 작업이다.
`RapidFuzz` 는 이미 의존성에 있고 `v1/regulatory/services/matcher.py` 에서
쓰고 있으나 원료 매칭에는 아직 안 쓴다.

**선행 결정**: OCR 경로가 둘이다. 어느 쪽을 정본으로 할지 먼저 정해야 한다.
- `v1/label/services/ocr_service.py` — 표시사항 이미지
- `v1/products/services/vision_service.py` — 품목제조보고서·원산지증명서

### P7. AI 한도 카운터를 캐시 → DB — 반나절

`ai_rate_limit.py` 의 일일/분당 카운터가 `FileBasedCache` 에 있고
`MAX_ENTRIES: 500` (`v1/config/settings.py`)이다. 항목이 넘치면 컬링으로
카운터가 소멸해 한도가 초기화될 수 있다. 검증 결과 캐시·농수산물 목록 캐시도
같은 500칸을 나눠 쓴다.

**현재 `django_cache` 파일 30개** — 아직 여유가 있어 잠재 위험이다.

---

### P8. 제품 관리 탭 디자인 통일·공간 효율 — 1~2일 (신규)

제품 상세(`products/product_detail.html`)의 탭 7개가 서로 다른 시대의 스타일로
쌓여 있다. **토큰과 공용 버튼 클래스는 이미 있는데 아무도 안 쓴다**는 게 핵심이다.

#### P8-1. 실측

```
공용 버튼 클래스 .v2-action-btn / .v2-action-btn-outline
  (products_common.css:37, :69 — pill, padding 7px 18px, font 13px)
  -> products/ 템플릿 17개 중 사용처는 product_explorer.html 1곳뿐
```

인라인 `style=` 개수:

| 템플릿 | style= | 비고 |
|---|---|---|
| `_tab_basic_info.html` | 124 | 폰트·패딩·라운드를 필드마다 되풀이 |
| `_tab_documents.html` | 73 | 버튼 크기가 여기서 가장 많이 갈린다 |
| `_tab_permissions.html` | 49 | |
| `product_detail.html` | 43 | |
| `_tab_label.html` | 3 | |

**문서함 버튼 — 한 화면에 6가지 크기**:

| 위치 | 클래스 | 실크기 |
|---|---|---|
| `:99` 불러오기 | `btn-sm px-3` + `font-size:13px; radius:4px` | 13px |
| `:102` 업로드 | `btn-sm px-4` + `font-size:13px; radius:4px` | 13px / 패딩만 다름 |
| `:242` 닫기 | `btn-sm rounded-circle` + `28x28 padding:0` | 원형 |
| `:299` 취소 | `btn rounded-pill px-3` | 기본(14px) |
| `:341` 취소 | `btn rounded-pill px-4` | 기본 / 패딩만 다름 |
| `:414` 다운로드 | `btn-xs border` + `font-size:11px; padding:2px 6px` | 11px |
| `:1023` 카드 액션 3개 | `btn-sm w-100 flex-column` + `font-size:10px` | 10px |
| `:1061` 기간 6개 | `btn-sm rounded-pill px-2` + `font-size:11px` | 11px |

라운드도 `4px` / `rounded-pill` / `rounded-circle` / 기본이 섞여 있다.

**기본정보 탭 세로 공간**: 카드가 `p-4`(24px) + 카드마다 `mb-4`(24px),
필드 블록마다 `row g-3 mb-4`, 그 사이에 또 `hr my-3`, 입력칸은
`padding:10px 14px`. 한 행에 필드 2~3개인데 행 간격이 24px 이라
한 화면에 6~8필드밖에 안 들어간다.

#### P8-2. 할 일

1. **`products_common.css`에 크기 3단계를 확정**하고 인라인 style 을 걷어낸다.
   `.v2-action-btn`(13px / 7px 18px)을 기준으로 `--sm`(12px / 5px 12px),
   `--xs`(11px / 3px 8px) 두 개를 추가. 라운드는 pill 하나로 통일하되
   아이콘 전용 원형만 예외로 남긴다.
2. **문서함 8종을 그 3단계로 치환.** 카드 액션의 `font-size:10px`(현행 최소)는
   토큰의 본문 최소치(`--ez-font-size-xs` = 12px)보다 작아 그대로 두면 안 된다.
3. **기본정보 탭 밀도**: `p-4`->`p-3`, 카드 `mb-4`->`mb-3`, 행 간격
   `mb-4`->`mb-3`, 입력 `padding:10px 14px`->`7px 12px`, `hr` 은 카드 경계가
   이미 구분자라 제거. 세로 약 25~30% 축소를 목표로 한다.
4. **반복되는 라벨 스타일**(`font-size:13px; font-weight:500; color:var(--text-secondary)`
   — 기본정보 탭에서만 수십 번)을 `.v2-field-label` 한 클래스로 뺀다.
5. 회귀 방지: `v1/common/checks.py` 에 Django system check 추가 —
   `templates/products/` 안에서 `btn` 과 인라인 `font-size` 가 같이 쓰인 곳을
   경고. (JS 는 `node` 가 없어 실행 검사를 못 하지만 템플릿 정적 검사는 된다)

#### P8-3. 하지 말 것

탭별 레이아웃을 통째로 다시 짜지 않는다. 문서함·권한 탭은 JS 가 innerHTML 로
버튼 마크업을 만들어내는 곳이 많아(`_tab_documents.html:1023` 등) 구조를 건드리면
동작이 깨진다. **클래스 치환과 간격 값 조정까지만** 한다.

## 4. 별건으로 남긴 것

### 4-1. 마이그레이션 그래프가 깨져 있다 ★

**`manage.py migrate` 가 실행 자체가 안 된다.**

```
InconsistentMigrationHistory: user_management.0004_companydocument_linked_document_type
is applied before its dependency products.0002_combined
```

- `regulatory` 앱 리프가 둘로 갈라져 있다
  (`0004_alter_inspectionresult_tkawyprno_and_more`, `0010_remove_false_positive_pattern`)
- `regulatory.0002~0004` 가 **미적용인데 `inspection_result`·`inspection_match`
  테이블은 존재한다** — 스키마가 마이그레이션 밖에서 관리되고 있다

지금 운영에 지장은 없다(`manage.py check` 통과, 런타임 정상). 다만 **신규 배포나
DB 재구축이 불가능하고, 앞으로 모델을 바꿀 때 마이그레이션을 만들 수 없다.**
`DEPLOY.md` 도 "이 저장소는 마이그레이션 그래프가 정리되기 전이라 migrate 를
돌리지 않는다"고 적고 있다.

테스트는 `v1/config/settings_test.py` 에서 마이그레이션을 우회해 돌린다.

### 4-2. UserProfile 저장 시그널의 전량 삭제

`v1/user_management/models.py` 의 `backfill_inspection_on_profile_save` 에도
`InspectionMatch` 전량 삭제가 남아 있다. 회사명·인허가번호가 바뀌면 옛 키워드
기준 매칭을 실제로 지워야 하는 면이 있어 라벨 저장과는 판단이 다르다.
프로필 저장은 빈도도 낮다. 푸시 비동기화만 적용해 뒀다.

---

## 5. 원 분석 문서의 정정

`LABEL_PROCESS_ANALYSIS.md` 를 코드로 검증한 결과 다음이 달랐다.
**다음에 그 문서를 참고할 때 함께 볼 것.**

| 원 분석 | 실제 |
|---|---|
| B2 "최종 표시 문구에 자동화가 하나도 없다" | 생성기가 이미 있다. 향료 번호·혼합제제·정제수·5% 규칙·알레르기/GMO 요약을 적용한다 (`views.py`) |
| B6 "팝업 왕복 중 이탈하면 입력분이 사라진다" | 팝업은 부모를 새로고침하지 않고 `window.opener` 로 값을 써 넣는다. 유실 경로는 **부모 화면을 떠날 때** 하나뿐 |
| B10 "OCR 결과를 `LabelIngredientRelation` 으로 바꾸는 연결부가 없다" | `document_ai_apply_to_bom` 이 `ProductBOM` 까지는 넣는다. 빠진 건 그 다음(3장 P6) |
| B10 "그 칸은 relation 이 있으면 다음 GET 에서 덮어써진다" | 덮어쓰는 건 readonly 파생 필드 `rawmtrl_nm`(참고)이고 의도된 동작. 사용자가 편집하는 `rawmtrl_nm_display` 는 건드리지 않는다 |
| B9 "`auto_fill_api` 가 하드코딩" | 맞지만 더 심하다. 같은 배열이 `recommendation_system.js` 에도 한 벌 더 있다 |
| B1 "26개 체크박스를 매 라벨마다 손으로 켠다" | 새 라벨 기본 체크는 5개. 나머지는 **꺼진 채 시작**한다 — 소비기한·원재료명(최종표시)·포장재질·주의사항 등 |
| 우선순위 2위 "AI-1 최우선" | 선행 결정(OCR 경로 일원화)이 안 끝났고 비용이 크다. 3장 P6 으로 미룸 |

### B1 은 아직 미착수 — 착수 시 주의할 점

`/label/food-type-settings/` 와 `/label/get-food-group/` 는 여전히 없다
(`label_creation.js` 가 호출하고 `.catch(console.error)` 로 삼킨다).
데이터는 완전히 준비돼 있다.

```
FoodType 293행 — frmlc_mtrqlt Y288/D5, country_of_origin Y266/D24/N3,
nutritions Y179/D72/N42, weight_calorie Y178/D97/N18, relevant_regulations 269행
```

다만 **뷰만 만들면 끝나지 않는다.**
- `label_creation.js` 의 `fieldMappings` 4개가 존재하지 않는 id 를 가리킨다:
  `chk_calories`, `chk_ingredients_info`, `chk_weight_calorie`, `chk_manufacturer_info`
  (템플릿엔 각각 없음 / `chk_ingredient_info` / 없음 / `chk_bssh_nm`)
- `FoodType.pog_daycnt` 는 Y/N/D 가 아니라 텍스트다
  (`'소비기한'`, `'제조연월일'`, `'소비기한, 품질유지기한'`).
  JS 는 `pog_daycnt`(Y/N/D)와 `pog_daycnt_options`(배열)를 따로 기대하므로
  뷰에서 갈라 보내야 한다

---

## 6. V2 에서 실제로 쓰이는 화면

작업 범위를 정할 때 참고. 활동로그(`UserActivityLog`) 실측 — **로컬 개발 DB 기준**이라
운영과 다를 수 있다.

```
search_domestic 685 · preview_view 459 · search_additive 330 · search_import 320
label_view 254 · label_write 26 · label_create 19 · label_update 18
bom_view 13 · ingredient_table_input 6 · bom_save 2
```

- **원재료 팝업**(`ingredient_table_input`)은 V2 에서 **BOM 등록 메뉴로 대체**돼
  거의 쓰지 않는다. 이 화면 전용 작업은 값이 낮다
- BOM 워크스페이스는 93.1 KB 로 마스터 페이로드를 애초에 싣지 않았다
- **내원료 상세**는 살아 있다 — `bom_save_api` 가 `MyIngredient` 를 생성·수정한다
- 표시사항 작성 화면(`label_view` 254)이 가장 많이 쓰인다

---

## 7. 테스트

```bash
python manage.py test --settings=v1.config.settings_test
```

운영 DB 계정에 테스트 DB 생성 권한이 없고 마이그레이션 그래프가 깨져 있어,
`v1/config/settings_test.py` 가 메모리 SQLite + 마이그레이션 우회로 돌린다.
운영 `settings.py` 는 건드리지 않았다. **서버에서는 돌리지 않는다.**

현재 51개. 저장소의 기존 회귀 방지 관례는 Django system check
(`v1/common/checks.py`)지만, 이번 건들은 정적 검사로 못 잡는 런타임 동작이라
`TestCase` 를 썼다.

### 검사 대상

| 클래스 | 무엇을 고정하나 |
|---|---|
| `RequiredFieldTests` | 체크는 켜졌는데 값이 빈 항목을 잡는지 / 꺼진 항목은 안 잡는지 |
| `RequiredFieldAiGateTests` | 볼 입력이 없으면 OpenAI 미호출·할당량 미차감, 필수 행이 표에서 안 지워지는지, 체크박스가 캐시 지문에 반영되는지 |
| `ConfirmValidationGateTests` (products) | 확정 직전 게이트가 담당자 유무에 따라 사유/확인 중 무엇을 요구하는지, 넘긴 내용이 활동 로그에 남는지 |
| `InspectionBackfillTriggerTests` | 수거검사 소급 매칭이 언제 도는지 / 무엇을 지우는지 |
| `FoodTypeOptionsApiTests` | 식품유형 검색 API, 겹치는 이름의 판정 순서 |
| `AdditiveDisplayNameCheckTests` | 첨가물 표시명 공란 |
| `ValidateLabelWiringTests` | 검사가 무료 검증 경로에 물려 있는지 |
| `RawmtrlNmOrderTests` | 원재료명 생성이 배합비 내림차순인지 |
| `LabelSavePostTests` | 자동저장이 활동로그를 오염시키지 않는지 / 폼 오류가 500 이 아닌지 |
| `AiValidationFailureTests` | AI 실패 시 타임아웃·사유 전달·규칙 결과 보존 |

`node` 가 없어 JS 는 실행 검사를 못 한다. 문자열·주석·정규식을 걷어낸 뒤
괄호 균형을 변경 전후로 비교하는 방식으로 갈음했다
(원본에도 정규식 리터럴 때문에 오탐이 있어 **전후 비교**로만 의미가 있다).

---

## 8. 배포

`DEPLOY.md` 참고. 이번 작업들은 **정적 파일(JS)이 바뀌므로 `collectstatic` 필수**,
마이그레이션은 없다.

```bash
cd /home/labeldata/mysite
git pull origin main
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py collectstatic --noinput
/home/labeldata/.virtualenvs/mysite-env/bin/python manage.py check
```

이후 Web 탭 → Reload.

되돌리기는 커밋 단위로 가능하다. JS·템플릿이 바뀐 커밋을 되돌릴 때는
`collectstatic` + Reload 가 함께 필요하다.
