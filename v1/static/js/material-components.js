/* ==================== Google Material Style UX - JavaScript Components ====================
 * Toast / Snackbar
 * FAB (Floating Action Button)
 * Loading Overlay
 * ==================== */

(function(global) {
    'use strict';
    
    // ==================== Toast Manager ====================
    
    const ToastManager = {
        container: null,
        queue: [],
        
        init() {
            if (!this.container) {
                this.container = document.createElement('div');
                this.container.className = 'toast-container';
                document.body.appendChild(this.container);
            }
        },
        
        /**
         * Toast 표시
         * @param {string} message - 메시지
         * @param {object} options - 옵션
         * @param {string} options.type - 'default', 'success', 'error', 'warning', 'info'
         * @param {number} options.duration - 표시 시간 (ms), 0이면 수동 닫기
         * @param {string} options.action - 액션 버튼 텍스트
         * @param {function} options.onAction - 액션 버튼 클릭 콜백
         * @param {boolean} options.closable - 닫기 버튼 표시 여부
         * @param {string} options.icon - 아이콘 클래스 (bi-check-circle 등)
         */
        show(message, options = {}) {
            this.init();
            
            const defaults = {
                type: 'default',
                duration: 4000,
                action: null,
                onAction: null,
                closable: false,
                icon: null
            };
            
            const settings = { ...defaults, ...options };
            
            // 아이콘 기본값
            if (!settings.icon) {
                switch (settings.type) {
                    case 'success': settings.icon = 'bi-check-circle-fill'; break;
                    case 'error': settings.icon = 'bi-x-circle-fill'; break;
                    case 'warning': settings.icon = 'bi-exclamation-triangle-fill'; break;
                    case 'info': settings.icon = 'bi-info-circle-fill'; break;
                }
            }
            
            // Toast 엘리먼트 생성
            const toast = document.createElement('div');
            toast.className = `toast${settings.type !== 'default' ? ` toast-${settings.type}` : ''}`;
            
            let html = '';
            
            if (settings.icon) {
                html += `<i class="toast-icon bi ${settings.icon}"></i>`;
            }
            
            html += `<span class="toast-message">${message}</span>`;
            
            if (settings.action) {
                html += `<button class="toast-action">${settings.action}</button>`;
            }
            
            if (settings.closable || settings.duration === 0) {
                html += `<button class="toast-close"><i class="bi bi-x"></i></button>`;
            }
            
            toast.innerHTML = html;
            
            // 이벤트 바인딩
            const closeToast = () => {
                toast.classList.add('hiding');
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 250);
            };
            
            if (settings.action && settings.onAction) {
                toast.querySelector('.toast-action').addEventListener('click', () => {
                    settings.onAction();
                    closeToast();
                });
            }
            
            const closeBtn = toast.querySelector('.toast-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', closeToast);
            }
            
            // DOM에 추가
            this.container.appendChild(toast);
            
            // 애니메이션 트리거
            requestAnimationFrame(() => {
                toast.classList.add('show');
            });
            
            // 자동 닫기
            if (settings.duration > 0) {
                setTimeout(closeToast, settings.duration);
            }
            
            return toast;
        },
        
        // 편의 메서드
        success(message, options = {}) {
            return this.show(message, { ...options, type: 'success' });
        },
        
        error(message, options = {}) {
            return this.show(message, { ...options, type: 'error', duration: options.duration || 6000 });
        },
        
        warning(message, options = {}) {
            return this.show(message, { ...options, type: 'warning' });
        },
        
        info(message, options = {}) {
            return this.show(message, { ...options, type: 'info' });
        }
    };
    
    
    // ==================== FAB Manager ====================
    
    const FABManager = {
        /**
         * FAB 생성
         * @param {object} options - 옵션
         * @param {string} options.icon - 아이콘 클래스
         * @param {string} options.text - Extended FAB 텍스트
         * @param {function} options.onClick - 클릭 이벤트
         * @param {string} options.color - 'primary', 'secondary', 'success', 'warning', 'error'
         * @param {array} options.menu - Speed Dial 메뉴 [{icon, label, onClick}]
         * @param {string} options.position - 'bottom-right', 'bottom-left', 'top-right', 'top-left'
         */
        create(options = {}) {
            const defaults = {
                icon: 'bi-plus-lg',
                text: null,
                onClick: null,
                color: 'primary',
                menu: null,
                position: 'bottom-right'
            };
            
            const settings = { ...defaults, ...options };
            
            // 컨테이너 생성
            const container = document.createElement('div');
            container.className = 'fab-container';
            
            // 위치 설정
            const positions = {
                'bottom-right': { bottom: '24px', right: '24px' },
                'bottom-left': { bottom: '24px', left: '24px' },
                'top-right': { top: '24px', right: '24px' },
                'top-left': { top: '24px', left: '24px' }
            };
            Object.assign(container.style, positions[settings.position]);
            
            // Speed Dial 메뉴
            if (settings.menu && settings.menu.length > 0) {
                const menu = document.createElement('div');
                menu.className = 'fab-menu';
                
                settings.menu.forEach(item => {
                    const menuItem = document.createElement('div');
                    menuItem.className = 'fab-menu-item';
                    menuItem.innerHTML = `
                        <span class="fab-menu-label">${item.label}</span>
                        <button class="fab fab-mini fab-secondary">
                            <i class="bi ${item.icon}"></i>
                        </button>
                    `;
                    
                    menuItem.querySelector('.fab-mini').addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (item.onClick) item.onClick();
                        container.classList.remove('open');
                    });
                    
                    menu.appendChild(menuItem);
                });
                
                container.appendChild(menu);
            }
            
            // 메인 FAB
            const fab = document.createElement('button');
            fab.className = `fab fab-main${settings.text ? ' fab-extended' : ''}${settings.color !== 'primary' ? ` fab-${settings.color}` : ''}`;
            
            let fabHTML = `<i class="fab-icon bi ${settings.icon}"></i>`;
            if (settings.text) {
                fabHTML += `<span class="fab-text">${settings.text}</span>`;
            }
            fab.innerHTML = fabHTML;
            
            // 클릭 이벤트
            fab.addEventListener('click', () => {
                if (settings.menu && settings.menu.length > 0) {
                    container.classList.toggle('open');
                } else if (settings.onClick) {
                    settings.onClick();
                }
            });
            
            container.appendChild(fab);
            document.body.appendChild(container);
            
            // 외부 클릭 시 메뉴 닫기
            if (settings.menu) {
                document.addEventListener('click', (e) => {
                    if (!container.contains(e.target)) {
                        container.classList.remove('open');
                    }
                });
            }
            
            return {
                element: container,
                fab: fab,
                show() { container.style.display = 'flex'; },
                hide() { container.style.display = 'none'; },
                destroy() { container.remove(); }
            };
        }
    };
    
    
    // ==================== Loading Overlay ====================
    
    const LoadingOverlay = {
        overlay: null,
        
        show(message = '로딩 중...') {
            if (!this.overlay) {
                this.overlay = document.createElement('div');
                this.overlay.className = 'loading-overlay';
                this.overlay.innerHTML = `
                    <div class="loading-spinner"></div>
                    <div class="loading-text">${message}</div>
                `;
                document.body.appendChild(this.overlay);
            } else {
                this.overlay.querySelector('.loading-text').textContent = message;
            }
            
            requestAnimationFrame(() => {
                this.overlay.classList.add('show');
            });
        },
        
        hide() {
            if (this.overlay) {
                this.overlay.classList.remove('show');
            }
        },
        
        setMessage(message) {
            if (this.overlay) {
                this.overlay.querySelector('.loading-text').textContent = message;
            }
        }
    };
    
    
    // ==================== Confirm Dialog (Material Style) ====================
    
    const ConfirmDialog = {
        /**
         * 확인 다이얼로그 표시
         * @param {object} options - 옵션
         * @param {string} options.title - 제목
         * @param {string} options.message - 메시지
         * @param {string} options.confirmText - 확인 버튼 텍스트
         * @param {string} options.cancelText - 취소 버튼 텍스트
         * @param {string} options.type - 'default', 'danger', 'warning'
         * @returns {Promise<boolean>}
         */
        show(options = {}) {
            return new Promise((resolve) => {
                const defaults = {
                    title: '확인',
                    message: '계속하시겠습니까?',
                    confirmText: '확인',
                    cancelText: '취소',
                    type: 'default'
                };
                
                const settings = { ...defaults, ...options };
                
                // 기존 다이얼로그 제거
                const existing = document.querySelector('.md-dialog-overlay');
                if (existing) existing.remove();
                
                // 오버레이 생성
                const overlay = document.createElement('div');
                overlay.className = 'md-dialog-overlay';
                overlay.style.cssText = `
                    position: fixed;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background: rgba(0,0,0,0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                    opacity: 0;
                    transition: opacity 0.2s ease;
                `;
                
                // 다이얼로그 생성
                const dialog = document.createElement('div');
                dialog.className = 'md-dialog';
                dialog.style.cssText = `
                    background: white;
                    border-radius: 16px;
                    min-width: 320px;
                    max-width: 400px;
                    box-shadow: 0 24px 38px 3px rgba(0,0,0,0.14), 0 9px 46px 8px rgba(0,0,0,0.12), 0 11px 15px -7px rgba(0,0,0,0.2);
                    transform: scale(0.9);
                    transition: transform 0.2s ease;
                `;
                
                const confirmColor = settings.type === 'danger' ? '#ea4335' : 
                                    settings.type === 'warning' ? '#f9ab00' : '#1a73e8';
                
                dialog.innerHTML = `
                    <div style="padding: 24px 24px 16px;">
                        <h3 style="margin: 0 0 16px; font-size: 18px; font-weight: 500; color: #202124;">${settings.title}</h3>
                        <p style="margin: 0; font-size: 14px; color: #5f6368; line-height: 1.5;">${settings.message}</p>
                    </div>
                    <div style="padding: 8px 16px 16px; display: flex; justify-content: flex-end; gap: 8px;">
                        <button class="md-dialog-cancel" style="
                            background: transparent;
                            border: none;
                            color: #5f6368;
                            padding: 10px 16px;
                            border-radius: 8px;
                            font-size: 14px;
                            font-weight: 500;
                            cursor: pointer;
                            transition: background 0.15s ease;
                        ">${settings.cancelText}</button>
                        <button class="md-dialog-confirm" style="
                            background: ${confirmColor};
                            border: none;
                            color: white;
                            padding: 10px 20px;
                            border-radius: 8px;
                            font-size: 14px;
                            font-weight: 500;
                            cursor: pointer;
                            transition: background 0.15s ease;
                        ">${settings.confirmText}</button>
                    </div>
                `;
                
                overlay.appendChild(dialog);
                document.body.appendChild(overlay);
                
                // 애니메이션
                requestAnimationFrame(() => {
                    overlay.style.opacity = '1';
                    dialog.style.transform = 'scale(1)';
                });
                
                // 이벤트
                const close = (result) => {
                    overlay.style.opacity = '0';
                    dialog.style.transform = 'scale(0.9)';
                    setTimeout(() => {
                        overlay.remove();
                        resolve(result);
                    }, 200);
                };
                
                dialog.querySelector('.md-dialog-cancel').addEventListener('click', () => close(false));
                dialog.querySelector('.md-dialog-confirm').addEventListener('click', () => close(true));
                overlay.addEventListener('click', (e) => {
                    if (e.target === overlay) close(false);
                });
                
                // ESC 키
                const escHandler = (e) => {
                    if (e.key === 'Escape') {
                        close(false);
                        document.removeEventListener('keydown', escHandler);
                    }
                };
                document.addEventListener('keydown', escHandler);
            });
        }
    };
    
    
    // ==================== Global Export ====================
    
    global.MD = {
        Toast: ToastManager,
        FAB: FABManager,
        Loading: LoadingOverlay,
        Confirm: ConfirmDialog
    };
    
    // 편의 함수
    global.showToast = (message, options) => ToastManager.show(message, options);
    global.showLoading = (message) => LoadingOverlay.show(message);
    global.hideLoading = () => LoadingOverlay.hide();
    global.confirm = (options) => ConfirmDialog.show(options);
    
})(window);
