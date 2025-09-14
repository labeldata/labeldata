/**
 * 통합 스마트 추천 시스템 v6.0 - 팝업 방식, 추천 기반 색상 변경
 * - 온/오프 토글 제거
 * - 추천 문구 존재 시에만 초록색 표시
 * - 팝업 방식으로 변경 (기존 모달 대신)
 */

class UnifiedSmartRecommendationSystem {
    constructor() {
        this.apiUrl = '/label/api/auto-fill/';
        this.phraseApiUrl = '/label/api/phrases/';
        this.currentField = null;
        this.currentFieldValue = '';
        this.recommendationCache = new Map();
        this.recommendationPopup = null;
        this.selectedItems = new Set();
        
        this.init();
    }

    init() {
        console.log('🚀 통합 스마트 추천 시스템 v6.0 초기화 시작 - 팝업 방식');
        
        this.createRecommendationPopup();
        this.setupFieldListeners();
        
        // 전역 변수로 등록
        window.unifiedSmartRecommendation = this;
        
        // 초기 필드 아이콘 상태 설정
        setTimeout(() => {
            this.checkAllFieldsForRecommendations();
        }, 500);
        
        console.log('✅ 통합 스마트 추천 시스템 v6.0 초기화 완료');
    }

    checkAllFieldsForRecommendations() {
        console.log('🔍 모든 필드의 추천 문구 존재 여부 확인 시작');
        
        const fields = [
            'prdlst_nm', 'prdlst_dcnm', 'storage_method', 'cautions', 
            'bssh_nm', 'frmlc_mtrqlt', 'rawmtrl_nm_display', 'content_weight',
            'additional_info', 'ingredient_info', 'prdlst_report_no', 'country_of_origin'
        ];

        fields.forEach(fieldName => {
            this.checkFieldForRecommendations(fieldName);
        });
        
        console.log('✅ 모든 필드 추천 확인 완료');
    }

    async checkFieldForRecommendations(fieldName) {
        const fieldElement = document.querySelector(`[name="${fieldName}"]`);
        const smartButton = document.querySelector(`.smart-recommendation-icon[data-field="${fieldName}"]`);
        
        if (!fieldElement || !smartButton) {
            return;
        }

        const value = fieldElement.value ? fieldElement.value.trim() : '';
        
        // 버튼을 체킹 상태로 표시
        smartButton.classList.add('checking');
        smartButton.classList.remove('has-recommendations');
        smartButton.title = '추천 문구 확인 중...';

        try {
            // 추천 문구 존재 여부 확인
            const hasRecommendations = await this.hasRecommendationsForField(fieldName, value);
            
            if (hasRecommendations) {
                smartButton.classList.add('has-recommendations');
                smartButton.classList.remove('checking');
                smartButton.title = `${fieldName} 스마트 추천 (추천 문구 있음)`;
                console.log(`✅ ${fieldName}: 추천 문구 있음`);
            } else {
                smartButton.classList.remove('has-recommendations', 'checking');
                smartButton.title = `${fieldName} 스마트 추천 (추천 문구 없음)`;
                console.log(`⭕ ${fieldName}: 추천 문구 없음`);
            }
        } catch (error) {
            console.error(`❌ ${fieldName} 추천 확인 실패:`, error);
            smartButton.classList.remove('has-recommendations', 'checking');
            smartButton.title = `${fieldName} 스마트 추천 (확인 실패)`;
        }
    }

