"""관리자 알림 메일 발송 배치를 파일 기반으로 기록하는 저장소.

DB 모델을 추가하지 않고, 배치별 JSON 파일 + 파일 존재 여부를 이용한 원자적 락으로
- 발송 진행 상황 추적 (요청-응답과 분리된 백그라운드 스레드가 건별로 즉시 기록)
- 동일 요청의 중복 제출 방지 (idempotency token)
- 동일 배치의 중복 처리 방지 (processing lock)
를 구현한다.
"""
import json
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

_BASE = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
BULK_EMAIL_DIR = _BASE.parent / 'bulk_email_data'
BATCHES_DIR = BULK_EMAIL_DIR / 'batches'
TOKENS_DIR = BULK_EMAIL_DIR / 'tokens'
LOCKS_DIR = BULK_EMAIL_DIR / 'locks'

for _d in (BATCHES_DIR, TOKENS_DIR, LOCKS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class DuplicateSubmissionError(Exception):
    """동일 idempotency token으로 이미 배치가 생성된 경우."""
    def __init__(self, batch_id):
        super().__init__(batch_id)
        self.batch_id = batch_id


def _batch_path(batch_id):
    return BATCHES_DIR / f'{batch_id}.json'


def _save_batch(batch_id, data):
    tmp_path = _batch_path(batch_id).with_suffix('.json.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, _batch_path(batch_id))  # 같은 파일시스템 내 원자적 교체


def create_batch(subject, body, created_by, emails, token):
    """token 파일을 원자적으로 생성해 중복 제출을 막는다.
    이미 같은 token 파일이 있으면 기존 배치 id를 담아 DuplicateSubmissionError를 발생시킨다."""
    token_file = TOKENS_DIR / f'{token}.txt'
    batch_id = uuid.uuid4().hex
    try:
        fd = os.open(str(token_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(batch_id)
    except FileExistsError:
        existing_batch_id = token_file.read_text(encoding='utf-8').strip()
        raise DuplicateSubmissionError(existing_batch_id)

    data = {
        'batch_id': batch_id,
        'subject': subject,
        'body': body,
        'created_by': created_by,
        'created_at': timezone.now().isoformat(),
        'recipients': [
            {'email': e, 'status': 'pending', 'sent_at': None, 'error': ''}
            for e in emails
        ],
    }
    _save_batch(batch_id, data)
    return batch_id


def load_batch(batch_id):
    path = _batch_path(batch_id)
    if not path.exists():
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def update_recipient_status(batch_id, email, status, error=''):
    data = load_batch(batch_id)
    if not data:
        return
    for r in data['recipients']:
        if r['email'] == email:
            r['status'] = status
            r['error'] = error
            if status == 'sent':
                r['sent_at'] = timezone.now().isoformat()
            break
    _save_batch(batch_id, data)


def batch_counts(data):
    recipients = data['recipients']
    return {
        'total': len(recipients),
        'sent': sum(1 for r in recipients if r['status'] == 'sent'),
        'failed': sum(1 for r in recipients if r['status'] == 'failed'),
        'pending': sum(1 for r in recipients if r['status'] == 'pending'),
    }


def claim_processing(batch_id):
    """배치 처리를 원자적으로 선점 (재발송 버튼 연타 등으로 인한 중복 실행 방지)."""
    lock_path = LOCKS_DIR / f'{batch_id}.lock'
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_processing(batch_id):
    lock_path = LOCKS_DIR / f'{batch_id}.lock'
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
