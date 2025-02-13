import requests
from bs4 import BeautifulSoup
from disposition.models import Administrativedisposition


class SeochoCrawler:
    """서초구 홈페이지 크롤러"""

    def __init__(self, target_url):
        self.target_url = target_url

    def fetch_page(self, url):
        """URL에서 HTML 페이지 가져오기"""
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

    def crawl(self):
        """크롤링 로직"""
        soup = self.fetch_page(self.target_url)
        rows = soup.select('table.tbl_type01 tbody tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue

            Administrativedisposition.objects.create(
                disposition_date=cols[0].get_text(strip=True),
                industry=cols[1].get_text(strip=True),
                business_name=cols[2].get_text(strip=True),
                address=cols[3].get_text(strip=True),
                disposition=cols[4].get_text(strip=True)
            )
