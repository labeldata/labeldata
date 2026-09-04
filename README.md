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

작업 문서는 **저장소에 넣지 않는다.** 서버가 `main` 을 그대로 받아 가는 방식
이라, 계획·현황 문서까지 운영 서버에 실릴 이유가 없다. 개발 PC 에만 둔다
(`.gitignore` 에 이름이 적혀 있다).

| 문서 | 언제 보나 |
|---|---|
| `PROJECT_DESIGN.md` | 시스템 전체 구조. 앱이 어떻게 나뉘고 무엇이 어디 있는지 |
| `LABEL_WORKFLOW_PLAN.md` | 표시사항 업무 흐름 — 개선 항목, 남은 것, 작업 기록 |
| `OCR_UPGRADE_PLAN.md` | **사진·문서 판독(OCR/VLM) 의 유일한 기준.** 방식·측정 기록·다음 작업 |
| `DEPLOY.md` | 서버 운영 — 배포 절차, 정기 배치, 빠뜨렸을 때의 증상 |
| `LAW_MONITOR_INTEGRATION_PLAN.md` | 법령 개정 모니터링 이식 계획 (**미착수**) |
| `REFACTORING_PLAN.md` | 프런트엔드 리팩토링 계획 (Phase 4 JS **미착수**) |

옛 문서는 `git log --follow -- <파일명>` 으로 꺼낼 수 있다. 저장소에서 뺀
날까지의 내용이 이력에 남아 있다 — `LABEL_IMPROVEMENT_STATUS.md`(2026-09-05
닫음, 살아 있던 항목은 `LABEL_WORKFLOW_PLAN.md` 로 옮김),
`ocr_system_design.md`(`OCR_UPGRADE_PLAN.md` 부록 A).

### 문서를 늘리기 전에

같은 주제의 문서가 둘이 되면 **어느 날 한쪽만 고쳐진다.** 실제로 그랬다 —
판독 관련 문서가 둘이었고, 채택하지 않은 설계안이 1,068줄로 남아 현재 기준인
척했다. 표시사항 쪽도 현황 문서와 계획 문서가 갈려 있다가 한쪽만 늙었다.

새 문서를 만들기 전에 **위 여섯 개 중 어디에 들어갈 내용인지** 먼저 보라.
