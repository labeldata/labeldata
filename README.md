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