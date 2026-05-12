from django.db import models

from accounts.models import Company, Freelancer


class Contract(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CLOSED, 'Closed'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contracts')
    freelancer = models.ForeignKey(Freelancer, on_delete=models.CASCADE, related_name='contracts')
    daily_rate = models.DecimalField(max_digits=8, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    def __str__(self):
        return f'{self.freelancer.name} @ {self.company.name} ({self.status})'


class TimesheetEntry(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='timesheet_entries')
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    rejection_reason = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('contract', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.contract} — {self.date} ({self.hours}h, {self.status})'
