from django.db import models

class AdministrativeAction(models.Model):
    name = models.CharField(max_length=255)  # 업체명
    registration_number = models.CharField(max_length=100)  # 인허가번호
    action_name = models.CharField(max_length=255)  # 행정처분명
    action_date = models.DateField()  # 행정처분일
    details = models.TextField(blank=True)  # 기타 내용

    def __str__(self):
        return self.name

class ActionRecord(models.Model):
    company_name = models.CharField(max_length=200)
    infraction = models.TextField()
    penalty = models.TextField()
    date = models.DateField()

    def __str__(self):
        return f"{self.company_name} - {self.date}"