    async hasRecommendationsForField(fieldName, value) {
        try {
            // 캐시 확인
            const cacheKey = `${fieldName}_${value}`;
            if (this.recommendationCache.has(cacheKey)) {
                const cached = this.recommendationCache.get(cacheKey);
                return cached && cached.recommendations && cached.recommendations.length > 0;
            }

            // 실제 API 호출로 추천 문구 확인 (GET 방식으로 변경)
            const params = new URLSearchParams({
                'input_field': fieldName,
                'input_value': value,
                'target_fields': JSON.stringify([fieldName]),
                'priority': 'medium'
            });

            const response = await fetch(`${this.apiUrl}?${params.toString()}`, {
                method: 'GET'
            });

            if (response.ok) {
                const data = await response.json();
                
                // 캐시에 저장
                this.recommendationCache.set(cacheKey, data);
                
                const hasRecommendations = data.recommendations && data.recommendations.length > 0;
                console.log(`📊 ${fieldName} 추천 확인 결과:`, hasRecommendations ? `${data.recommendations.length}개` : '없음');
                
                return hasRecommendations;
            }
        } catch (error) {
            console.error('추천 문구 확인 실패:', error);
        }
        
        return false;
    }

    setupFieldListeners() {
        console.log('🎯 필드 리스너 설정 시작');
        // 기본적인 필드 리스너만 설정
    }

