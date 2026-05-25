from django.db import models


class LabelLayout(models.Model):
    label = models.OneToOneField(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name='layout',
        verbose_name='표시사항',
    )
    canvas_width = models.PositiveIntegerField(default=800, verbose_name='캔버스 너비(px)')
    canvas_height = models.PositiveIntegerField(default=600, verbose_name='캔버스 높이(px)')
    grid_size = models.PositiveIntegerField(default=10, verbose_name='그리드 크기(px)')
    background_color = models.CharField(max_length=20, default='#ffffff', verbose_name='배경색')
    elements = models.JSONField(default=list, verbose_name='개체 목록')
    created_datetime = models.DateTimeField(auto_now_add=True)
    updated_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'label_editor_layout'
        verbose_name = '라벨 레이아웃'
        verbose_name_plural = '라벨 레이아웃 목록'

    def __str__(self):
        return f'Layout for {self.label}'


class EditorImage(models.Model):
    label = models.ForeignKey(
        'label.MyLabel',
        on_delete=models.CASCADE,
        related_name='editor_images',
        verbose_name='표시사항',
    )
    file = models.ImageField(upload_to='label_editor/%Y/%m/%d/', verbose_name='이미지')
    original_filename = models.CharField(max_length=255, verbose_name='원본 파일명')
    uploaded_datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'label_editor_image'
        verbose_name = '에디터 이미지'
        verbose_name_plural = '에디터 이미지 목록'

    def __str__(self):
        return self.original_filename
