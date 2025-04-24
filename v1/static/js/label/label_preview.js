document.addEventListener('DOMContentLoaded', function () {
    // ------------------ 팝업 유틸리티 함수 ------------------
    function openPopup(url, name, width = 1100, height = 900) {
      console.log(`팝업 열기 시도: url=${url}, name=${name}, width=${width}, height=${height}`);
      const left = (screen.width - width) / 2;
      const top = (screen.height - height) / 2;
      const popup = window.open(url, name, `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`);
      if (!popup) {
        console.error("Popup blocked by browser");
        alert('팝업이 차단되었습니다. 브라우저의 팝업 차단 설정을 확인해 주세요.');
      }
      return popup;
    }
  
    // 미리보기 팝업 설정
    const defaultSettings = {
        layout: 'horizontal',
        fontSize: 10,
        letterSpacing: 5,
        fontStretch: 90,
        dimensions: { width: 27, height: 10 },
        isTableView: true
    };

    // 팝업 열기 함수
    window.openPreviewPopup = function() {
        const form = document.getElementById("labelForm");
        if (!form) {
            console.error("Label form not found");
            return;
        }

        // 폼 데이터 수집
        const formData = new FormData(form);
        const queryParams = new URLSearchParams();

        // 폼 데이터를 URL 파라미터로 변환
        formData.forEach((value, key) => {
            if (value) {
                queryParams.append(key, value);
            }
        });

        // 체크박스 상태 추가
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            if (checkbox.checked) {
                queryParams.append(checkbox.name, "true");
            }
        });

        // URL 설정
        const url = `/label/preview/?${queryParams.toString()}`;
        console.log("Opening preview URL:", url);

        // 팝업 설정
        const width = 1100;
        const height = 900;
        const left = (window.innerWidth - width) / 2;
        const top = (window.innerHeight - height) / 2;

        // 팝업 열기
        const popup = window.open(
            url,
            "previewPopup",
            `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
        );

        if (!popup) {
            alert("팝업이 차단되었습니다. 팝업 차단을 해제해주세요.");
        }
    };

    // pairedItems 부분 수정
    const pairedItems = [];
    if (Array.isArray(items)) {
        const tableWidth = 500;
        const maxWidthPerItem = tableWidth * 0.5;
        const cellWidth = tableWidth * 0.25;

        for (let i = 0; i < items.length; i++) {
            const item1 = items[i];
            if (!item1 || !item1.label || !item1.value) {
                console.warn(`유효하지 않은 항목 at index ${i}:`, item1);
                continue;
            }

            // 현재 항목의 길이 계산
            const text1 = item1.label + (item1.value || '');
            const width1 = getTextWidth(text1, fontSize);
            const lineCount1 = getTextLineCount(item1.value || '', fontSize, cellWidth);

            if (width1 >= maxWidthPerItem || lineCount1 >= 2) {
                // 긴 항목도 2칼럼 구조로 표시
                pairedItems.push([{
                    ...item1,
                    fullWidth: true  // 내용이 긴 경우 표시용 플래그
                }]);
                continue;
            }

            const item2 = items[i + 1];
            if (item2 && item2.label && item2.value) {
                const text2 = item2.label + (item2.value || '');
                const width2 = getTextWidth(text2, fontSize);
                const lineCount2 = getTextLineCount(item2.value || '', fontSize, cellWidth);

                if (width2 <= maxWidthPerItem && lineCount2 < 2) {
                    pairedItems.push([item1, item2]);
                    i++;
                    continue;
                }
            }

            pairedItems.push([item1]);
        }
    }

    // 테이블 렌더링 부분 수정
    `<table className="w-100 border">
        <tbody>
            {pairedItems.length > 0 ? (
                pairedItems.map((pair, pairIndex) => (
                    <tr key={pairIndex}>
                        {pair[0].fullWidth ? (
                            // 긴 내용의 경우 2칼럼 구조 유지
                            <>
                                <td style={{width: '25%'}}>{pair[0].label}</td>
                                <td style={{width: '75%'}}>{pair[0].value}</td>
                            </>
                        ) : (
                            // 일반적인 경우 (1개 또는 2개 항목)
                            <>
                                <td style={{width: '25%'}}>{pair[0].label}</td>
                                <td style={{width: '25%'}}>{pair[0].value}</td>
                                {pair[1] && (
                                    <>
                                        <td style={{width: '25%'}}>{pair[1].label}</td>
                                        <td style={{width: '25%'}}>{pair[1].value}</td>
                                    </>
                                )}
                                {!pair[1] && <td colSpan="2"></td>}
                            </>
                        )}
                    </tr>
                ))
            ) : (
                <tr>
                    <td colSpan="4">표시사항 데이터가 없습니다.</td>
                </tr>
            )}
        </tbody>
    </table>`;

    // 디버깅을 위한 로깅
    console.log("label_preview.js initialized");
});

// DOMContentLoaded 이벤트에서 window에 함수 등록
document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.openPreviewPopup !== 'function') {
        console.error('Preview popup function not loaded properly');
    } else {
        console.log('Preview popup function loaded successfully');
    }
});

const nutrients = [
    { id: 'calorie', label: '열량', unit: ['kcal', 'cal'], step: 5 },
    { id: 'natrium', label: '나트륨', unit: ['mg', 'g'], step: 5, limit: 2000 },
    { id: 'carbohydrate', label: '탄수화물', unit: ['g', 'mg'], step: 0.5, limit: 324 },
    { id: 'sugar', label: '당류', unit: ['g', 'mg'], step: 0.5, limit: 100 },
    { id: 'afat', label: '지방', unit: ['g', 'mg'], step: 0.1, limit: 54 },
    { id: 'transfat', label: '트랜스지방', unit: ['g', 'mg'], step: 0.1 },
    { id: 'satufat', label: '포화지방', unit: ['g', 'mg'], step: 0.1, limit: 15 },
    { id: 'cholesterol', label: '콜레스테롤', unit: ['mg', 'g'], step: 5, limit: 300 },
    { id: 'protein', label: '단백질', unit: ['g', 'mg'], step: 0.5, limit: 55 }
];

// 영양성분 테이블 렌더링 부분 수정
const renderNutritionTable = (nutrition, baseAmount) => {
    return (
        <table className="nutrition-table">
            <thead>
                <tr>
                    <th>구성성분</th>
                    <th>함량</th>
                    <th>%영양성분 기준치</th>
                </tr>
            </thead>
            <tbody>
                {nutrition.map((item, idx) => {
                    const nutrient = nutrients.find(n => n.label === item.label);
                    const value = parseFloat(item.value);
                    let dvPercent = '';
                    
                    if (nutrient?.limit && !isNaN(value)) {
                        const adjustedValue = (value * baseAmount) / 100;
                        dvPercent = Math.round((adjustedValue / nutrient.limit) * 100);
                    }

                    return (
                        <tr key={idx}>
                            <td>{item.label}</td>
                            <td>{item.value}</td>
                            <td>{dvPercent ? `${dvPercent}%` : '-'}</td>
                        </tr>
                    );
                })}
            </tbody>
        </table>
    );
};

// 긴 내용 항목을 위한 테이블 셀 렌더링 부분 수정
const renderTableCell = (item, isLongContent) => (
    <tr>
        <td style={{width: '25%'}} className="border p-2">{item.label}</td>
        <td 
            style={{width: isLongContent ? '75%' : '25%'}} 
            className="border p-2"
            colSpan={isLongContent ? 3 : 1}
        >
            <div dangerouslySetInnerHTML={{ 
                __html: highlightText(item.value) 
            }} />
        </td>
    </tr>
);

// 내용 길이 체크 함수
const isLongContent = (text, maxLength = 50) => {
    return text.length > maxLength;
};

// 테이블 뷰 렌더링 수정
const renderTableView = (items) => {
    return (
        <table className="w-100 border">
            <tbody>
                {items.map((item, index) => {
                    const longContent = isLongContent(item.value);
                    if (longContent) {
                        return renderTableCell(item, true);
                    }

                    if (index % 2 === 0) {
                        const nextItem = items[index + 1];
                        if (!nextItem) {
                            return renderTableCell(item, false);
                        }
                        return (
                            <tr key={index}>
                                <td style={{width: '25%'}} className="border p-2">{item.label}</td>
                                <td style={{width: '25%'}} className="border p-2">
                                    <div dangerouslySetInnerHTML={{ __html: highlightText(item.value) }} />
                                </td>
                                <td style={{width: '25%'}} className="border p-2">{nextItem.label}</td>
                                <td style={{width: '25%'}} className="border p-2">
                                    <div dangerouslySetInnerHTML={{ __html: highlightText(nextItem.value) }} />
                                </td>
                            </tr>
                        );
                    }
                    return null;
                })}
            </tbody>
        </table>
    );
};