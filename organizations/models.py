import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Organisation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRIAL = 'trial', 'Trial'
        SUSPENDED = 'suspended', 'Suspended'
        DEACTIVATED = 'deactivated', 'Deactivated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    registration_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['status']), models.Index(fields=['name'])]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        PLATFORM_SUPER_ADMIN = 'platform_super_admin', 'Platform Super Admin'
        DAIRY_OWNER = 'dairy_owner', 'Dairy Owner'
        ORGANISATION_ADMIN = 'organisation_admin', 'Organisation Admin'
        BRANCH_MANAGER = 'branch_manager', 'Branch Manager'
        COLLECTION_SUPERVISOR = 'collection_supervisor', 'Collection Supervisor'
        MILK_COLLECTION_OPERATOR = 'milk_collection_operator', 'Milk Collection Operator'
        QUALITY_OFFICER = 'quality_officer', 'Quality Officer'
        ACCOUNTANT = 'accountant', 'Accountant'
        INVENTORY_MANAGER = 'inventory_manager', 'Inventory Manager'
        CUSTOMER_SUPPORT = 'customer_support', 'Customer Support Staff'
        FARMER = 'farmer', 'Farmer'
        MILK_CUSTOMER = 'milk_customer', 'Milk Customer'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=40, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organisation', 'user'], name='unique_org_membership')]
        indexes = [models.Index(fields=['organisation', 'role']), models.Index(fields=['user', 'is_active'])]

    def __str__(self):
        return f'{self.user} - {self.organisation} ({self.role})'


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organisation', 'name'], name='unique_branch_name_per_org')]
        indexes = [models.Index(fields=['organisation', 'is_active'])]
