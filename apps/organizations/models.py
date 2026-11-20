from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class Organization(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_organizations"
    )
    name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=220, blank=True)
    slug = models.SlugField(max_length=190, unique=True)
    registration_number = models.CharField(max_length=80, blank=True)
    business_type = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=80, default="Nepal")
    currency = models.CharField(max_length=3, default="NPR")
    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.TRIAL, db_index=True
    )
    is_demo = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return self.name


class Branch(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="branches"
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_branches",
    )
    is_active = models.BooleanField(default=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_branch_code_per_org"
            )
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.organization.name})"


class Membership(UUIDModel, TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Dairy owner"
        ADMIN = "admin", "Organisation admin"
        DAIRY_MANAGER = "dairy_manager", "Dairy manager"
        BRANCH_MANAGER = "branch_manager", "Branch manager"
        COLLECTION_OPERATOR = "collection_operator", "Milk collection operator"
        QUALITY_OFFICER = "quality_officer", "Quality officer"
        ACCOUNTANT = "accountant", "Accountant"
        INVENTORY_MANAGER = "inventory_manager", "Inventory manager"
        SUPPORT = "support", "Customer support"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        SUSPENDED = "suspended", "Suspended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    invited_email = models.EmailField(blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    permissions = models.ManyToManyField(
        "OrganizationPermission",
        blank=True,
        related_name="memberships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"], name="uniq_user_org_membership"
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["organization", "role", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.organization} · {self.role}"


class BranchAssignment(UUIDModel, TimeStampedModel):
    membership = models.ForeignKey(
        Membership, on_delete=models.CASCADE, related_name="branch_assignments"
    )
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="member_assignments")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "branch"], name="uniq_member_branch_assignment"
            )
        ]


class StaffInvitation(UUIDModel, TimeStampedModel):
    """One-time, hashed-token invitation to join an organisation as staff."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="staff_invitations"
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_staff_invitations"
    )
    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=32, choices=Membership.Role.choices)
    branches = models.ManyToManyField(Branch, blank=True, related_name="staff_invitations")
    permissions = models.ManyToManyField(
        "OrganizationPermission",
        blank=True,
        related_name="staff_invitations",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "email", "created_at"])]

    @property
    def is_pending(self):
        from django.utils import timezone

        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )


class OrganizationPermission(UUIDModel, TimeStampedModel):
    """A tenant-scoped capability that an owner explicitly grants to a membership."""

    class Key(models.TextChoices):
        DASHBOARD_VIEW = "dashboard.view", "View dashboard"
        COLLECTIONS_VIEW = "collections.view", "View milk collections"
        COLLECTIONS_CREATE = "collections.create", "Record milk collections"
        COLLECTIONS_APPROVE = "collections.approve", "Approve milk collections"
        PARTIES_VIEW = "parties.view", "View farmers and customers"
        PARTIES_MANAGE = "parties.manage", "Manage farmers and customers"
        FINANCE_VIEW = "finance.view", "View financial records"
        FINANCE_MANAGE = "finance.manage", "Manage payments and accounts"
        INVENTORY_VIEW = "inventory.view", "View inventory"
        INVENTORY_MANAGE = "inventory.manage", "Manage inventory"
        STAFF_MANAGE = "staff.manage", "Manage organisation staff"
        REPORTS_VIEW = "reports.view", "View reports"
        EXPORTS_CREATE = "exports.create", "Create data exports"
        SETTINGS_MANAGE = "settings.manage", "Manage organisation settings"

    key = models.CharField(max_length=64, choices=Key.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.name
