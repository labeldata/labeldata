# Welcome to your organization's demo respository
This code repository (or "repo") is designed to demonstrate the best GitHub has to offer with the least amount of noise.

The repo includes an `index.html` file (so it can render a web page), two GitHub Actions workflows, and a CSS stylesheet dependency.

project/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
├── user_management/
│   ├── views.py
│   ├── urls.py
│   ├── templates/
│       ├── user_management/signup.html
│       ├── user_management/login.html
├── action/
│   ├── admin.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
├── label/
│   ├── admin.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── templates/
│       ├── label/post_list.html
│       ├── label/food_item_detail.html
├── main/
│   ├── views.py
│   ├── urls.py
│   ├── templates/
│       ├── main/home.html
└── common/
    ├── models.py
    ├── utils.py


templates/
├── base.html               # 프로젝트 전역에서 사용하는 기본 템플릿
├── includes/               # 공통적으로 포함되는 템플릿 요소
│   ├── messages.html
│   ├── navbar.html
│   ├── pagination.html
├── main/                   # main 앱 관련 템플릿
│   ├── home.html
│   ├── food_item_detail.html
├── action/                 # action 앱 관련 템플릿
│   ├── action_confirm_delete.html
│   ├── action_form.html
│   ├── action_list.html
│   ├── action_detail.html
├── user_management/        # user_management 앱 관련 템플릿
│   ├── login.html
│   ├── signup.html
├── label/                  # label 앱 관련 템플릿
│   ├── food_item_list.html
│   ├── post_detail.html
│   ├── post_form.html
│   ├── post_list.html
├── admin/                  # 관리자 페이지 관련 템플릿
│   ├── change_list.html

git status # 현재 상태 확인
git add 파일명 or . # 파일 추가
git commit -m "커밋 메시지" #커밋 생성
git push origin main # 원격 저장소 푸시


작업 계획(1.19)
○ 1/25 오전 9시 ~30분 리뷰

1. 메인페이지 : 추후 확정
2. 제품 목록
   1) 리스트가 조회 안됨 -> fooditem 모델 수정(항목 추가 : 제품명, 업소명, 유형, 유통/소비기한, 최종수정일자 등) 및 리스트 연결
   2) 하단 페이지번호 조회 기준 변경 -> 10개씩, 현재 위치 표시 등
   3) 제품 상세보기 페이지 -> 추가 -> 내 표시사항 작성 기능으로 연결
3. 표시사항 등록
   1) label model 필요정보 상세히 설계
4. 행정처분 크롤링 기능 상세화 - 서초구
   1) 조회화면 생성, 검색 기능 설계(메인 화면)
 2) 지자체url 등록, 크롤링 항목을 개별 관리하는 메뉴