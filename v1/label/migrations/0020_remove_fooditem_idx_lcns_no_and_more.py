"""
같은 컬럼에 두 벌씩 걸려 있던 인덱스를 걷어낸다.

모델에서는 이미 지웠는데 마이그레이션으로 옮겨지지 않아, makemigrations 를 돌릴
때마다 이 5건이 따라 나왔다. 마이그레이션이 넉 달 동안 막혀 있어서 대신
`ensure_search_indexes --drop-duplicates` 라는 관리 명령이 DB 쪽을 맡고 있었다.
그 전제(migrate 를 못 돈다)가 사라졌으므로 제자리로 돌린다.

**이미 지워져 있을 수 있다.** 위 관리 명령을 돌린 환경에서는 인덱스가 없고,
그냥 RemoveIndex 를 쓰면 "check that column/key exists" 로 죽는다. 그래서
상태(state)와 실제 DDL 을 갈라, DDL 은 있을 때만 지운다.

지우는 인덱스와 남는 인덱스 (products/services 의 검색은 남는 쪽을 쓴다):

    food_item.idx_lcns_no           -> food_item_lcns_no_1e94cc47
    food_item.idx_prdlst_nm         -> food_item_prdlst_nm_2b626e08
    food_item.idx_prdlst_report_no  -> PRIMARY
    imported_food.idx_bsn_ofc_name  -> imported_food_bsn_ofc_name_4f34dd05
    imported_food.idx_itm_nm        -> imported_food_itm_nm_76398b54
"""
from django.db import migrations

# (테이블, 지울 인덱스)
DUPLICATES = [
    ('food_item', 'idx_lcns_no'),
    ('food_item', 'idx_prdlst_report_no'),
    ('food_item', 'idx_prdlst_nm'),
    ('imported_food', 'idx_bsn_ofc_name'),
    ('imported_food', 'idx_itm_nm'),
]


def drop_duplicate_indexes(apps, schema_editor):
    """있을 때만 지운다. 이미 없는 환경에서도 그냥 지나간다."""
    with schema_editor.connection.cursor() as cursor:
        for table, index in DUPLICATES:
            cursor.execute(
                'SELECT COUNT(*) FROM information_schema.statistics '
                'WHERE table_schema = DATABASE() '
                'AND table_name = %s AND index_name = %s',
                [table, index],
            )
            if cursor.fetchone()[0]:
                cursor.execute(f'ALTER TABLE `{table}` DROP INDEX `{index}`')


def noop(apps, schema_editor):
    """
    되돌리기는 아무것도 하지 않는다.

    다시 만들면 중복 인덱스가 되살아난다 - 이 마이그레이션이 없애려던 바로 그
    상태다. 인덱스가 필요하면 ensure_search_indexes 가 만든다.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('label', '0019_mylabel_basic_display_type_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(model_name='fooditem', name='idx_lcns_no'),
                migrations.RemoveIndex(model_name='fooditem', name='idx_prdlst_report_no'),
                migrations.RemoveIndex(model_name='fooditem', name='idx_prdlst_nm'),
                migrations.RemoveIndex(model_name='importedfood', name='idx_bsn_ofc_name'),
                migrations.RemoveIndex(model_name='importedfood', name='idx_itm_nm'),
            ],
            database_operations=[
                migrations.RunPython(drop_duplicate_indexes, noop),
            ],
        ),
    ]
