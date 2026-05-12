from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    name = models.CharField(max_length=255)
    billing_email = models.EmailField()

    class Meta:
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name


class CompanyAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_admin')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='admins')

    def __str__(self):
        return f'{self.user.email} @ {self.company.name}'


class Freelancer(models.Model):
    name = models.CharField(max_length=255)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='freelancer')

    def __str__(self):
        return self.name
