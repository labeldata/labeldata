# 표시사항 개선 작업 현황

최종 갱신: 2026-08-30 · 기준 커밋 `54e3259`

`LABEL_PROCESS_ANALYSIS.md`(2026-08-29, 저장소 밖 문서)의 제안을 코드로 재검증하고
일부를 반영한 결과. **분석 문서의 결론 중 일부는 실제 코드와 달랐고, 그 정정 내용도
여기에 함께 적는다.**

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

현재 36개. 저장소의 기존 회귀 방지 관례는 Django system check
(`v1/common/checks.py`)지만, 이번 건들은 정적 검사로 못 잡는 런타임 동작이라
`TestCase` 를 썼다.

### 검사 대상

| 클래스 | 무엇을 고정하나 |
|---|---|
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
