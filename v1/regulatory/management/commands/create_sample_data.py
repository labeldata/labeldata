"""
로컬 개발용 샘플 데이터 생성 커맨드.

사용법:
  python manage.py create_sample_data
  python manage.py create_sample_data --user admin
  python manage.py create_sample_data --flush   # 기존 샘플 삭제 후 재생성
"""
import random
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# ── 샘플 원재료 / 검출물질 풀 ─────────────────────────────────────────────────
_INGREDIENTS = [
    '마늘종', '마늘', '생강', '대파', '양파', '고추', '시금치', '깻잎',
    '당근', '배추', '무', '참깨', '들깨', '콩', '팥', '옥수수',
    '쌀', '밀가루', '전분', '소금', '설탕', '식용유', '참기름', '들기름',
]
_SUBSTANCES = [
    '납', '카드뮴', '수은', '비소', '아플라톡신', '오크라톡신',
    '벤조피렌', '잔류농약(클로르피리포스)', '잔류농약(에토펜프록스)',
    '대장균군', '살모넬라', '황색포도상구균', '리스테리아',
    '타르색소(적색2호)', '사카린나트륨', '보존료(소브산)',
]
_COMPANIES = [
    '(주)한국식품', '대한식품(주)', '(주)서울식품산업', '부산식품(주)',
    '(주)신선식품', '자연건강식품(주)', '(주)농심', '청정원식품(주)',
    '(주)삼양식품', '오뚜기식품(주)', '(주)CJ제일제당', '롯데식품(주)',
]
_PRODUCTS = [
    '고수 나물', '흙 대파', '시금치', '깻잎 무침', '마늘 장아찌',
    '참기름', '들기름', '된장', '간장', '고추장', '쌈장',
    '쌀국수', '잡채', '비빔냉면', '순대', '어묵', '떡볶이',
    '두부', '콩나물', '숙주나물', '김치', '열무김치', '깍두기',
]
_PLAN_TITLES = [
    '2026년 상반기 식품 안전 수거검사', '2026년 농산물 잔류농약 검사',
    '2026년 가공식품 중금속 수거검사', '2026년 김치류 위생검사',
    '2026년 수산물 안전성 검사', '2026년 식용유지 수거검사',
]
_INSTITUTIONS = [
    '서울특별시 보건환경연구원', '경기도 보건환경연구원',
    '부산광역시 보건환경연구원', '인천광역시 보건환경연구원',
    '대전광역시 보건환경연구원', '광주광역시 보건환경연구원',
    '대구광역시 보건환경연구원', '울산광역시 보건환경연구원',
]
_JUDGMENTS = ['', '검토중', '적합', '부적합', '부적합']  # 부적합 가중
_VIOLATION_REASONS = [
    '잔류농약 기준 초과 (클로르피리포스 0.05 mg/kg 검출)',
    '중금속(납) 기준 초과 (0.3 mg/kg 초과)',
    '대장균군 기준 초과 (양성 검출)',
    '타르색소 기준 초과 (적색2호 검출)',
    '사카린나트륨 기준 초과',
    '보존료(소브산) 미표시 사용',
    '아플라톡신 기준 초과 (5 μg/kg 초과)',
    '살모넬라 검출',
]
_ADMIN_ACTIONS = [
    '영업정지 15일', '영업정지 1개월', '시정명령', '품목제조정지 15일',
    '영업허가취소', '과징금 부과', '폐기처분', '회수조치',
]
_ADDRESSES = [
    '서울특별시 강남구 테헤란로 123', '경기도 성남시 분당구 판교로 456',
    '부산광역시 해운대구 센텀동로 789', '인천광역시 남동구 인주대로 321',
    '대전광역시 유성구 대학로 654', '광주광역시 북구 운암동 987',
]


def _rand_date(days_back=365):
    d = datetime.date.today() - datetime.timedelta(days=random.randint(1, days_back))
    return d.strftime('%Y%m%d')


def _rand_license():
    year = random.randint(2018, 2025)
    city = random.choice(['서울강남', '서울강북', '경기성남', '부산해운대', '인천남동'])
    seq = random.randint(1000, 9999)
    return f'{year}-{city}-{seq:05d}'


