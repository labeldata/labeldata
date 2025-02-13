from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import CrawlingSetting


@admin.register(CrawlingSetting)
class CrawlingSettingAdmin(admin.ModelAdmin):
    list_display = ('location', 'target_url', 'crawling_period', 'trigger_crawl')
    search_fields = ('location',)

    def trigger_crawl(self, obj):
        """Admin에서 크롤링 실행 버튼"""
        crawl_url = reverse('disposition:crawl_dispositions', args=[obj.id])
        return format_html(
            '<a class="button" style="color: white; background-color: #4CAF50; padding: 5px 10px; '
            'text-decoration: none; border-radius: 5px;" href="{}">크롤링 실행</a>',
            crawl_url
        )
    trigger_crawl.short_description = '크롤링 실행'
