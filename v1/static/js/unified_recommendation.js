/**
 * 통합 스마트 추천 시스템 v5.0 - 단일 파일 완전 통합
 * - 헤더 온/오프 토글 기능
 * - 우측 플로팅 모달 추천
 * - 현재값과 추천값 비교 UI
 * - 주의사항/기타표시사항 복수 선택 지원
 * - 모든 중복 파일 제거하고 단일 시스템으로 통합
 */

class UnifiedSmartRecommendationSystem {
    constructor() {
        this.apiUrl = '/label/api/auto-fill/';
        this.phraseApiUrl = '/label/api/phrases/';
        this.recentUsageApiUrl = '/label/api/recent-usage/';
        this.currentField = null;
        this.currentFieldValue = '';
        this.debounceTimer = null;
        this.recommendationCache = new Map();
        this.phraseCache = new Map();
        this.floatingModal = null;
        
        // 스마트 추천 활성화 상태
        this.isSmartRecommendationEnabled = true;
        
        // 선택된 추천 항목 관리
        this.selectedItems = new Set();
        
        // 추천 로직 필터 상태 (기본적으로 모든 로직 활성화)
        this.activeFilters = new Set(['similar', 'recent', 'saved', 'popular']);
        
        this.init();
    }

    init() {
        console.log('🚀 통합 스마트 추천 시스템 v5.0 초기화 시작');
        
        this.setupToggleButton();
        this.createFloatingModal();
        this.setupFieldListeners();
        this.addCustomStyles();
        
        // 전역 변수로 등록
        window.unifiedSmartRecommendation = this;
        window.unifiedRecommendationSystem = this;
        
        console.log('✅ 통합 스마트 추천 시스템 v5.0 초기화 완료 - 표시사항 작성 페이지 전용');
    }

