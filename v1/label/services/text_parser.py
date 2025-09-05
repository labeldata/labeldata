"""
OCR 텍스트 파싱 엔진
추출된 텍스트를 분석하여 표시사항 필드별로 분류
"""
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LabelTextParser:
    def __init__(self):
        # 필드별 키워드 패턴 정의
        self.field_patterns = {
            'prdlst_nm': {
                'keywords': ['제품명', '상품명', '품명', '제품', '상품'],
                'patterns': [
                    r'제품명\s*[:\-]?\s*([^\n\r]+)',
                    r'상품명\s*[:\-]?\s*([^\n\r]+)',
                    r'품명\s*[:\-]?\s*([^\n\r]+)',
                    r'제품\s*[:\-]?\s*([^\n\r]+)',
                    r'상품\s*[:\-]?\s*([^\n\r]+)'
                ],
                'weight': 1.0
            },
            'prdlst_dcnm': {
                'keywords': ['식품유형', '식품의 유형', '유형', '분류'],
                'patterns': [
                    r'식품유형\s*[:\-]?\s*([^\n\r]+)',
                    r'식품의\s*유형\s*[:\-]?\s*([^\n\r]+)',
                    r'유형\s*[:\-]?\s*([^\n\r]+)',
                    r'분류\s*[:\-]?\s*([^\n\r]+)'
                ],
                'weight': 1.0
            },
            'content_weight': {
                'keywords': ['내용량', '중량', '용량', '정량'],
                'patterns': [
                    r'내용량\s*[:\-]?\s*([0-9,]+(?:\.\d+)?\s*[gkmlL]+)',
                    r'중량\s*[:\-]?\s*([0-9,]+(?:\.\d+)?\s*[gkmlL]+)',
                    r'용량\s*[:\-]?\s*([0-9,]+(?:\.\d+)?\s*[gkmlL]+)',
                    r'정량\s*[:\-]?\s*([0-9,]+(?:\.\d+)?\s*[gkmlL]+)',
                    r'(\d+(?:,\d+)*(?:\.\d+)?\s*(?:g|kg|ml|L|mL|리터))',
                    r'(\d+(?:,\d+)*(?:\.\d+)?\s*(?:그램|킬로그램|밀리리터))'
                ],
                'weight': 0.9
            },
            'country_of_origin': {
                'keywords': ['원산지', '원산국', '제조국'],
                'patterns': [
                    r'원산지\s*[:\-]?\s*([^\n\r]+)',
                    r'원산국\s*[:\-]?\s*([^\n\r]+)',
                    r'제조국\s*[:\-]?\s*([^\n\r]+)',
                    r'(대한민국|한국|미국|중국|일본|독일|프랑스|이탈리아|스페인|호주|캐나다|영국)'
                ],
                'weight': 0.8
            },
            'bssh_nm': {
                'keywords': ['제조원', '제조업체', '제조사', '생산업체', '생산자'],
                'patterns': [
                    r'제조원\s*[:\-]?\s*([^\n\r]+)',
                    r'제조업체\s*[:\-]?\s*([^\n\r]+)',
                    r'제조사\s*[:\-]?\s*([^\n\r]+)',
                    r'생산업체\s*[:\-]?\s*([^\n\r]+)',
                    r'생산자\s*[:\-]?\s*([^\n\r]+)',
                    r'([가-힣]+(?:주식회사|㈜|유한회사|회사))',
                    r'([A-Z][a-z]+\s+(?:Co\.|Corporation|Inc\.|Ltd\.))'
                ],
                'weight': 0.8
            },
            'storage_method': {
                'keywords': ['보관방법', '보존방법', '저장방법', '보관', '보존'],
                'patterns': [
                    r'보관방법\s*[:\-]?\s*([^\n\r]+)',
                    r'보존방법\s*[:\-]?\s*([^\n\r]+)',
                    r'저장방법\s*[:\-]?\s*([^\n\r]+)',
                    r'(냉장보관|냉동보관|실온보관|건조한곳|직사광선을\s*피해)',
                    r'(-?\d+℃\s*(?:이하|이상|보관))',
                    r'(서늘하고\s*건조한\s*곳에\s*보관)'
                ],
                'weight': 0.7
            },
            'rawmtrl_nm': {
                'keywords': ['원재료명', '원료', '성분', '재료'],
                'patterns': [
                    r'원재료명?\s*[:\-]?\s*([^\n\r]+(?:\n[^가-힣제품원]*)*)',
                    r'원료\s*[:\-]?\s*([^\n\r]+)',
                    r'성분\s*[:\-]?\s*([^\n\r]+)',
                    r'재료\s*[:\-]?\s*([^\n\r]+)'
                ],
                'weight': 0.9
            },
            'cautions': {
                'keywords': ['주의사항', '주의', '경고', '주의하세요'],
                'patterns': [
                    r'주의사항\s*[:\-]?\s*([^\n\r]+(?:\n[^가-힣제품원]*)*)',
                    r'주의\s*[:\-]?\s*([^\n\r]+)',
                    r'경고\s*[:\-]?\s*([^\n\r]+)',
                    r'(알레르기\s*[^.\n\r]*)',
                    r'(견과류\s*[^.\n\r]*)',
                    r'(유제품\s*[^.\n\r]*)'
                ],
                'weight': 0.8
            },
            'pog_daycnt': {
                'keywords': ['소비기한', '유통기한', '제조일자', '생산일자'],
                'patterns': [
                    r'소비기한\s*[:\-]?\s*([^\n\r]+)',
                    r'유통기한\s*[:\-]?\s*([^\n\r]+)',
                    r'제조일자\s*[:\-]?\s*([^\n\r]+)',
                    r'생산일자\s*[:\-]?\s*([^\n\r]+)',
                    r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})',
                    r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)',
                    r'(\d{2}[-./]\d{1,2}[-./]\d{1,2})',
                    r'(별도\s*표기|제품\s*포장지\s*참조)'
                ],
                'weight': 0.8
            },
            'distributor_address': {
                'keywords': ['유통업체', '판매업체', '수입업체', '유통원'],
                'patterns': [
                    r'유통업체\s*[:\-]?\s*([^\n\r]+)',
                    r'판매업체\s*[:\-]?\s*([^\n\r]+)',
                    r'수입업체\s*[:\-]?\s*([^\n\r]+)',
                    r'유통원\s*[:\-]?\s*([^\n\r]+)'
                ],
                'weight': 0.6
            },
            'ingredient_info': {
                'keywords': ['특정성분', '함량', '영양성분'],
                'patterns': [
                    r'특정성분\s*[:\-]?\s*([^\n\r]+)',
                    r'함량\s*[:\-]?\s*([^\n\r]+)',
                    r'영양성분\s*[:\-]?\s*([^\n\r]+)',
                    r'(\d+(?:\.\d+)?%)',
                    r'(\d+(?:\.\d+)?\s*mg/\d+g)'
                ],
                'weight': 0.7
            }
        }
        
        # 한국어 일반 패턴
        self.korean_patterns = {
            'company_suffix': ['주식회사', '㈜', '유한회사', '(주)', 'Co.', 'Ltd.', 'Inc.'],
            'weight_units': ['g', 'kg', 'ml', 'L', 'mL', '그램', '킬로그램', '밀리리터', '리터'],
            'temperature': ['℃', '도'],
            'allergens': ['견과류', '대두', '우유', '달걀', '밀', '갑각류', '생선', '조개류']
        }
    
    def parse_label_text(self, text: str) -> Dict[str, Any]:
        """
        OCR로 추출된 텍스트를 분석하여 각 필드별로 분류
        """
        if not text or not text.strip():
            return {}
        
        logger.info(f"텍스트 파싱 시작, 길이: {len(text)}")
        
        results = {}
        
        # 전체 텍스트 정규화
        normalized_text = self._normalize_text(text)
        
        # 각 필드별로 데이터 추출
        for field_name, config in self.field_patterns.items():
            try:
                extracted_data = self._extract_field_data(normalized_text, field_name, config)
                if extracted_data:
                    results[field_name] = extracted_data
                    logger.info(f"필드 '{field_name}' 추출 완료: {extracted_data.get('text', '')[:50]}...")
            except Exception as e:
                logger.error(f"필드 '{field_name}' 추출 중 오류: {str(e)}")
        
        logger.info(f"텍스트 파싱 완료, 추출된 필드 수: {len(results)}")
        return results
    
    def _normalize_text(self, text: str) -> str:
        """
        텍스트 정규화 (공백, 특수문자 정리)
        """
        # 연속된 공백을 하나로 통합
        text = re.sub(r'\s+', ' ', text)
        
        # 불필요한 특수문자 제거 (단, 필요한 문자는 보존)
        text = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ:\-.,()%/℃°]', ' ', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def _extract_field_data(self, text: str, field_name: str, config: Dict) -> Optional[Dict[str, Any]]:
        """
        특정 필드에 대한 데이터 추출
        """
        best_match = None
        highest_confidence = 0.0
        
        # 정규식 패턴으로 매칭 시도
        for pattern in config['patterns']:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                
                for match in matches:
                    # 매칭된 텍스트 추출
                    if match.groups():
                        extracted_text = match.group(1).strip()
                    else:
                        extracted_text = match.group(0).strip()
                    
                    if extracted_text and len(extracted_text) > 1:
                        # 신뢰도 계산
                        confidence = self._calculate_confidence(
                            extracted_text, field_name, config, pattern, text
                        )
                        
                        if confidence > highest_confidence:
                            highest_confidence = confidence
                            best_match = {
                                'text': self._clean_extracted_text(extracted_text, field_name),
                                'confidence': confidence,
                                'matched_pattern': pattern,
                                'field_name': field_name
                            }
            except re.error as e:
                logger.error(f"정규식 오류 - 패턴: {pattern}, 오류: {str(e)}")
                continue
        
        return best_match if best_match and highest_confidence > 0.3 else None
    
    def _calculate_confidence(self, text: str, field_name: str, config: Dict, 
                            pattern: str, full_text: str) -> float:
        """
        추출된 텍스트의 신뢰도 계산
        """
        confidence = 0.4  # 기본 신뢰도
        
        # 1. 키워드 매칭 보너스
        keyword_bonus = 0.0
        for keyword in config['keywords']:
            if keyword in full_text:
                keyword_bonus += 0.15
                if keyword in text:
                    keyword_bonus += 0.1
        confidence += min(keyword_bonus, 0.3)
        
        # 2. 필드별 특수 검증
        field_bonus = self._get_field_specific_bonus(text, field_name)
        confidence += field_bonus
        
        # 3. 텍스트 길이 고려
        length_bonus = self._get_length_bonus(text, field_name)
        confidence += length_bonus
        
        # 4. 패턴 정확도
        pattern_bonus = self._get_pattern_bonus(pattern, config['patterns'])
        confidence += pattern_bonus
        
        # 5. 가중치 적용
        confidence *= config.get('weight', 1.0)
        
        # 6. 전체 텍스트 내 위치 고려 (앞쪽에 있을수록 높은 신뢰도)
        position_bonus = self._get_position_bonus(text, full_text)
        confidence += position_bonus
        
        return min(1.0, max(0.0, confidence))
    
    def _get_field_specific_bonus(self, text: str, field_name: str) -> float:
        """
        필드별 특수 검증 보너스
        """
        bonus = 0.0
        
        if field_name == 'content_weight':
            # 중량 단위 포함 여부
            for unit in self.korean_patterns['weight_units']:
                if unit in text:
                    bonus += 0.2
                    break
            
            # 숫자 포함 여부
            if re.search(r'\d+', text):
                bonus += 0.1
        
        elif field_name == 'bssh_nm':
            # 회사 접미사 포함 여부
            for suffix in self.korean_patterns['company_suffix']:
                if suffix in text:
                    bonus += 0.2
                    break
        
        elif field_name == 'storage_method':
            # 온도 관련 키워드
            if re.search(r'\d+\s*℃|냉장|냉동|실온', text):
                bonus += 0.2
        
        elif field_name == 'cautions':
            # 알레르기 관련 키워드
            for allergen in self.korean_patterns['allergens']:
                if allergen in text:
                    bonus += 0.15
                    break
        
        elif field_name == 'pog_daycnt':
            # 날짜 형식 검증
            if re.search(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{4}년.*\d{1,2}월.*\d{1,2}일', text):
                bonus += 0.3
        
        elif field_name == 'country_of_origin':
            # 국가명 검증
            countries = ['대한민국', '한국', '미국', '중국', '일본', '독일', '프랑스', '이탈리아']
            for country in countries:
                if country in text:
                    bonus += 0.3
                    break
        
        return min(bonus, 0.4)
    
    def _get_length_bonus(self, text: str, field_name: str) -> float:
        """
        텍스트 길이에 따른 보너스
        """
        length = len(text.strip())
        
        # 필드별 적절한 길이 범위
        optimal_ranges = {
            'prdlst_nm': (3, 50),
            'prdlst_dcnm': (3, 30),
            'content_weight': (2, 20),
            'country_of_origin': (2, 20),
            'bssh_nm': (5, 100),
            'storage_method': (5, 100),
            'rawmtrl_nm': (10, 500),
            'cautions': (5, 200),
            'pog_daycnt': (5, 30)
        }
        
        min_len, max_len = optimal_ranges.get(field_name, (2, 100))
        
        if min_len <= length <= max_len:
            return 0.1
        elif length < min_len * 0.5 or length > max_len * 2:
            return -0.2
        else:
            return 0.0
    
    def _get_pattern_bonus(self, pattern: str, all_patterns: List[str]) -> float:
        """
        패턴 순서에 따른 보너스 (앞선 패턴일수록 높은 신뢰도)
        """
        try:
            index = all_patterns.index(pattern)
            return max(0.0, 0.1 - (index * 0.02))
        except ValueError:
            return 0.0
    
    def _get_position_bonus(self, text: str, full_text: str) -> float:
        """
        전체 텍스트 내에서의 위치에 따른 보너스
        """
        try:
            position = full_text.find(text)
            if position >= 0:
                relative_position = position / len(full_text)
                # 앞쪽에 있을수록 높은 보너스
                return max(0.0, 0.1 - (relative_position * 0.1))
        except:
            pass
        return 0.0
    
    def _clean_extracted_text(self, text: str, field_name: str) -> str:
        """
        추출된 텍스트 정리 (불필요한 문자 제거 등)
        """
        # 앞뒤 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로 통합
        text = re.sub(r'\s+', ' ', text)
        
        # 끝의 콜론, 하이픈 제거
        text = re.sub(r'[:\-]\s*$', '', text)
        
        # 필드별 특수 정리
        if field_name == 'content_weight':
            # 내용량은 숫자 + 단위만 추출
            match = re.search(r'\d+(?:,\d+)*(?:\.\d+)?\s*[gkmlL그킬밀리터]+', text)
            if match:
                text = match.group(0)
        
        elif field_name == 'pog_daycnt':
            # 날짜는 표준 형식으로 정리
            date_match = re.search(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', text)
            if date_match:
                text = date_match.group(0)
        
        # 너무 긴 텍스트는 적절히 자르기
        max_lengths = {
            'prdlst_nm': 100,
            'prdlst_dcnm': 50,
            'content_weight': 30,
            'country_of_origin': 30,
            'bssh_nm': 200,
            'storage_method': 200,
            'rawmtrl_nm': 1000,
            'cautions': 500,
            'pog_daycnt': 50
        }
        
        max_len = max_lengths.get(field_name, 200)
        if len(text) > max_len:
            text = text[:max_len] + '...'
        
        return text
