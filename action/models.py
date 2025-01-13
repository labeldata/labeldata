from django.db import models
from common.models import AdministrativeAction


class InfractionRecord(models.Model):
    """위반 기록"""
    administrative_action = models.ForeignKey(
        AdministrativeAction,
        on_delete=models.CASCADE,
        related_name='infractions',
        help_text="관련 행정처분"
    )
    infraction_details = models.TextField(help_text="위반 세부사항")
    penalty_details = models.TextField(help_text="처벌 세부사항")
    record_date = models.DateField(help_text="기록 날짜")

    def __str__(self):
        return f"{self.administrative_action.action_name} - {self.record_date}"
