from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Company, Freelancer


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'role']

    def get_role(self, obj):
        if hasattr(obj, 'company_admin'):
            return 'admin'
        if hasattr(obj, 'freelancer'):
            return 'freelancer'
        return 'unknown'


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'billing_email']


class FreelancerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Freelancer
        fields = ['id', 'name']
