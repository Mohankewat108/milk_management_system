# Dairy Manager and organisation permissions

DairyNexus keeps the existing platform and dairy ownership boundaries:

- Platform Owner remains a Django superuser protected by the platform administration views.
- Dairy Owner remains `Organization.owner` plus `Membership.Role.OWNER`.
- Organisation-wide owner/admin authority is unchanged.

## Dairy Manager

`Membership.Role.DAIRY_MANAGER` is an organisation membership role, not a replacement for either owner role. A Dairy Manager must have at least one active `BranchAssignment`. Branch scope is always resolved from membership assignments; no organisation or branch identifier supplied by the browser grants access.

## Granular capability grants

`OrganizationPermission` is the shared permission catalogue. A membership receives explicit capabilities through its `permissions` many-to-many relation. Pending staff invitations carry the same permission grants, which are copied to the membership only after the invitation token is validated and accepted.

Current capabilities include dashboard, collections (view/create/approve), parties (view/manage), finance (view/manage), inventory (view/manage), staff management, reports, exports and organisation settings.

The `organization_access` decorator accepts an optional capability. When the authenticated membership is a Dairy Manager, the capability must be explicitly granted. Existing role-based authorization for other established roles remains unchanged. Owners and organisation admins retain their existing authority.

## Tenant and branch safety

- Membership lookup is based on the authenticated user and URL organisation slug.
- Membership and organisation must be active.
- Branch assignments are created from a form queryset scoped to the current organisation.
- Operational querysets continue to filter by the membership's assigned branch IDs.
- A Dairy Manager with no branch assignments receives no branch records.
- Cross-organisation access remains denied by the existing tenant boundary and database integrity rules.

## Rollout

Migration `0006_dairy_manager_permissions` adds the permission catalogue and M2M grant relations without rewriting existing ownership rows. The migration seeds the permission catalogue and does not grant new permissions to existing users. Existing Platform Owner, Dairy Owner, staff, farmer and customer accounts retain their current identities and relationships.
