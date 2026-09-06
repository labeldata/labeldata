"""
붙여넣기 양식(엑셀) 만들기 — 표 화면 공용.

사용자들은 배합비도 연락처도 엑셀로 관리하다 여기로 온다. 붙여넣기는 **열
순서를 맞춰 와야** 하는데, 자기 엑셀의 열 순서를 알 방법이 우리에게 없다.

그래서 양식을 우리가 준다. 내려받아 채우고 그대로 긁어 붙이면 된다.
열 이름을 보고 알아서 맞추는 것(열 매핑)은 다음 일이고, 그때도 이 양식은
"이렇게 생긴 것을 기대한다" 는 기준으로 남는다.

양식에 넣는 것은 셋뿐이다.

  머리글   화면의 열 이름과 **글자까지 같다.** 다르면 붙여넣기가 머리글 줄을
           못 알아보고 자료로 넣는다
  보기 줄  한 줄. 무엇을 어떤 꼴로 적는지는 설명보다 예가 빠르다
  안내     맨 위 한 줄. 파일만 보고도 쓰는 법을 알아야 한다
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HEAD_FILL = PatternFill('solid', fgColor='E8F0FE')
_NOTE_FILL = PatternFill('solid', fgColor='FEF7E0')


def build(title, headers, sample, note, widths=None):
    """
    양식 한 장을 만들어 바이트로 돌려준다.

    headers  열 이름 (화면의 머리글과 같아야 한다)
    sample   보기 줄 한 줄
    note     맨 위 안내 한 줄
    widths   열 너비. 없으면 이름 길이로 어림한다
    """
    book = Workbook()
    sheet = book.active
    sheet.title = title[:31]

    sheet.append([note])
    sheet.merge_cells(start_row=1, start_column=1,
                      end_row=1, end_column=max(len(headers), 1))
    guide = sheet.cell(row=1, column=1)
    guide.fill = _NOTE_FILL
    guide.font = Font(size=10)
    guide.alignment = Alignment(vertical='center', wrap_text=True)
    sheet.row_dimensions[1].height = 30

    sheet.append(list(headers))
    for i in range(1, len(headers) + 1):
        cell = sheet.cell(row=2, column=i)
        cell.fill = _HEAD_FILL
        cell.font = Font(bold=True, size=11)
        cell.alignment = Alignment(horizontal='center', vertical='center')
    sheet.row_dimensions[2].height = 22

    if sample:
        sheet.append(list(sample))

    for i, name in enumerate(headers, start=1):
        width = (widths or {}).get(name)
        sheet.column_dimensions[get_column_letter(i)].width = width or max(
            12, min(30, len(str(name)) * 2 + 6))

    # 머리글까지 함께 긁어 와도 붙여넣기가 그 줄을 버린다. 그래도 자료만
    # 집도록 틀을 고정해 둔다 — 세 번째 줄부터가 자료다.
    sheet.freeze_panes = 'A3'

    buffer = io.BytesIO()
    book.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


BOM_HEADERS = ['원료명', '원재료 표시명', '식품유형', '배합비(%)',
               '제조사/수입사', '알레르기 성분', 'GMO', '품목보고번호', '비고']
BOM_SAMPLE = ['전란액', '전란액', '알가공품', '12.5', '(주)가나다',
              '알류', '', '19990000000', '']
BOM_NOTE = ('세 번째 줄부터 채우세요. 다 채운 뒤 이 표를 통째로 긁어 '
            'BOM 탭에 붙여넣으면 됩니다. 배합비는 숫자만 적습니다(% 기호 없이). '
            '쓰시던 엑셀을 그대로 붙여넣어도 됩니다 — 머리글이 있으면 열 '
            '순서가 달라도 제자리를 찾아갑니다. 알레르기를 "계란 / 우유 / 밀" '
            '처럼 열로 나눠 O 로 체크하셨다면 그것도 모아서 넣습니다.')

CONTACT_HEADERS = ['이메일', '이름', '회사명', '인허가번호', '비고']
CONTACT_SAMPLE = ['hong@example.com', '홍길동', '(주)가나다식품', '20240123456',
                  '품질팀 · 02-000-0000']
CONTACT_NOTE = ('세 번째 줄부터 채우세요. 다 채운 뒤 이 표를 통째로 긁어 '
                '연락처 표에 붙여넣으면 됩니다. 이메일이 없는 줄은 저장되지 '
                '않습니다. 쓰시던 엑셀을 그대로 붙여넣어도 됩니다 — 머리글이 '
                '있으면 열 순서가 달라도 제자리를 찾아갑니다.')


def bom_template():
    return build('배합비', BOM_HEADERS, BOM_SAMPLE, BOM_NOTE,
                 widths={'원료명': 22, '원재료 표시명': 22, '비고': 24})


def contact_template():
    return build('연락처', CONTACT_HEADERS, CONTACT_SAMPLE, CONTACT_NOTE,
                 widths={'이메일': 26, '회사명': 22, '인허가번호': 18, '비고': 24})
