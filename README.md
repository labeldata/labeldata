function fetchKoreanLabelingByDateRange() {
  const serviceKey = 'W%2Fa0WaIQ8wchtXd0%2F8ULXkcbd5KQ%2BM2AkNERlMgwDJpuFHGEtzVOjnRG%2BoAjJ4Nu5gpveEmfEEOD8CvRPPlyCA%3D%3D';
  const baseUrl = 'https://apis.data.go.kr/1471000/IprtFoodPrdtKoreanLabelingItem/getIprtFoodPrdtKoreanLabelingItem';
  const numOfRows = 100;
  const maxPages = 300; // 최대 페이지 수
  const sheetName = '수입식품';

  // ✅ 수동 날짜 설정
  const startDate = '20200101';
  const endDate = '20250325';

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName) || SpreadsheetApp.getActiveSpreadsheet().insertSheet(sheetName);
  let headerWritten = sheet.getLastRow() > 0;
  let headers = headerWritten ? sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0] : [];

  let allRows = []; // 데이터를 한 번에 저장할 배열

  for (let pageNo = 1; pageNo <= maxPages; pageNo++) {
    const url = `${baseUrl}?serviceKey=${serviceKey}&pageNo=${pageNo}&numOfRows=${numOfRows}`;
    Logger.log(`🔄 페이지 ${pageNo} 호출 중...`);

    try {
      const response = UrlFetchApp.fetch(url, {
        method: 'get',
        muteHttpExceptions: true,
        headers: { accept: '*/*' }
      });

      const xml = response.getContentText();
      const document = XmlService.parse(xml);
      const root = document.getRootElement();
      const body = root.getChild('body');
      const items = body?.getChild('items')?.getChildren('item');
      if (!items || items.length === 0) break;

      let rows = [];

      for (let i = 0; i < items.length; i++) {
        let obj = {};
        items[i].getChildren().forEach(child => {
          obj[child.getName()] = child.getText();
        });

        const category = obj['DCL_PRDUCT_SE_CD_NM'];
        const procsDate = obj['PROCS_DTM'];

        if (category !== '가공식품' && category !== '식품첨가물') continue;
        if (!procsDate || procsDate < startDate || procsDate > endDate) continue;

        if (!headerWritten) headers = Object.keys(obj);
        rows.push(headers.map(h => obj[h] || ""));
      }

      if (rows.length > 0) {
        allRows = allRows.concat(rows); // 데이터 누적
        Logger.log(`✅ 페이지 ${pageNo} 저장 완료 (${rows.length}건)`);
      } else {
        Logger.log(`⚠️ 페이지 ${pageNo}: 필터 통과 항목 없음`);
      }

    } catch (e) {
      Logger.log(`❌ 오류 발생 - 페이지 ${pageNo}: ${e}`);
      break;
    }
  }

  // 데이터를 한 번에 시트에 추가
  if (allRows.length > 0) {
    if (!headerWritten) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    }
    sheet.getRange(sheet.getLastRow() + 1, 1, allRows.length, headers.length).setValues(allRows);
    Logger.log(`✅ ${allRows.length}개의 데이터 입력 완료`);
  } else {
    Logger.log("입력할 데이터가 없습니다.");
  }
}