    setupToggleButton() {
        // 표시사항 작성 페이지 헤더의 스마트 추천 토글 버튼 설정
        console.log('🔍 토글 버튼 설정 시작');
        
        // DOM 로딩 완료 후 재시도 로직
        const setupButton = () => {
            const toggleBtn = document.getElementById('smartRecommendationToggleBtn');
            const toggleText = document.getElementById('smartToggleText');
            const toggleIcon = document.getElementById('smartToggleIcon');
            
            console.log('🔍 토글 버튼 요소 찾기:', {
                toggleBtn: !!toggleBtn,
                toggleText: !!toggleText,
                toggleIcon: !!toggleIcon
            });
            
            if (toggleBtn) {
                // 기존 이벤트 리스너 모두 제거
                const newBtn = toggleBtn.cloneNode(true);
                toggleBtn.parentNode.replaceChild(newBtn, toggleBtn);
                
                // 새 이벤트 리스너 추가
                newBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🖱️ 토글 버튼 클릭됨');
                    this.toggleSmartRecommendation();
                });
                
                // 초기 상태 설정
                this.updateToggleButton();
                console.log('✅ 표시사항 작성 페이지 토글 버튼 설정 완료');
                return true;
            } else {
                console.warn('❌ 토글 버튼을 찾을 수 없습니다');
                return false;
            }
        };
        
        // 즉시 실행
        if (!setupButton()) {
            // 500ms 후 재시도
            setTimeout(() => {
                if (!setupButton()) {
                    // 1초 후 재시도
                    setTimeout(() => {
                        setupButton();
                    }, 1000);
                }
            }, 500);
        }
    }

    toggleSmartRecommendation() {
        console.log('🔄 스마트 추천 토글 실행 - 현재 상태:', this.isSmartRecommendationEnabled);
        
        this.isSmartRecommendationEnabled = !this.isSmartRecommendationEnabled;
        
        console.log('🔄 스마트 추천 토글 완료 - 새 상태:', this.isSmartRecommendationEnabled);
        
        this.updateToggleButton();
        this.hideFloatingModal();
        
        // 모든 필드 아이콘 상태 업데이트
        this.updateFieldIcons();
        
        const status = this.isSmartRecommendationEnabled ? 'ON' : 'OFF';
        this.showNotification(`스마트 추천이 ${status} 되었습니다.`, 'info');
        
        console.log(`📱 스마트 추천 ${status}`);
        
        return this.isSmartRecommendationEnabled;
    }

    updateToggleButton() {
        const toggleBtn = document.getElementById('smartRecommendationToggleBtn');
        const toggleText = document.getElementById('smartToggleText');
        const toggleIcon = document.getElementById('smartToggleIcon');
        
        console.log('🎨 토글 버튼 업데이트 - 상태:', this.isSmartRecommendationEnabled);
        
        if (toggleBtn && toggleText && toggleIcon) {
            if (this.isSmartRecommendationEnabled) {
                // ON 상태: 버튼을 성공 스타일로, 아이콘을 켜진 상태로
                toggleBtn.className = 'btn btn-success btn-sm';
                toggleText.textContent = '스마트 추천';
                toggleIcon.innerHTML = '<i class="fas fa-magic text-light"></i>';
                toggleBtn.title = '스마트 추천 활성화됨 (클릭하여 끄기)';
                console.log('✅ 토글 버튼 ON 스타일 적용');
            } else {
                // OFF 상태: 버튼을 아웃라인으로, 아이콘을 꺼진 상태로
                toggleBtn.className = 'btn btn-outline-secondary btn-sm';
                toggleText.textContent = '스마트 추천';
                toggleIcon.innerHTML = '<i class="fas fa-magic text-muted"></i>';
                toggleBtn.title = '스마트 추천 비활성화됨 (클릭하여 켜기)';
                console.log('⭕ 토글 버튼 OFF 스타일 적용');
            }
        } else {
            console.warn('❌ 토글 버튼 요소를 찾을 수 없음:', {
                toggleBtn: !!toggleBtn,
                toggleText: !!toggleText,
                toggleIcon: !!toggleIcon
            });
        }
    }

    setupFieldListeners() {
        const fields = [
            'prdlst_nm', 'prdlst_dcnm', 'storage_method', 'cautions', 
            'bssh_nm', 'frmlc_mtrqlt', 'rawmtrl_nm_display', 'content_weight',
            'additional_info', 'ingredient_info', 'prdlst_report_no', 'country_of_origin'
        ];

        console.log('🎯 필드 리스너 설정 시작');

        let foundFields = 0;
        fields.forEach(field => {
            const element = document.querySelector(`[name="${field}"]`);
            if (element) {
                foundFields++;
                console.log(`✅ 필드 발견: ${field} (${element.tagName})`);
                
                // 입력 이벤트
                element.addEventListener('input', (e) => this.handleFieldInput(e, field));
                element.addEventListener('focus', (e) => this.handleFieldFocus(e, field));
                element.addEventListener('blur', (e) => this.handleFieldBlur(e, field));
                
                // 입력 필드 클릭 시 체크박스 자동 활성화
                element.addEventListener('click', (e) => this.handleFieldClick(e, field));
                
                // 필드 라벨에 추천 아이콘 추가
                this.addRecommendationIcon(element, field);
                
            } else {
                console.warn(`❌ 필드를 찾을 수 없음: ${field}`);
            }
        });

        console.log(`📊 필드 리스너 설정 완료: ${foundFields}/${fields.length}개 필드`);
        
        // 체크박스 클릭 제어 로직 추가
        this.setupCheckboxBehavior();
    }

    setupCheckboxBehavior() {
        console.log('🔄 체크박스 동작 설정 시작');
        
        const fields = [
            'prdlst_nm', 'prdlst_dcnm', 'storage_method', 'cautions', 
            'bssh_nm', 'frmlc_mtrqlt', 'rawmtrl_nm_display', 'content_weight',
            'additional_info', 'ingredient_info', 'prdlst_report_no', 'country_of_origin'
        ];

        fields.forEach(field => {
            const checkboxId = `chk_${field}`;
            const checkbox = document.getElementById(checkboxId);
            const inputField = document.querySelector(`[name="${field}"]`);
            
            if (checkbox && inputField) {
                // 체크박스 클릭 이벤트 (입력값이 있을 때만 해제 가능)
                checkbox.addEventListener('click', (e) => {
                    const hasValue = inputField.value.trim().length > 0;
                    
                    if (checkbox.checked && hasValue) {
                        // 체크 해제 시 확인
                        if (!confirm('입력된 내용이 있습니다. 정말 체크를 해제하시겠습니까?')) {
                            e.preventDefault();
                            return false;
                        }
                    }
                });
                
                // 라벨 클릭 시에도 동일한 로직 적용
                const label = document.querySelector(`label[for="${checkboxId}"]`);
                if (label) {
                    label.addEventListener('click', (e) => {
                        const hasValue = inputField.value.trim().length > 0;
                        
                        if (checkbox.checked && hasValue) {
                            // 체크 해제 시 확인
                            if (!confirm('입력된 내용이 있습니다. 정말 체크를 해제하시겠습니까?')) {
                                e.preventDefault();
                                return false;
                            }
                        }
                    });
                }
            }
        });
        
        console.log('✅ 체크박스 동작 설정 완료');
    }

    addRecommendationIcon(element, fieldName) {
        const parent = element.parentNode;
        if (!parent) return;

        // 이미 아이콘이 있으면 제거
        const existingIcon = parent.querySelector('.smart-rec-icon');
        if (existingIcon) {
            existingIcon.remove();
        }

        // 아이콘 생성
        const icon = document.createElement('span');
        icon.className = 'smart-rec-icon';
        icon.innerHTML = '<i class="fas fa-magic"></i>'; // 통일된 추천 아이콘
        icon.title = '스마트 추천 가능';
        
        // 기본 스타일 설정
        this.setIconStyle(icon);

        // 부모를 relative로 설정
        if (getComputedStyle(parent).position === 'static') {
            parent.style.position = 'relative';
        }

        parent.appendChild(icon);

        // 아이콘 클릭 시 추천 모달 표시
        icon.addEventListener('click', (e) => {
            e.stopPropagation();
            
            // 스마트추천이 비활성화된 경우 알림 표시
            if (!this.isSmartRecommendationEnabled) {
                this.showNotification('스마트추천 기능이 비활성화되어 있습니다. 헤더의 토글 버튼을 켜주세요.', 'warning');
                return;
            }
            
            const value = element.value.trim();
            if (value.length >= 1) {
                this.currentField = fieldName;
                this.currentFieldValue = value;
                this.loadAndShowRecommendations(fieldName, value);
            } else {
                this.showNotification('먼저 내용을 입력해주세요.', 'warning');
            }
        });

        // 입력 필드에 패딩 추가
        element.style.paddingRight = '40px';

        // 호버 효과
        icon.addEventListener('mouseenter', () => {
            icon.style.opacity = '1';
            icon.style.transform = 'translateY(-50%) scale(1.1)';
        });

        icon.addEventListener('mouseleave', () => {
            const baseOpacity = this.isSmartRecommendationEnabled ? '0.8' : '0.4';
            icon.style.opacity = baseOpacity;
            icon.style.transform = 'translateY(-50%) scale(1)';
        });
    }

    setIconStyle(icon) {
        const isEnabled = this.isSmartRecommendationEnabled;
        const baseColor = isEnabled ? '#28a745' : '#6c757d';
        const backgroundColor = isEnabled ? 'rgba(40, 167, 69, 0.1)' : 'rgba(108, 117, 125, 0.1)';
        const opacity = isEnabled ? '0.8' : '0.4';
        
        icon.style.cssText = `
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 14px;
            opacity: ${opacity};
            cursor: ${isEnabled ? 'pointer' : 'not-allowed'};
            z-index: 10;
            background: ${backgroundColor};
            border: 1px solid ${baseColor};
            border-radius: 50%;
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            color: ${baseColor};
        `;
        
        icon.title = isEnabled ? '스마트 추천 사용 가능' : '스마트 추천 비활성화됨';
    }

    updateFieldIcons() {
        console.log('🔄 필드 아이콘 상태 업데이트');
        const icons = document.querySelectorAll('.smart-rec-icon');
        icons.forEach(icon => {
            this.setIconStyle(icon);
        });
    }

    handleFieldClick(event, fieldName) {
        console.log(`🖱️ 필드 클릭: ${fieldName}`);
        
        // 해당 필드의 체크박스 찾기
        const checkboxId = `chk_${fieldName}`;
        const checkbox = document.getElementById(checkboxId);
        const inputField = event.target;
        
        if (checkbox && !checkbox.checked) {
            // 입력필드가 실제로 비활성화되어 있는지 확인
            if (inputField.disabled) {
                // 비활성화된 필드인 경우 안내 메시지 표시
                this.showNotification('이 항목을 사용하려면 체크박스를 클릭하세요.', 'info');
                
                // 체크박스로 포커스 이동 (선택사항)
                checkbox.focus();
                return;
            }
            
            // 일반적인 경우 자동으로 체크박스 활성화
            checkbox.checked = true;
            console.log(`✅ 체크박스 자동 활성화: ${checkboxId}`);
            
            // 체크박스 change 이벤트 발생시키기 (다른 로직들과 호환성 유지)
            const changeEvent = new Event('change', { bubbles: true });
            checkbox.dispatchEvent(changeEvent);
        }
    }

    handleFieldInput(event, fieldName) {
        if (!this.isSmartRecommendationEnabled) return;

        const value = event.target.value.trim();
        this.currentFieldValue = value;
        this.currentField = fieldName;

        // 디바운스 처리
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            if (value.length >= 2) {
                console.log(`🔍 자동 추천 로딩: ${fieldName}="${value}"`);
                this.loadAndShowRecommendations(fieldName, value);
            } else {
                this.hideFloatingModal();
            }
        }, 600);
    }

    handleFieldFocus(event, fieldName) {
        if (!this.isSmartRecommendationEnabled) return;

        this.currentField = fieldName;
        const value = event.target.value.trim();
        this.currentFieldValue = value;

        console.log(`📝 필드 포커스: ${fieldName}`);
    }

    handleFieldBlur(event, fieldName) {
        // 모달과의 상호작용을 위해 지연 처리
        setTimeout(() => {
            if (this.currentField === fieldName) {
                // 모달이 열려있지 않으면 필드 정보 초기화
                if (!this.floatingModal || this.floatingModal.style.display === 'none') {
                    this.currentField = null;
                }
            }
        }, 200);
    }

    async loadAndShowRecommendations(fieldName, inputValue) {
        try {
            console.log(`🔍 ${fieldName}="${inputValue}" 통합 추천 로딩 시작`);

            // 캐시 확인
            const cacheKey = `${fieldName}:${inputValue}`;
            if (this.recommendationCache.has(cacheKey)) {
                console.log('📦 캐시에서 데이터 로드');
                const cached = this.recommendationCache.get(cacheKey);
                this.showFloatingRecommendations(fieldName, cached);
                return;
            }

            // 모든 추천 로직을 병렬로 실행
            const [
                similarRecommendations,
                popularPhrases,
                recentUserData,
                savedPhrases
            ] = await Promise.all([
                this.loadSimilarRecommendations(fieldName, inputValue),
                this.loadPopularPhrases(fieldName),
                this.loadRecentUserData(fieldName),
                this.loadSavedPhrases(fieldName)
            ]);

            // 통합 데이터 구성
            const combinedData = {
                success: true,
                has_recommendations: true,
                input_field: fieldName,
                input_value: inputValue,
                recommendations: {
                    similar: similarRecommendations,
                    popular: popularPhrases,
                    recent: recentUserData,
                    saved: savedPhrases
                }
            };

            console.log('📄 통합 추천 데이터:', combinedData);

            // 캐시 저장
            this.recommendationCache.set(cacheKey, combinedData);
            
            // 플로팅 모달에 표시
            this.showFloatingRecommendations(fieldName, combinedData);
            console.log('✅ 통합 추천 데이터 표시 완료');

        } catch (error) {
            console.error('❌ 통합 추천 로딩 실패:', error);
            this.hideFloatingModal();
        }
    }

    // 로직 1: 수입식품 DB 기반 유사 항목 추천
    async loadSimilarRecommendations(fieldName, inputValue) {
        try {
            console.log('🌐 수입식품 DB 유사 항목 로딩...');
            
            const formData = this.collectFormData();
            const params = new URLSearchParams({
                input_field: fieldName,
                input_value: inputValue,
                ...formData, // 현재 입력된 모든 데이터 포함
                recommendation_type: 'similar',
                priority: 'high'
            });

            const response = await fetch(`${this.apiUrl}?${params}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('✅ 수입식품 DB 유사 항목:', data);
                return data.suggestions || {};
            }
            
            return {};
        } catch (error) {
            console.error('❌ 수입식품 DB 로딩 실패:', error);
            return {};
        }
    }

    // 로직 2: 많이 사용된 문구 추천
    async loadPopularPhrases(fieldName) {
        try {
            console.log('🔥 인기 문구 로딩...');
            
            const response = await fetch(`${this.phraseApiUrl}?field=${fieldName}&type=popular&limit=10`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('✅ 인기 문구:', data);
                return data.phrases || [];
            }
            
            return [];
        } catch (error) {
            console.error('❌ 인기 문구 로딩 실패:', error);
            return [];
        }
    }

    // 로직 3: 최근 사용한 항목 추천
    async loadRecentUserData(fieldName) {
        try {
            console.log('📄 최근 사용 항목 로딩...');
            
            const response = await fetch(`${this.recentUsageApiUrl}?field=${fieldName}&limit=5`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('✅ 최근 사용 항목:', data);
                return data.recent_items || [];
            }
            
            return [];
        } catch (error) {
            console.error('❌ 최근 사용 항목 로딩 실패:', error);
            return [];
        }
    }

    // 로직 4: 내 문구에 저장된 문구 추천
    async loadSavedPhrases(fieldName) {
        try {
            console.log('💾 저장된 문구 로딩...');
            
            const response = await fetch(`${this.phraseApiUrl}?field=${fieldName}&type=saved&user_only=true`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('✅ 저장된 문구:', data);
                return data.phrases || [];
            }
            
            return [];
        } catch (error) {
            console.error('❌ 저장된 문구 로딩 실패:', error);
            return [];
        }
    }

    getTargetFields(inputField) {
        const fieldMap = {
            'prdlst_nm': ['prdlst_dcnm', 'storage_method', 'cautions', 'bssh_nm'],
            'prdlst_dcnm': ['storage_method', 'cautions', 'frmlc_mtrqlt'],
            'storage_method': ['cautions'],
            'bssh_nm': ['storage_method'],
            'frmlc_mtrqlt': ['cautions', 'storage_method'],
            'rawmtrl_nm_display': ['cautions', 'storage_method'],
            'cautions': ['storage_method'],
            'content_weight': ['storage_method', 'cautions'],
            'additional_info': ['cautions'],
            'ingredient_info': ['cautions', 'storage_method']
        };
        
        return fieldMap[inputField] || ['storage_method', 'cautions'];
    }

    createFloatingModal() {
        // 기존 모달 제거
        if (this.floatingModal) {
            this.floatingModal.remove();
        }

        // 플로팅 모달 생성
        const modal = document.createElement('div');
        modal.id = 'smartRecommendationFloatingModal';
        modal.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1050;
            background: white;
            border: 2px solid #007bff;
            border-radius: 15px;
            padding: 0;
            box-shadow: 0 8px 25px rgba(0,123,255,0.3);
            min-width: 500px;
            max-width: 600px;
            max-height: 90vh;
            min-height: 650px;
            overflow: hidden;
            display: none;
            font-family: inherit;
        `;

        modal.innerHTML = `
            <div class="modal-header bg-primary text-white p-3 position-relative">
                <h6 class="mb-0">
                    <i class="fas fa-arrows-alt me-2 text-white-50" title="드래그하여 이동"></i>
                    <i class="fas fa-lightbulb me-2"></i>
                    <span id="floatingModalTitle">표시사항 스마트 추천</span>
                </h6>
                <button type="button" class="btn btn-sm position-absolute top-50 end-0 translate-middle-y me-3" 
                        id="closeFloatingModal" style="background: none; border: none; color: white; font-size: 1.2rem; padding: 0.25rem;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body p-0" style="max-height: 90vh; overflow-y: auto;">
                <div id="floatingModalContent">
                    <div class="text-center py-4">
                        <i class="fas fa-spinner fa-spin fa-2x text-primary mb-2"></i>
                        <p class="text-muted">추천 데이터를 불러오는 중...</p>
                    </div>
                </div>
            </div>
            
            <!-- 고정된 하단 버튼 -->
            <div class="modal-footer p-3 bg-light border-top" style="position: sticky; bottom: 0; z-index: 10;">
                <button type="button" class="btn btn-primary w-100" id="applySelectedRecommendations" disabled>
                    <i class="fas fa-check"></i> 적용하기
                </button>
            </div>
        `;

        document.body.appendChild(modal);
        this.floatingModal = modal;

        // 드래그 기능 추가
        this.makeModalDraggable(modal);

        // 이벤트 리스너 설정
        modal.querySelector('#closeFloatingModal').addEventListener('click', () => {
            this.hideFloatingModal();
        });

        modal.querySelector('#applySelectedRecommendations').addEventListener('click', () => {
            this.applySelectedRecommendations();
        });

        console.log('✅ 플로팅 모달 생성 완료');
    }

    makeModalDraggable(modal) {
        let isDragging = false;
        let currentX;
        let currentY;
        let initialX;
        let initialY;
        let xOffset = 0;
        let yOffset = 0;

        // 드래그 핸들 생성 (헤더 영역을 드래그 핸들로 사용)
        const header = modal.querySelector('.modal-header');
        if (header) {
            header.style.cursor = 'move';
            header.style.userSelect = 'none';
            
            header.addEventListener('mousedown', dragStart);
            document.addEventListener('mousemove', drag);
            document.addEventListener('mouseup', dragEnd);
        }

        function dragStart(e) {
            if (e.target.closest('button')) return; // 버튼 클릭 시 드래그 방지
            
            initialX = e.clientX - xOffset;
            initialY = e.clientY - yOffset;

            if (e.target === header || header.contains(e.target)) {
                isDragging = true;
                modal.style.transition = 'none';
            }
        }

        function drag(e) {
            if (isDragging) {
                e.preventDefault();
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;

                xOffset = currentX;
                yOffset = currentY;

                // 화면 경계 제한
                const rect = modal.getBoundingClientRect();
                const maxX = window.innerWidth - rect.width;
                const maxY = window.innerHeight - rect.height;

                currentX = Math.min(Math.max(0, currentX), maxX);
                currentY = Math.min(Math.max(0, currentY), maxY);

                modal.style.transform = `translate(${currentX}px, ${currentY}px)`;
                modal.style.left = 'auto';
                modal.style.top = 'auto';
            }
        }

        function dragEnd(e) {
            initialX = currentX;
            initialY = currentY;
            isDragging = false;
            modal.style.transition = '';
        }
    }

    showFloatingRecommendations(fieldName, data) {
        console.log('🎭 플로팅 모달 표시 시작:', {
            fieldName: fieldName,
            hasModal: !!this.floatingModal,
            hasRecommendations: !!data.recommendations
        });
        
        if (!this.floatingModal || !data.recommendations) {
            console.log('❌ 모달 또는 recommendations 없음');
            return;
        }

        const titleElement = this.floatingModal.querySelector('#floatingModalTitle');
        const contentElement = this.floatingModal.querySelector('#floatingModalContent');

        const fieldLabel = this.getFieldLabel(fieldName);
        titleElement.textContent = `표시사항 스마트 추천`;

        // 추천 데이터 수집
        const recommendations = this.collectRecommendations(fieldName, data);

        console.log('📈 추천 결과:', recommendations.length, '개');

        if (recommendations.length === 0) {
            console.log('❌ 추천 없음 - 모달 숨김');
            this.hideFloatingModal();
            return;
        }

        // 현재값 가져오기
        const currentValue = this.getCurrentFieldValue(fieldName);
        const isMultiSelect = ['cautions', 'additional_info'].includes(fieldName);

        // 타입별 통계 계산
        const stats = {
            similar: recommendations.filter(r => r.type === 'similar').length,
            recent: recommendations.filter(r => r.type === 'recent').length,
            saved: recommendations.filter(r => r.type === 'saved').length,
            popular: recommendations.filter(r => r.type === 'popular').length
        };

        let html = `
            <div class="recommendation-container">
                <!-- 선택된 항목 미리보기 (상단 고정) -->
                <div id="selectedItemsPreview" style="display: none; border-bottom: 1px solid #dee2e6; position: sticky; top: 0; z-index: 5; background: white;"></div>

                <!-- 4가지 로직 통계 (클릭 가능한 필터) -->
                <div class="recommendation-stats p-3 bg-light border-bottom">
                    <h6 class="mb-2">
                        <i class="fas fa-chart-bar text-primary"></i> 추천 로직별 분포
                        <small class="text-muted">(클릭하여 필터링)</small>
                    </h6>
                    <div class="row text-center">
                        <div class="col-3">
                            <div class="stat-box p-2 border rounded filter-item ${this.activeFilters.has('similar') ? 'active' : ''}" 
                                 data-filter="similar" style="cursor: pointer; transition: all 0.2s;">
                                <div class="stat-icon">🌐</div>
                                <div class="stat-count">${stats.similar}</div>
                                <small class="text-muted">식품DB</small>
                            </div>
                        </div>
                        <div class="col-3">
                            <div class="stat-box p-2 border rounded filter-item ${this.activeFilters.has('recent') ? 'active' : ''}" 
                                 data-filter="recent" style="cursor: pointer; transition: all 0.2s;">
                                <div class="stat-icon">🕒</div>
                                <div class="stat-count">${stats.recent}</div>
                                <small class="text-muted">최근 사용</small>
                            </div>
                        </div>
                        <div class="col-3">
                            <div class="stat-box p-2 border rounded filter-item ${this.activeFilters.has('saved') ? 'active' : ''}" 
                                 data-filter="saved" style="cursor: pointer; transition: all 0.2s;">
                                <div class="stat-icon">💾</div>
                                <div class="stat-count">${stats.saved}</div>
                                <small class="text-muted">저장 문구</small>
                            </div>
                        </div>
                        <div class="col-3">
                            <div class="stat-box p-2 border rounded filter-item ${this.activeFilters.has('popular') ? 'active' : ''}" 
                                 data-filter="popular" style="cursor: pointer; transition: all 0.2s;">
                                <div class="stat-icon">🔥</div>
                                <div class="stat-count">${stats.popular}</div>
                                <small class="text-muted">인기 문구</small>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 추천 목록 -->
                <div class="recommendations-section p-3">
                    <h6 class="mb-3">
                        <i class="fas fa-lightbulb text-primary"></i> 추천 목록 
                        <span class="badge bg-primary ms-2">${recommendations.length}개</span>
                        ${(fieldName === 'cautions' || fieldName === 'additional_info') ? 
                            '<span class="badge bg-success ms-1">복수선택</span>' : 
                            '<span class="badge bg-warning ms-1">단일선택</span>'}
                    </h6>
                    
                    ${(fieldName === 'cautions' || fieldName === 'additional_info') ? `
                        <div class="alert alert-info py-2 px-3 mb-3" style="font-size: 0.85em;">
                            <i class="fas fa-info-circle me-1"></i>
                            <strong>${fieldName === 'cautions' ? '주의사항' : '기타표시사항'}</strong>은 여러 개 선택 시 줄바꿈으로 연속 표시됩니다.
                        </div>
                    ` : `
                        <div class="alert alert-warning py-2 px-3 mb-3" style="font-size: 0.85em;">
                            <i class="fas fa-info-circle me-1"></i>
                            이 항목은 <strong>하나만 선택</strong>할 수 있습니다.
                        </div>
                    `}
                    
                    <div class="recommendation-items" id="recommendation-items-container" style="width: 100%;">
        `;

        // 활성화된 필터에 따라 추천 목록 필터링
        const filteredRecommendations = recommendations.filter(item => {
            const itemType = item.type || 'similar';
            return this.activeFilters.has(itemType);
        });

        // 필터링된 목록이 비어있는 경우 처리
        if (filteredRecommendations.length === 0) {
            html += `
                <div class="text-center py-4">
                    <i class="fas fa-filter fa-2x text-muted mb-2"></i>
                    <p class="text-muted">선택한 필터에 해당하는 추천 항목이 없습니다.</p>
                    <small class="text-muted">다른 로직을 선택해보세요.</small>
                </div>
            `;
        } else {
            filteredRecommendations.forEach((item, index) => {
                // 각 추천 항목의 타겟 필드에 해당하는 현재값 가져오기
                const targetField = item.targetField || item.field || fieldName;
                const itemCurrentValue = this.getCurrentFieldValue(targetField);
                const isCurrentSame = itemCurrentValue && itemCurrentValue.trim() === item.content.trim();
                const itemId = `rec_${fieldName}_${index}`;
                const additionalInfo = this.getAdditionalInfo(item);

                html += `
                    <div class="recommendation-item mb-2 p-3 border rounded ${isCurrentSame ? 'border-success bg-light' : ''}" 
                         data-content="${this.escapeHtml(item.content)}"
                         data-target-field="${targetField}"
                         data-filter-type="${item.type || 'similar'}"
                         style="width: 100%; display: block;">
                        
                        <div class="d-flex align-items-start w-100">
                            <input type="checkbox" class="form-check-input me-3 flex-shrink-0" id="${itemId}" 
                                   data-content="${this.escapeHtml(item.content)}"
                                   data-target-field="${targetField}"
                                   ${isCurrentSame ? 'checked' : ''}
                                   onchange="unifiedSmartRecommendation.toggleRecommendationSelection(this)"
                                   style="margin-top: 2px;">
                            
                            <span class="me-3 flex-shrink-0" style="font-size: 1.0em;">${item.icon}</span>
                            
                            <div class="flex-grow-1" style="min-width: 0;">
                                <div class="fw-bold text-dark mb-1" style="word-break: break-word; line-height: 1.3;">
                                    ${this.getFieldLabel(targetField)} : ${this.escapeHtml(
                                        targetField === 'country_of_origin' ? this.convertCountryCodeToKorean(item.content) : item.content
                                    )}
                                </div>
                                <small class="text-muted d-block" style="word-break: break-word; line-height: 1.2;">
                                    출처 : ${item.subtitle}${additionalInfo ? `, ${additionalInfo}` : ''}
                                </small>
                                ${isCurrentSame ? `
                                    <span class="badge bg-success mt-1">
                                        <i class="fas fa-check"></i> 현재값과 동일
                                    </span>
                                ` : ''}
                            </div>
                        </div>
                        
                        <!-- 현재값과 다른 경우에만 상태 표시 -->
                        ${!isCurrentSame && itemCurrentValue && itemCurrentValue.trim() ? `
                            <div class="mt-2 ms-5">
                                <div class="alert alert-warning py-1 px-2 mb-0" style="font-size: 0.8em;">
                                    <i class="fas fa-exchange-alt me-1"></i>현재값: "${this.escapeHtml(this.truncateText(itemCurrentValue, 30))}" → 추천값으로 변경됩니다
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `;
            });
        }

        html += `
                    </div>
                </div>
            </div>
        `;

        contentElement.innerHTML = html;

        // 선택 상태 초기화 및 현재값과 동일한 항목들 자동 선택
        this.selectedItems.clear();
        
        // 현재값과 동일한 항목들을 selectedItems에 추가
        filteredRecommendations.forEach((item, index) => {
            const targetField = item.targetField || item.field || fieldName;
            const itemCurrentValue = this.getCurrentFieldValue(targetField);
            const isCurrentSame = itemCurrentValue && itemCurrentValue.trim() === item.content.trim();
            
            if (isCurrentSame) {
                const key = `${targetField}:${item.content}`;
                this.selectedItems.add(key);
            }
        });
        
        this.updateApplyButton();

        // 필터 클릭 이벤트 리스너 추가
        this.setupFilterListeners();

        // 모달 표시
        this.floatingModal.style.display = 'block';
        
        console.log(`✅ 플로팅 모달 표시: ${fieldLabel} (${recommendations.length}개 추천)`);
    }

    collectRecommendations(fieldName, data) {
        const recommendations = [];
        
        console.log('🔍 통합 추천 데이터 수집 시작:', {
            fieldName: fieldName,
            hasRecommendations: !!data.recommendations
        });
        
        if (!data.recommendations) {
            console.log('❌ recommendations 데이터 없음');
            return recommendations;
        }

        // 1. 수입식품 DB 기반 유사 항목 (최우선)
        if (data.recommendations.similar) {
            console.log('🌐 수입식품 DB 유사 항목 처리');
            this.processSimilarRecommendations(data.recommendations.similar, recommendations);
        }

        // 2. 내가 최근 사용한 항목 (높은 우선순위)
        if (data.recommendations.recent && data.recommendations.recent.length > 0) {
            console.log('� 최근 사용 항목 처리');
            data.recommendations.recent.forEach(item => {
                if (item.content && item.field) {
                    recommendations.push({
                        type: 'recent',
                        content: item.content,
                        subtitle: `최근 사용함`,
                        icon: '🕒',
                        field: item.field,
                        targetField: item.field,
                        priority: 2,
                        lastUsed: item.last_used
                    });
                }
            });
        }

        // 3. 내 저장된 문구 (중간 우선순위)
        if (data.recommendations.saved && data.recommendations.saved.length > 0) {
            console.log('💾 저장된 문구 처리');
            data.recommendations.saved.forEach(item => {
                if (item.content && item.field) {
                    recommendations.push({
                        type: 'saved',
                        content: item.content,
                        subtitle: `내 저장 문구`,
                        icon: '�',
                        field: item.field,
                        targetField: item.field,
                        priority: 3,
                        phraseId: item.id
                    });
                }
            });
        }

        // 4. 인기 문구 (낮은 우선순위)
        if (data.recommendations.popular && data.recommendations.popular.length > 0) {
            console.log('� 인기 문구 처리');
            data.recommendations.popular.forEach(item => {
                if (item.content && item.field) {
                    recommendations.push({
                        type: 'popular',
                        content: item.content,
                        subtitle: `인기 문구`,
                        icon: '🔥',
                        field: item.field,
                        targetField: item.field,
                        priority: 4,
                        usageCount: item.usage_count
                    });
                }
            });
        }

        // 우선순위별 정렬 및 중복 제거
        const uniqueRecommendations = this.removeDuplicatesAndSort(recommendations);
        
        console.log('📊 수집된 통합 추천 개수:', uniqueRecommendations.length);
        console.log('📋 추천 타입별 분포:', {
            similar: uniqueRecommendations.filter(r => r.type === 'similar').length,
            recent: uniqueRecommendations.filter(r => r.type === 'recent').length,
            saved: uniqueRecommendations.filter(r => r.type === 'saved').length,
            popular: uniqueRecommendations.filter(r => r.type === 'popular').length
        });

        return uniqueRecommendations;
    }

    processSimilarRecommendations(similarData, recommendations) {
        if (similarData && typeof similarData === 'object') {
            Object.entries(similarData).forEach(([field, suggestionArray]) => {
                if (Array.isArray(suggestionArray)) {
                    suggestionArray.forEach(suggestion => {
                        const sources = suggestion.sources || [];
                        const content = suggestion.value || suggestion.content;
                        
                        if (content) {
                            recommendations.push({
                                type: 'similar',
                                content: content,
                                subtitle: `식품DB 기반`,
                                icon: '🌐',
                                field: field,
                                targetField: field,
                                priority: 1,
                                similarity: suggestion.similarity || 0.8
                            });
                        }
                    });
                }
            });
        }
    }

    removeDuplicatesAndSort(recommendations) {
        // 내용과 필드가 같은 항목 제거 (우선순위 높은 것만 유지)
        const uniqueMap = new Map();
        
        recommendations.forEach(rec => {
            const key = `${rec.targetField}:${rec.content}`;
            if (!uniqueMap.has(key) || uniqueMap.get(key).priority > rec.priority) {
                uniqueMap.set(key, rec);
            }
        });

        // 우선순위별로 정렬 후 반환 (우선순위 높은 것부터)
        return Array.from(uniqueMap.values()).sort((a, b) => {
            if (a.priority !== b.priority) {
                return a.priority - b.priority;
            }
            // 같은 우선순위 내에서는 추가 기준으로 정렬
            if (a.type === 'similar' && b.type === 'similar') {
                return (b.similarity || 0) - (a.similarity || 0);
            }
            if (a.type === 'popular' && b.type === 'popular') {
                return (b.usageCount || 0) - (a.usageCount || 0);
            }
            return 0;
        });
    }

    toggleRecommendationSelection(checkbox) {
        const content = checkbox.dataset.content;
        const targetField = checkbox.dataset.targetField;
        
        const key = `${targetField}:${content}`;
        
        // 중복 선택 방지 로직 (주의사항과 기타표시사항만 중복 허용)
        const isMultiSelectField = targetField === 'cautions' || targetField === 'additional_info';
        
        if (checkbox.checked) {
            if (!isMultiSelectField) {
                // 단일 선택 필드: 같은 필드의 다른 체크박스들 해제
                const otherCheckboxes = this.floatingModal.querySelectorAll(
                    `input[data-target-field="${targetField}"]:not(#${checkbox.id})`
                );
                otherCheckboxes.forEach(otherBox => {
                    if (otherBox.checked) {
                        otherBox.checked = false;
                        const otherKey = `${otherBox.dataset.targetField}:${otherBox.dataset.content}`;
                        this.selectedItems.delete(otherKey);
                    }
                });
            }
            this.selectedItems.add(key);
        } else {
            this.selectedItems.delete(key);
        }
        
        this.updateApplyButton();
        console.log(`📝 ${isMultiSelectField ? '복수선택' : '단일선택'} 토글: ${targetField} = "${content}" (${checkbox.checked ? '선택' : '해제'})`);
    }

    updateApplyButton() {
        const btn = this.floatingModal?.querySelector('#applySelectedRecommendations');
        const previewContainer = this.floatingModal?.querySelector('#selectedItemsPreview');
        
        if (btn) {
            btn.disabled = this.selectedItems.size === 0;
            
            if (this.selectedItems.size > 0) {
                // 선택된 항목들을 필드별로 그룹화하여 미리보기 표시
                const fieldGroups = {};
                this.selectedItems.forEach(item => {
                    const [fieldName, content] = item.split(':');
                    if (!fieldGroups[fieldName]) {
                        fieldGroups[fieldName] = [];
                    }
                    fieldGroups[fieldName].push(content);
                });
                
                // 상단 미리보기 HTML 생성
                let previewHtml = '<div class="alert alert-info py-2 px-3 mb-0" style="font-size: 0.8em;"><h6 class="mb-2">적용 미리보기:</h6>';
                
                Object.entries(fieldGroups).forEach(([fieldName, contents]) => {
                    const fieldLabel = this.getFieldLabel(fieldName);
                    const isMultiLine = fieldName === 'cautions' || fieldName === 'additional_info';
                    const separator = isMultiLine ? ' → ' : ', ';
                    
                    // 원산지인 경우 국가코드를 한글로 변환
                    const processedContents = fieldName === 'country_of_origin' 
                        ? contents.map(content => this.convertCountryCodeToKorean(content))
                        : contents;
                    
                    const previewText = processedContents.join(separator);
                    
                    previewHtml += `
                        <div class="mb-1">
                            <strong>${fieldLabel}:</strong> 
                            <span class="text-muted">${this.escapeHtml(this.truncateText(previewText, 50))}</span>
                            ${isMultiLine ? ' <small class="badge bg-secondary">줄바꿈</small>' : ''}
                        </div>
                    `;
                });
                
                previewHtml += '</div>';
                
                // 상단 미리보기 컨테이너 업데이트
                if (previewContainer) {
                    previewContainer.innerHTML = previewHtml;
                    previewContainer.style.display = 'block';
                }
                
                btn.innerHTML = `<i class="fas fa-check"></i> 적용하기 (${this.selectedItems.size}개)`;
            } else {
                // 선택된 항목이 없을 때
                if (previewContainer) {
                    previewContainer.style.display = 'none';
                }
                
                btn.innerHTML = '<i class="fas fa-check"></i> 적용하기';
            }
        }
    }

    setupFilterListeners() {
        // 필터 아이템 클릭 이벤트 (이벤트 위임 사용)
        if (this.floatingModal) {
            this.floatingModal.addEventListener('click', (e) => {
                const filterItem = e.target.closest('.filter-item');
                if (filterItem) {
                    const filterType = filterItem.dataset.filter;
                    this.toggleFilter(filterType);
                    e.preventDefault();
                    e.stopPropagation();
                }
            });
        }
    }

    toggleFilter(filterType) {
        if (this.activeFilters.has(filterType)) {
            this.activeFilters.delete(filterType);
        } else {
            this.activeFilters.add(filterType);
        }
        
        // 필터 상태에 따라 UI 업데이트
        this.updateFilterUI();
        this.updateRecommendationList();
    }

    updateFilterUI() {
        if (!this.floatingModal) return;
        
        const filterItems = this.floatingModal.querySelectorAll('.filter-item');
        filterItems.forEach(item => {
            const filterType = item.dataset.filter;
            if (this.activeFilters.has(filterType)) {
                item.classList.add('active');
                item.style.backgroundColor = '#e3f2fd';
                item.style.borderColor = '#2196f3';
            } else {
                item.classList.remove('active');
                item.style.backgroundColor = '';
                item.style.borderColor = '';
            }
        });
    }

    updateRecommendationList() {
        if (!this.floatingModal) return;
        
        const recommendationItems = this.floatingModal.querySelectorAll('.recommendation-item');
        let visibleCount = 0;
        
        recommendationItems.forEach(item => {
            const filterType = item.dataset.filterType || 'similar';
            if (this.activeFilters.has(filterType)) {
                item.style.display = 'block';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });
        
        // 빈 상태 메시지 처리
        const container = this.floatingModal.querySelector('#recommendation-items-container');
        const emptyMessage = container?.querySelector('.text-center');
        
        if (visibleCount === 0 && !emptyMessage) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'text-center py-4 empty-filter-message';
            emptyDiv.innerHTML = `
                <i class="fas fa-filter fa-2x text-muted mb-2"></i>
                <p class="text-muted">선택한 필터에 해당하는 추천 항목이 없습니다.</p>
                <small class="text-muted">다른 로직을 선택해보세요.</small>
            `;
            container?.appendChild(emptyDiv);
        } else if (visibleCount > 0) {
            // 빈 메시지 제거
            const emptyMsg = container?.querySelector('.empty-filter-message');
            if (emptyMsg) {
                emptyMsg.remove();
            }
        }
    }

    applySelectedRecommendations() {
        if (this.selectedItems.size === 0) {
            this.showNotification('선택된 항목이 없습니다.', 'warning');
            return;
        }

        let appliedCount = 0;
        const appliedFields = new Set();

        // 선택된 항목들을 필드별로 그룹화
        const fieldGroups = {};
        this.selectedItems.forEach(item => {
            const [fieldName, content] = item.split(':');
            if (!fieldGroups[fieldName]) {
                fieldGroups[fieldName] = [];
            }
            fieldGroups[fieldName].push(content);
        });

        console.log('📋 적용할 필드 그룹:', fieldGroups);

        // 각 필드에 값 적용
        Object.entries(fieldGroups).forEach(([fieldName, contents]) => {
            const element = document.querySelector(`[name="${fieldName}"]`);
            if (!element) {
                console.warn(`❌ 필드를 찾을 수 없음: ${fieldName}`);
                return;
            }

            // 현재 값 가져오기
            const currentValue = element.value.trim();
            
            // 원산지인 경우 국가코드를 한글로 변환
            const processedContents = fieldName === 'country_of_origin' 
                ? contents.map(content => this.convertCountryCodeToKorean(content))
                : contents;
            
            let newValue;
            
            // 주의사항과 기타표시사항은 특별 처리 (연속 표시)
            if (fieldName === 'cautions' || fieldName === 'additional_info') {
                if (processedContents.length === 1) {
                    if (currentValue) {
                        // 기존 값이 있으면 연속으로 추가 (줄바꿈으로 구분)
                        newValue = currentValue + '\n' + processedContents[0];
                    } else {
                        // 기존 값이 없으면 새로 설정
                        newValue = processedContents[0];
                    }
                } else {
                    // 복수 항목: 기존 값에 각각을 줄바꿈으로 추가
                    const newContents = processedContents.filter(content => !currentValue.includes(content)); // 중복 제거
                    if (currentValue) {
                        newValue = currentValue + '\n' + newContents.join('\n');
                    } else {
                        newValue = processedContents.join('\n');
                    }
                }
            } else {
                // 다른 필드들은 기존 로직 유지
                if (processedContents.length === 1) {
                    // 단일 항목: 그대로 적용
                    newValue = processedContents[0];
                } else {
                    // 복수 항목: 쉼표로 구분하여 연결
                    if (currentValue && !processedContents.includes(currentValue)) {
                        // 기존 값이 있고 선택 항목에 없으면 기존 값도 포함
                        newValue = [currentValue, ...processedContents].join(', ');
                    } else {
                        newValue = processedContents.join(', ');
                    }
                }
            }

            // 값 적용
            element.value = newValue;
            element.dispatchEvent(new Event('change', { bubbles: true }));
            
            // 시각적 효과
            this.highlightField(element);
            
            appliedCount += processedContents.length;
            appliedFields.add(this.getFieldLabel(fieldName));
            
            console.log(`✅ 적용 완료: ${fieldName} = "${newValue}"`);
        });

        const fieldsList = Array.from(appliedFields).join(', ');
        this.showNotification(`${fieldsList}에 ${appliedCount}개 항목이 적용되었습니다.`, 'success');
        
        // 모달 닫기
        this.hideFloatingModal();
        
        console.log(`✅ 전체 추천 적용 완료: ${appliedCount}개 항목, ${appliedFields.size}개 필드`);
    }

    hideFloatingModal() {
        if (this.floatingModal) {
            this.floatingModal.style.display = 'none';
            this.selectedItems.clear();
        }
    }

    highlightField(element) {
        element.style.transition = 'all 0.3s ease';
        element.style.borderColor = '#28a745';
        element.style.boxShadow = '0 0 10px rgba(40, 167, 69, 0.3)';
        
        setTimeout(() => {
            element.style.borderColor = '';
            element.style.boxShadow = '';
        }, 2000);
    }

    showNotification(message, type = 'info', duration = 3000) {
        console.log(`📢 알림: ${message} (${type})`);
        
        // 기존 알림이 있으면 제거
        const existingToast = document.querySelector('.unified-smart-toast');
        if (existingToast) {
            existingToast.remove();
        }
        
        // 토스트 알림 표시
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed unified-smart-toast`;
        toast.style.cssText = `
            top: 20px; right: 20px; z-index: 9999;
            min-width: 300px; opacity: 0; transition: opacity 0.3s ease;
            border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        
        const iconMap = {
            'success': 'check-circle',
            'error': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle'
        };
        
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${iconMap[type] || 'info-circle'} me-2"></i>
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // 페이드 인
        setTimeout(() => toast.style.opacity = '1', 10);
        
        // 자동 제거
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.opacity = '0';
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.remove();
                    }
                }, 300);
            }
        }, duration);
    }

    addCustomStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .smart-rec-icon:hover {
                transform: translateY(-50%) scale(1.1) !important;
                opacity: 1 !important;
            }
            
            .recommendation-item {
                transition: all 0.2s ease;
                cursor: pointer;
            }
            
            .recommendation-item:hover {
                border-color: #007bff !important;
                box-shadow: 0 2px 8px rgba(0,123,255,0.2) !important;
                transform: translateY(-1px);
            }
            
            .recommendation-item.border-success {
                background-color: #f8fff9 !important;
                border-width: 2px !important;
            }
            
            #smartRecommendationFloatingModal {
                backdrop-filter: blur(2px);
            }
            
            .current-value-section {
                border-bottom: 1px solid #dee2e6 !important;
            }
            
            .filter-item {
                transition: all 0.2s ease !important;
                cursor: pointer !important;
            }
            
            .filter-item:hover {
                background-color: #f0f8ff !important;
                border-color: #007bff !important;
                transform: translateY(-1px) !important;
            }
            
            .filter-item.active {
                background-color: #e3f2fd !important;
                border-color: #2196f3 !important;
                border-width: 2px !important;
                box-shadow: 0 2px 4px rgba(33, 150, 243, 0.3) !important;
            }
            
            .filter-item.active .stat-icon {
                filter: brightness(1.2) !important;
            }
        `;
        document.head.appendChild(style);
    }

    // 유틸리티 메서드들
    getCSRFToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                         document.querySelector('meta[name=csrf-token]')?.getAttribute('content') ||
                         document.querySelector('#csrf_token')?.value;
        
        if (!csrfToken) {
            console.warn('⚠️ CSRF 토큰을 찾을 수 없습니다');
        }
        
        return csrfToken;
    }

    collectFormData() {
        const formData = {};
        const form = document.getElementById('labelForm') || document.querySelector('form');
        
        if (form) {
            const formDataObj = new FormData(form);
            for (let [key, value] of formDataObj.entries()) {
                formData[key] = value;
            }
        }
        
        return formData;
    }

    getFieldLabel(fieldName) {
        const labels = {
            'prdlst_nm': '제품명',
            'prdlst_dcnm': '식품유형',
            'storage_method': '보관방법',
            'cautions': '주의사항',
            'bssh_nm': '제조원',
            'frmlc_mtrqlt': '용기.포장재질',
            'rawmtrl_nm_display': '원재료명(표시)',
            'content_weight': '내용량',
            'additional_info': '기타표시사항',
            'ingredient_info': '성분정보',
            'prdlst_report_no': '품목제조신고번호',
            'country_of_origin': '원산지'
        };
        return labels[fieldName] || fieldName;
    }

    getCurrentFieldValue(fieldName) {
        const element = document.querySelector(`[name="${fieldName}"]`);
        return element ? element.value.trim() : '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateText(text, maxLength = 50) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    // 국가 코드를 한글명으로 변환
    convertCountryCodeToKorean(countryCode) {
        if (!countryCode) return countryCode;
        
        const countryMap = {
            'KR': '대한민국', 'KO': '대한민국', 'KOREA': '대한민국', '한국': '대한민국',
            'US': '미국', 'USA': '미국', 'UNITED STATES': '미국',
            'CN': '중국', 'CHINA': '중국',
            'JP': '일본', 'JAPAN': '일본',
            'DE': '독일', 'GERMANY': '독일',
            'FR': '프랑스', 'FRANCE': '프랑스',
            'IT': '이탈리아', 'ITALY': '이탈리아',
            'ES': '스페인', 'SPAIN': '스페인',
            'UK': '영국', 'GB': '영국', 'UNITED KINGDOM': '영국',
            'AU': '호주', 'AUSTRALIA': '호주',
            'CA': '캐나다', 'CANADA': '캐나다',
            'BR': '브라질', 'BRAZIL': '브라질',
            'IN': '인도', 'INDIA': '인도',
            'TH': '태국', 'THAILAND': '태국',
            'VN': '베트남', 'VIETNAM': '베트남',
            'PH': '필리핀', 'PHILIPPINES': '필리핀',
            'MY': '말레이시아', 'MALAYSIA': '말레이시아',
            'SG': '싱가포르', 'SINGAPORE': '싱가포르',
            'ID': '인도네시아', 'INDONESIA': '인도네시아',
            'NZ': '뉴질랜드', 'NEW ZEALAND': '뉴질랜드',
            'MX': '멕시코', 'MEXICO': '멕시코',
            'CH': '스위스', 'SWITZERLAND': '스위스',
            'AT': '오스트리아', 'AUSTRIA': '오스트리아',
            'BE': '벨기에', 'BELGIUM': '벨기에',
            'NL': '네덜란드', 'NETHERLANDS': '네덜란드',
            'SE': '스웨덴', 'SWEDEN': '스웨덴',
            'NO': '노르웨이', 'NORWAY': '노르웨이',
            'DK': '덴마크', 'DENMARK': '덴마크',
            'FI': '핀란드', 'FINLAND': '핀란드',
            'PL': '폴란드', 'POLAND': '폴란드',
            'CZ': '체코', 'CZECH REPUBLIC': '체코',
            'HU': '헝가리', 'HUNGARY': '헝가리',
            'RU': '러시아', 'RUSSIA': '러시아',
            'UA': '우크라이나', 'UKRAINE': '우크라이나',
            'TR': '터키', 'TURKEY': '터키',
            'IL': '이스라엘', 'ISRAEL': '이스라엘',
            'SA': '사우디아라비아', 'SAUDI ARABIA': '사우디아라비아',
            'AE': '아랍에미리트', 'UAE': '아랍에미리트',
            'EG': '이집트', 'EGYPT': '이집트',
            'ZA': '남아프리카공화국', 'SOUTH AFRICA': '남아프리카공화국',
            'AR': '아르헨티나', 'ARGENTINA': '아르헨티나',
            'CL': '칠레', 'CHILE': '칠레',
            'PE': '페루', 'PERU': '페루',
            'CO': '콜롬비아', 'COLOMBIA': '콜롬비아',
            'EC': '에콰도르', 'ECUADOR': '에콰도르',
            'UY': '우루과이', 'URUGUAY': '우루과이',
            'PY': '파라과이', 'PARAGUAY': '파라과이',
            'BO': '볼리비아', 'BOLIVIA': '볼리비아',
            'VE': '베네수엘라', 'VENEZUELA': '베네수엘라'
        };
        
        const trimmedCode = countryCode.trim().toUpperCase();
        
        // 직접 매핑 확인
        if (countryMap[trimmedCode]) {
            return countryMap[trimmedCode];
        }
        
        // 이미 한글인 경우 그대로 반환
        if (/[가-힣]/.test(countryCode)) {
            return countryCode;
        }
        
        // 매핑되지 않은 경우 원본 반환
        return countryCode;
    }

    // 기존 호환성을 위한 메서드들
    enableSmartRecommendation() {
        this.isSmartRecommendationEnabled = true;
        this.updateToggleButton();
        console.log('📱 스마트 추천 활성화');
    }

    disableSmartRecommendation() {
        this.isSmartRecommendationEnabled = false;
        this.updateToggleButton();
        this.hideFloatingModal();
        console.log('📱 스마트 추천 비활성화');
    }

    isSmartRecommendationActive() {
        return this.isSmartRecommendationEnabled;
    }

    getAdditionalInfo(rec) {
        switch (rec.type) {
            case 'similar':
                return rec.similarity ? `유사도 ${Math.round(rec.similarity * 100)}%` : '';
            case 'popular':
                return rec.usageCount ? `${rec.usageCount}회 사용됨` : '';
            case 'recent':
                return rec.lastUsed ? `최근 사용: ${this.formatDate(rec.lastUsed)}` : '';
            case 'saved':
                return '내 문구';
            default:
                return '';
        }
    }

    formatDate(dateStr) {
        try {
            const date = new Date(dateStr);
            const now = new Date();
            const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
            
            if (diffDays === 0) return '오늘';
            if (diffDays === 1) return '어제';
            if (diffDays < 7) return `${diffDays}일 전`;
            if (diffDays < 30) return `${Math.floor(diffDays / 7)}주 전`;
            return `${Math.floor(diffDays / 30)}개월 전`;
        } catch (e) {
            return dateStr;
        }
    }
}

// 전역 인스턴스 생성
let unifiedSmartRecommendation;

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 통합 스마트 추천 시스템 로딩...');
    
    // 기존 인스턴스들 정리
    if (window.unifiedSmartRecommendation) {
        console.log('🧹 기존 인스턴스 정리 중...');
    }
    
    // DOM이 완전히 로드된 후 약간의 지연을 두고 초기화
    setTimeout(() => {
        try {
            // 새 인스턴스 생성
            unifiedSmartRecommendation = new UnifiedSmartRecommendationSystem();
            
            // 전역 함수들 등록
            window.toggleSmartRecommendation = function() {
                return unifiedSmartRecommendation.toggleSmartRecommendation();
            };
            
            window.enableSmartRecommendation = function() {
                return unifiedSmartRecommendation.enableSmartRecommendation();
            };
            
            window.disableSmartRecommendation = function() {
                return unifiedSmartRecommendation.disableSmartRecommendation();
            };
            
            window.isSmartRecommendationActive = function() {
                return unifiedSmartRecommendation.isSmartRecommendationActive();
            };
            
            console.log('✅ 통합 스마트 추천 시스템 완전 초기화 완료');
            console.log('💡 사용법: 필드에 입력하거나 🎯 아이콘을 클릭하여 스마트 추천을 사용하세요');
        } catch (error) {
            console.error('❌ 스마트 추천 시스템 초기화 실패:', error);
        }
    }, 100);
});

console.log('📦 통합 스마트 추천 시스템 v5.0 로드 완료 - 표시사항 작성 페이지 전용, 모든 중복 파일 정리됨');
