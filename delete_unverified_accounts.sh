#!/bin/bash
# PythonAnywhere용 미인증 계정 삭제 스크립트
# 매일 오전 1시에 실행되도록 Scheduled Tasks에 등록

# 작업 디렉토리로 이동
cd mysite

# 가상환경 활성화 (가상환경 사용 시)
# source venv/bin/activate

# Django 관리 명령 실행
python manage.py delete_unverified_accounts

# 결과를 로그 파일에 기록 (선택사항)
# python manage.py delete_unverified_accounts >> logs/delete_unverified_$(date +\%Y\%m\%d).log 2>&1