    createRecommendationPopup() {
        // 기존 팝업 제거
        if (this.recommendationPopup) {
            this.recommendationPopup.remove();
        }

        // 추천 팝업 생성
        const popup = document.createElement('div');
        popup.id = 'smartRecommendationPopup';
        popup.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 2000;
            background: white;
            border: 2px solid #10b981;
            border-radius: 12px;
            padding: 0;
            box-shadow: 0 10px 30px rgba(16, 185, 129, 0.2);
            width: 600px;
            max-width: 90vw;
            max-height: 80vh;
            overflow: hidden;
            display: none;
            font-family: inherit;
        `;

        popup.innerHTML = `
            <div class="popup-header" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 16px; position: relative;">
                <h6 class="mb-0" style="font-size: 1.1rem; font-weight: 600;">
                    <i class="fas fa-lightbulb me-2"></i>
                    <span id="popupTitle">스마트 추천</span>
                </h6>
                <button type="button" class="btn btn-sm position-absolute top-50 end-0 translate-middle-y me-3" 
                        id="closeRecommendationPopup" 
                        style="background: none; border: none; color: white; font-size: 1.2rem; padding: 0.25rem;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="popup-body" style="max-height: 60vh; overflow-y: auto; padding: 20px;">
                <div id="popupContent">
                    <div class="text-center py-4">
                        <i class="fas fa-spinner fa-spin fa-2x text-success mb-2"></i>
                        <p class="text-muted">추천 데이터를 불러오는 중...</p>
                    </div>
                </div>
            </div>
            
            <!-- 하단 버튼 -->
            <div class="popup-footer" style="padding: 16px; background: #f8f9fa; border-top: 1px solid #dee2e6;">
                <button type="button" class="btn btn-success w-100" id="applySelectedRecommendations" disabled>
                    <i class="fas fa-check"></i> 선택한 추천 문구 적용
                </button>
            </div>
        `;

        document.body.appendChild(popup);
        this.recommendationPopup = popup;

        // 이벤트 리스너 설정
        popup.querySelector('#closeRecommendationPopup').addEventListener('click', () => {
            this.hideRecommendationPopup();
        });

        // 배경 클릭 시 닫기
        popup.addEventListener('click', (e) => {
            if (e.target === popup) {
                this.hideRecommendationPopup();
            }
        });

        // ESC 키로 닫기
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && popup.style.display !== 'none') {
                this.hideRecommendationPopup();
            }
        });

        console.log('✅ 스마트 추천 팝업 생성 완료');
    }

    async loadAndShowRecommendations(fieldName, inputValue) {
        try {
            console.log(`🔍 ${fieldName}="${inputValue}" 실제 추천 데이터 로딩`);

            // 캐시 확인
            const cacheKey = `${fieldName}_${inputValue}`;
            let data = null;
            
            if (this.recommendationCache.has(cacheKey)) {
                data = this.recommendationCache.get(cacheKey);
                console.log('📦 캐시에서 데이터 로드');
            } else {
                // 실제 API 호출 (GET 방식으로 변경)
                const params = new URLSearchParams({
                    'input_field': fieldName,
                    'input_value': inputValue,
                    'target_fields': JSON.stringify([fieldName]),
                    'priority': 'medium'
                });

                const response = await fetch(`${this.apiUrl}?${params.toString()}`, {
                    method: 'GET'
                });

                if (response.ok) {
                    data = await response.json();
                    this.recommendationCache.set(cacheKey, data);
                    console.log('🌐 API에서 데이터 로드:', data);
                } else {
                    throw new Error(`API 호출 실패: ${response.status}`);
                }
            }

            // 팝업 표시
            this.showRecommendationPopup(fieldName, data);

        } catch (error) {
            console.error('❌ 추천 로딩 실패:', error);
            this.hideRecommendationPopup();
            alert('추천 데이터를 불러오는데 실패했습니다.');
        }
    }

    showRecommendationPopup(fieldName, data) {
        if (!this.recommendationPopup) {
            this.createRecommendationPopup();
        }

        // 현재 필드 정보 저장
        this.currentField = fieldName;

        // 팝업 제목 설정
        const title = document.getElementById('popupTitle');
        if (title) {
            title.textContent = `${this.getFieldDisplayName(fieldName)} 스마트 추천`;
        }

        // 팝업 내용 설정
        const content = document.getElementById('popupContent');
        if (content && data) {
            content.innerHTML = this.generateRecommendationContent(data);
            
            // 추천 문구 클릭 이벤트 추가
            this.setupRecommendationClickEvents();
        }

        // 팝업 표시
        this.recommendationPopup.style.display = 'block';
        console.log('✅ 스마트 추천 팝업 표시');
    }

    setupRecommendationClickEvents() {
        const recommendationItems = document.querySelectorAll('.recommendation-clickable');
        
        recommendationItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const text = item.getAttribute('data-text');
                const fieldName = this.currentField;
                
                this.applyRecommendationToField(fieldName, text);
                
                // 애니메이션 효과
                item.style.backgroundColor = '#d4edda';
                item.style.borderColor = '#c3e6cb';
                
                setTimeout(() => {
                    item.style.backgroundColor = '';
                    item.style.borderColor = '#10b981';
                }, 300);
            });
            
            // 호버 효과
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = '#f8f9fa';
                item.style.borderColor = '#059669';
                item.style.transform = 'translateX(5px)';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = '';
                item.style.borderColor = '#10b981';
                item.style.transform = 'translateX(0)';
            });
        });
    }

    applyRecommendationToField(fieldName, text) {
        const fieldElement = document.querySelector(`[name="${fieldName}"]`);
        if (!fieldElement) {
            console.error(`❌ 필드를 찾을 수 없음: ${fieldName}`);
            return;
        }

        const isMultipleAllowed = ['cautions', 'additional_info'].includes(fieldName);
        
        if (isMultipleAllowed) {
            // 주의사항, 기타표시사항은 중복 추가 가능
            const currentValue = fieldElement.value.trim();
            if (currentValue) {
                // 이미 같은 내용이 있는지 확인
                if (!currentValue.includes(text)) {
                    fieldElement.value = currentValue + '\n' + text;
                } else {
                    console.log('⚠️ 이미 같은 내용이 있습니다.');
                }
            } else {
                fieldElement.value = text;
            }
        } else {
            // 다른 필드는 덮어쓰기
            fieldElement.value = text;
        }

        // 체크박스 자동 활성화
        const checkboxId = `chk_${fieldName}`;
        const checkbox = document.getElementById(checkboxId);
        if (checkbox && !checkbox.checked) {
            checkbox.checked = true;
            console.log(`✅ 체크박스 자동 활성화: ${checkboxId}`);
        }

        console.log(`✅ 추천 문구 적용: ${fieldName} = "${text}"`);
        
        // 성공 알림
        this.showNotification('추천 문구가 적용되었습니다!', 'success');
        
        // 잠시 후 팝업 닫기 (중복 추가 가능한 필드는 열어둠)
        if (!isMultipleAllowed) {
            setTimeout(() => {
                this.hideRecommendationPopup();
            }, 800);
        }
    }

    hideRecommendationPopup() {
        if (this.recommendationPopup) {
            this.recommendationPopup.style.display = 'none';
            this.selectedItems.clear();
            console.log('✅ 스마트 추천 팝업 숨김');
        }
    }

    generateRecommendationContent(data) {
        if (!data || !data.recommendations || data.recommendations.length === 0) {
            return `
                <div class="recommendation-section">
                    <div class="text-center py-4">
                        <i class="fas fa-info-circle text-muted fa-2x mb-2"></i>
                        <p class="text-muted">해당 필드에 대한 추천 문구가 없습니다.</p>
                    </div>
                </div>
            `;
        }

        const fieldName = this.currentField;
        const isMultipleAllowed = ['cautions', 'additional_info'].includes(fieldName);
        
        return `
            <div class="recommendation-section">
                <h6 class="mb-3">
                    <i class="fas fa-lightbulb text-success me-2"></i>
                    ${this.getFieldDisplayName(fieldName)} 추천 문구
                    ${isMultipleAllowed ? '<small class="text-muted">(여러 개 선택 가능)</small>' : ''}
                </h6>
                <div class="recommendation-list" style="max-height: 400px; overflow-y: auto;">
                    ${data.recommendations.map((item, index) => {
                        const text = typeof item === 'string' ? item : (item.text || item.content || item);
                        const confidence = item.confidence || 0;
                        const source = item.source || 'auto';
                        
                        return `
                            <div class="recommendation-item p-3 border rounded mb-2 recommendation-clickable" 
                                 style="cursor: pointer; transition: all 0.2s ease; border-left: 4px solid #10b981;"
                                 data-text="${text.replace(/"/g, '&quot;')}"
                                 data-index="${index}">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div class="flex-grow-1">
                                        <div class="recommendation-text" style="font-weight: 500; margin-bottom: 4px;">
                                            ${text}
                                        </div>
                                        ${confidence > 0 ? `
                                            <small class="text-muted">
                                                <i class="fas fa-chart-bar me-1"></i>
                                                신뢰도: ${Math.round(confidence * 100)}%
                                            </small>
                                        ` : ''}
                                    </div>
                                    <div class="recommendation-action">
                                        <i class="fas fa-plus-circle text-success" style="font-size: 1.2rem;"></i>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
                <div class="mt-3 text-center">
                    <small class="text-muted">
                        <i class="fas fa-mouse-pointer me-1"></i>
                        추천 문구를 클릭하면 바로 적용됩니다
                    </small>
                </div>
            </div>
        `;
    }

    getFieldDisplayName(fieldName) {
        const fieldNames = {
            'prdlst_nm': '제품명',
            'prdlst_dcnm': '식품유형',
            'storage_method': '보관방법',
            'cautions': '주의사항',
            'bssh_nm': '제조원 소재지',
            'frmlc_mtrqlt': '용기.포장재질',
            'rawmtrl_nm_display': '원재료명(표시)',
            'content_weight': '내용량',
            'additional_info': '기타표시사항',
            'ingredient_info': '특정성분 함량',
            'prdlst_report_no': '품목보고번호',
            'country_of_origin': '원산지'
        };
        return fieldNames[fieldName] || fieldName;
    }

    showNotification(message, type = 'info') {
        // 토스트 알림 생성
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transform: translateX(100%);
            transition: transform 0.3s ease;
            max-width: 300px;
        `;
        
        // 타입별 색상 설정
        const colors = {
            success: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            warning: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
            error: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
            info: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
        };
        
        toast.style.background = colors[type] || colors.info;
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : type === 'error' ? 'times-circle' : 'info-circle'} me-2"></i>
                ${message}
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // 애니메이션으로 표시
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 100);
        
        // 3초 후 자동 제거
        setTimeout(() => {
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }
}

// 시스템 초기화
document.addEventListener('DOMContentLoaded', function() {
    if (!window.unifiedSmartRecommendation) {
        new UnifiedSmartRecommendationSystem();
    }
});
