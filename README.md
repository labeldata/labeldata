# LabelData

식품 표시사항(한글표시사항) 작성·검증·관리 시스템. Django 5.2 / MySQL /
PythonAnywhere.

```bash
python manage.py runserver                                 # 개발
python manage.py test --settings=v1.config.settings_test   # 시험
```

시험은 `settings_test` 로 돌린다 — 운영 DB 계정에 테스트 DB 생성 권한이 없다.

## 배포

```bash
git pull origin main
python manage.py migrate --plan              # 무엇이 도는지 먼저 본다
python manage.py migrate
python manage.py collectstatic --noinput     # 정적 파일이 바뀌었으면 반드시
```

마지막으로 **Web 탭 → Reload**.

## 문서

작업 문서는 **저장소에 둔다.** 예전에는 "운영 서버가 main 을 그대로 받아 가니
계획 문서까지 실릴 이유가 없다" 며 개발 PC 로 내렸는데(2026-09-05), 그렇게 내린
넷이 **그대로 사라졌다** — 개발 PC 에도 없고 git 이력에만 남았다.

    DEPLOY.md 495줄 · LABEL_WORKFLOW_PLAN.md 291줄
    OCR_UPGRADE_PLAN.md 1,649줄 · LAW_MONITOR_INTEGRATION_PLAN.md 562줄

문서가 운영 서버에 몇 킬로바이트 실리는 것보다 **문서가 없어지는 것이 훨씬
비싸다.** 2026-09-11 에 정책을 되돌렸다.

| 문서 | 언제 보나 |
|---|---|
| `IMPROVEMENT_PLAN.md` | **기능 개선의 유일한 기준.** 끝난 것·남은 것·안 하기로 한 것 |
| `README.md` | 이 파일. 어떻게 돌리고 어떻게 올리나 |

옛 문서는 `git log --follow -- <파일명>` 으로 꺼낸다. 저장소에서 뺀 날까지의
내용이 이력에 남아 있다.

| 없어진 문서 | 어디로 |
|---|---|
| `NUTRITION_UX_PLAN.md` | `IMPROVEMENT_PLAN.md` 1·2·5·6 장 |
| `REGULATORY_ALERT_PIPELINE.md` | `IMPROVEMENT_PLAN.md` 4 장 |
| `FOOD_CATEGORY_REFACTORING_DESIGN.md` | **채택되지 않았다.** 3 장에 까닭만 남겼다 |
| `MENU_ANALYSIS.md` | 폐기 — 적혀 있던 "미수정" 버그가 이미 고쳐져 있었다 |
| `REGULATORY_SYSTEM_ANALYSIS.md` | 폐기 — 2025-07 기준. 4 장이 대신한다 |
| `LABEL_IMPROVEMENT_STATUS.md` | 2026-09-05 닫음 |
| `ocr_system_design.md` | 미채택 설계안 |

### 문서를 늘리기 전에

같은 주제의 문서가 둘이 되면 **어느 날 한쪽만 고쳐진다.** 실제로 세 번 그랬다 —
판독 문서가 둘이었고(미채택 설계안 1,068줄이 현재 기준인 척했다), 표시사항 쪽이
현황과 계획으로 갈렸고, 부적합·처분 문서가 2025-07 판과 2026-09 판 둘이었다.

새 문서를 만들기 전에 **`IMPROVEMENT_PLAN.md` 에 들어갈 내용인지** 먼저 보라.