class Command(BaseCommand):
    help = '로컬 개발용 샘플 데이터 생성 (부적합·행정처분·수거검사)'

    def add_arguments(self, parser):
        parser.add_argument('--user', default='admin', help='대상 사용자 username (기본: admin)')
        parser.add_argument('--flush', action='store_true', help='기존 샘플 데이터 삭제 후 재생성')
        parser.add_argument('--news', type=int, default=30, help='부적합·처분 뉴스 생성 수 (기본: 30)')
        parser.add_argument('--insp', type=int, default=20, help='수거검사 결과 생성 수 (기본: 20)')

    def handle(self, *args, **options):
        from v1.regulatory.models import (
            RegulatoryNews, InspectionResult, InspectionMatch,
        )
        from v1.user_management.models import UserProfile
        from v1.label.models import MyLabel

        username = options['username'] if 'username' in options else options['user']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'사용자 "{username}" 없음. --user 옵션으로 username을 지정하세요.')

        if options['flush']:
            deleted, _ = RegulatoryNews.objects.filter(
                external_id__startswith='SAMPLE-'
            ).delete()
            self.stdout.write(f'  기존 샘플 뉴스 {deleted}건 삭제')
            deleted2, _ = InspectionResult.objects.filter(
                tkawyprno__startswith='SAMP-'
            ).delete()
            self.stdout.write(f'  기존 샘플 수거검사 {deleted2}건 삭제')

        # ── 1. UserProfile (회사명 + 인허가번호) 설정 ─────────────────────────
        profile, created = UserProfile.objects.get_or_create(user=user)
        if not profile.company_name:
            profile.company_name = '(주)한국식품'
            profile.save(update_fields=['company_name'])
            self.stdout.write(f'  UserProfile 회사명 설정: {profile.company_name}')
        if not profile.license_number:
            profile.license_number = '2022-서울강남-01234'
            profile.save(update_fields=['license_number'])
            self.stdout.write(f'  UserProfile 인허가번호 설정: {profile.license_number}')

        # ── 2. 부적합·처분 RegulatoryNews ────────────────────────────────────
        news_count = options['news']
        sources = [
            # (api_source, source, weight)
            ('I2620', 'domestic', 4),   # 국내 검사부적합
            ('I2640', 'domestic', 2),
            ('I0490', 'domestic', 2),   # 국내 회수
            ('I0470', 'domestic', 3),   # 국내 행정처분
            ('I0480', 'domestic', 2),
            ('imp_insp', 'import', 2),  # 수입 부적합
            ('import',   'import', 1),  # 수입 회수
            ('I0482',    'import', 1),  # 수입 행정처분
            ('saol_admin','domestic',1),# 지자체 행정처분
        ]
        weights = [w for *_, w in sources]

        created_news = 0
        for i in range(1, news_count + 1):
            api_source, source, _ = random.choices(sources, weights=weights)[0]
            ext_id = f'SAMPLE-{api_source}-{i:04d}'
            if RegulatoryNews.objects.filter(source=source, external_id=ext_id).exists():
                continue

            ingredient = random.choice(_INGREDIENTS)
            substance  = random.choice(_SUBSTANCES)
            company    = random.choice(_COMPANIES)
            product    = random.choice(_PRODUCTS)
            violation  = random.choice(_VIOLATION_REASONS)

            is_admin = api_source in ('I0470', 'I0480', 'I0482', 'saol_admin')

            RegulatoryNews.objects.create(
                api_source=api_source,
                source=source,
                external_id=ext_id,
                product_name=product,
                company_name=company,
                violation_reason=violation if not is_admin else '',
                raw_detail_text=f'행정처분 내용: {random.choice(_ADMIN_ACTIONS)}' if is_admin else violation,
                ai_keywords=[ingredient, substance],
                ai_substances=[substance],
                violation_type='residue' if '잔류' in violation else 'micro' if '대장균' in violation or '살모' in violation else 'heavy_metal',
                ai_summary=f'{product}에서 {violation}',
                ai_parsed=True,
                risk_level=random.choice(['HIGH', 'HIGH', 'MED', 'MED', 'LOW']),
                event_date=datetime.date.today() - datetime.timedelta(days=random.randint(1, 300)),
            )
            created_news += 1

        self.stdout.write(self.style.SUCCESS(f'  부적합·처분 뉴스 {created_news}건 생성'))

        # ── 3. 수거검사 InspectionResult + InspectionMatch ───────────────────
        insp_count = options['insp']
        existing_labels = list(
            MyLabel.objects.filter(user_id=user).values_list('my_label_id', 'prdlst_report_no', 'prdlst_nm')[:10]
        )

        created_insp = 0
        created_match = 0
        for i in range(1, insp_count + 1):
            prno = f'SAMP-{i:04d}'
            company = random.choice(_COMPANIES)
            product = random.choice(_PRODUCTS)
            judgment = random.choice(_JUDGMENTS)

            insp, insp_created = InspectionResult.objects.get_or_create(
                tkawyprno=prno,
                defaults=dict(
                    plan_titl=random.choice(_PLAN_TITLES),
                    bssh_nm=company,
                    prdtnm=product,
                    prdlst_report_no=f'{random.randint(10,99)}{random.randint(100000,999999)}-{random.randint(1000,9999)}' if random.random() < 0.5 else '',
                    jdgmnt_cd_nm=judgment,
                    induty_cd_nm='식품제조업',
                    site_addr=random.choice(_ADDRESSES),
                    tkawydtm=_rand_date(180),
                    tkawyspci_typecd_nm=random.choice(['유통식품', '생산단계식품']),
                    exc_instt_nm=random.choice(_INSTITUTIONS),
                    last_updt_dtm=timezone.now().strftime('%Y%m%d%H%M%S'),
                ),
            )
            if insp_created:
                created_insp += 1

            # 매칭 생성: 랜덤하게 회사명 또는 인허가번호로 매칭
            reasons = []
            if profile.company_name and random.random() < 0.6:
                reasons.append(('company', profile.company_name))
            if profile.license_number and random.random() < 0.5:
                reasons.append(('license_no', profile.license_number))
            if existing_labels and random.random() < 0.3:
                lbl = random.choice(existing_labels)
                if lbl[1]:  # label_no 있을 때
                    reasons.append(('label_no', lbl[1]))

            if not reasons:
                reasons = [('company', profile.company_name or '(주)한국식품')]

            label_id = None
            if existing_labels and reasons[0][0] == 'label_no':
                for lid, lno, _ in existing_labels:
                    if lno == reasons[0][1]:
                        label_id = lid
                        break

            reason, matched_val = reasons[0]
            is_read = random.random() < 0.4

            InspectionMatch.objects.get_or_create(
                inspection=insp,
                user=user,
                alert_phase=1,
                defaults=dict(
                    label_id=label_id,
                    match_reason=reason,
                    matched_value=matched_val,
                    notified_at=timezone.now() - datetime.timedelta(days=random.randint(0, 30)),
                    read_yn=is_read,
                    read_at=timezone.now() if is_read else None,
                ),
            )
            created_match += 1

            # 20% 확률로 판정변동(phase=2) 매칭 추가
            if judgment == '부적합' and random.random() < 0.2:
                InspectionMatch.objects.get_or_create(
                    inspection=insp,
                    user=user,
                    alert_phase=2,
                    defaults=dict(
                        label_id=label_id,
                        match_reason=reason,
                        matched_value=matched_val,
                        prev_judgment='검토중',
                        notified_at=timezone.now() - datetime.timedelta(days=random.randint(0, 7)),
                        read_yn=False,
                    ),
                )
                created_match += 1

        self.stdout.write(self.style.SUCCESS(
            f'  수거검사 결과 {created_insp}건, 매칭 {created_match}건 생성'
        ))

        self.stdout.write(self.style.SUCCESS(
            f'\n[완료] 대상 사용자: {user.username} ({user.email})'
        ))
        self.stdout.write(
            f'   부적합·처분: {RegulatoryNews.objects.filter(external_id__startswith="SAMPLE-").count()}건 (샘플)'
        )
        self.stdout.write(
            f'   수거검사 매칭: {InspectionMatch.objects.filter(user=user).count()}건 (전체)'
        )
