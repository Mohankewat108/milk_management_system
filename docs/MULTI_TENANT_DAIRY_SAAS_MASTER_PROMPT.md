# DairyNexus — Multi-Tenant Dairy Farm SaaS Product & Engineering Prompt

## Product objective

Build DairyNexus as a secure, multi-tenant SaaS platform for independently operated dairy farms. One central Platform Owner can register and oversee many dairy businesses. Each Dairy Farm Owner can operate one or more farm workspaces and create/manage many milk customers, milk farmers, employees, collections, deliveries, payments and reports within each authorized farm.

This is a dairy business-management platform, not a public directory of farms and not one shared workspace where all users can see one another's records.

## 1. Required business hierarchy

    DairyNexus Platform
    └── Platform Owner / SaaS Super Admin
        ├── Farm Tenant: Himalayan Dairy
        │   ├── Farm Owner
        │   ├── Staff and branch users
        │   ├── Milk farmers / suppliers
        │   ├── Customer 001, Customer 002, Customer 003...
        │   ├── Milk collections and quality
        │   ├── Sales, deliveries and customer subscriptions
        │   ├── Customer invoices and payments
        │   └── Expenses, inventory and reports
        ├── Farm Tenant: Green Valley Milk
        │   ├── Farm Owner (may be the same person if explicitly assigned)
        │   └── Its own staff, farmers, customers and operational records
        └── Farm Tenant: Terai Fresh Dairy
            └── Completely separate tenant data

The number of farms and customers must not be hardcoded. Enforce capacity through configurable subscription plans and infrastructure controls.

## 2. Roles and authority boundaries

### 2.1 Platform Owner

The Platform Owner operates the SaaS platform and is separate from every dairy business owner.

Capabilities:
- Create a dairy farm tenant and assign an existing user account as its owner.
- Register a farm on behalf of a business owner.
- View all tenants, owners, status, registration date, branches, customer counts, farmer counts, staff counts and subscription state.
- Activate, suspend, reactivate and close a tenant with reason, actor, timestamp and audit history.
- Assign/change subscription plans and tenant limits.
- View platform-wide aggregate usage and system health.
- Manage platform administrators and support operations.
- Access tenant operational data only through an explicitly permissioned, audited support workflow. Routine platform dashboards should use aggregate data.
- Never silently impersonate a farm owner or edit financial/collection records.

Platform actions must be protected by server-side platform-admin permissions, CSRF protection and audit events. Hiding a button is not authorization.

### 2.2 Dairy Farm Owner

A farm owner is a normal authenticated account with an active OWNER membership for one or more Organization tenants.

Capabilities inside each assigned farm:
- Switch between authorized farm workspaces.
- Update farm profile and contact details.
- Create, edit, deactivate and search many milk customers.
- Create, edit, deactivate and search many milk farmers/suppliers.
- Create branches and assign staff, subject to plan permissions.
- Invite/provision employees with least-privilege roles.
- Record, review and approve milk collections according to role policy.
- Configure milk prices and quality rules.
- Manage delivery schedules and customer subscriptions.
- Create invoices and record customer receipts.
- Calculate farmer payable amounts and record farmer payments.
- Manage expenses, stock, suppliers and operational reports.
- View only data belonging to the selected farm and authorized branches.

A person may own multiple farms. Ownership of Farm A must not grant access to Farm B unless a separate active membership exists for Farm B.

### 2.3 Farm employees

Support least-privilege roles:
- Farm administrator
- Branch manager
- Collection operator
- Quality officer
- Accountant
- Inventory manager
- Delivery operator
- Customer support

Every staff account must have an organization membership and, where applicable, explicit branch assignments. Enforce permissions in views, services, selectors and background jobs.

### 2.4 Milk customer

A customer belongs to a specific farm tenant. Customers must not see other customers or other farms.

Customer portal capabilities:
- View own profile and assigned farm identity/contact details.
- View own milk orders/subscription and delivery schedule.
- View own approved milk supply/quantity history.
- View own invoices, outstanding balance and completed payments.
- Download own receipts/statements where supported.
- Submit support requests or delivery issues.
- Update permitted contact details.

Resolve the customer profile from the authenticated user's verified association. Never trust arbitrary tenant IDs or customer IDs submitted by the browser.

## 3. Tenant data model and isolation

Use the existing Django Organization model as the tenant boundary unless a reviewed migration plan justifies a schema change.

Required rules:
- Every farm-owned record must have an Organization foreign key directly or through a strictly validated parent relation.
- Every branch belongs to exactly one Organization.
- Every Membership links one user to one Organization and one role.
- A user can have multiple Organization memberships, including OWNER memberships for multiple farms.
- Customer codes and farmer codes are unique within a tenant, not globally.
- A branch selected on a form must belong to the current tenant.
- Cross-tenant foreign-key combinations must be rejected in services and validation.
- All list/detail/update/delete selectors must filter by the authorized tenant before resolving a record.
- Never trust organization, branch, customer, farmer or owner IDs posted by the browser.
- Use transaction.atomic for multi-record onboarding and financial workflows.
- Add database constraints and indexes for tenant-scoped uniqueness and common tenant queries.
- Test cross-tenant access by changing URL slugs, UUIDs, form values, query parameters and related-object IDs.

Evaluate PostgreSQL row-level security as additional defence in depth. Do not claim RLS is active until policies, migrations, connection context and tests exist.

## 4. Platform farm onboarding workflow

1. Platform Owner opens Platform Control Centre.
2. Selects Create dairy farm.
3. Enters farm legal/business details.
4. Selects an existing active user account as the farm owner.
5. Reviews tenant name, country, currency, timezone and contact details.
6. Submits the form.
7. In one database transaction:
   - Create Organization with unique slug and TRIAL status.
   - Create active OWNER membership for the selected account.
   - Create the initial MAIN branch.
   - Record an audit event.
8. Show success confirmation and return to the tenant list.
9. Farm owner signs in and sees the newly assigned farm in their workspace selector.
10. Farm owner opens the farm and begins adding customers, farmers and staff.

If the owner has no account, implement a separate invitation flow with expiring, single-use tokens and email delivery. Never create an account with a known default password or expose a temporary password.

## 5. Farm owner customer management workflow

Within a selected tenant:
1. Farm Owner opens Customers and selects Add Customer.
2. Enters customer code, full name, phone, email, address, location and optional account association.
3. Selects a branch belonging to the same farm.
4. System validates duplicate customer code within that tenant.
5. Saves the customer with tenant derived from the authenticated membership, not an untrusted posted tenant ID.
6. Customer appears only in that tenant's directory and reports.
7. Farm owner can add many customers without a hardcoded application limit, subject to the subscription plan.
8. Deactivation preserves historical collections, invoices and payments.
9. Customer portal association must be explicit and verified; creating a contact record must not automatically grant account access.

## 6. Platform Control Centre

Build a dedicated platform administration interface:
- Tenant count, active, trial, suspended and closed counts.
- Total registered users and customer totals.
- Tenant list with search, filters, sorting and pagination.
- Farm name, owner, tenant status, country, currency, created date, branches, customers, farmers, staff and plan.
- Farm detail view with clear tenant overview.
- Audited status changes with confirmation and reason.
- Subscription assignment and limit visibility.
- Platform audit log.
- Empty, loading, validation and failure states.
- Responsive desktop, tablet and mobile layouts.

Do not show fake revenue, collection totals or profit values. Only show metrics supported by actual records and clearly label date range and currency.

## 7. Farm Workspace

Every farm workspace must have:
- Farm identity and logo.
- Workspace switcher for users with multiple memberships.
- Branch selector where role permits.
- Dashboard scoped to current tenant and branch access.
- Customer directory and customer detail.
- Farmer/supplier directory and farmer detail.
- Staff and role management.
- Milk collection and quality.
- Pricing configuration.
- Delivery routes and schedules.
- Customer billing, receipts and balances.
- Farmer settlements.
- Expenses and inventory.
- Reports and exports.
- Farm settings and audit activity.

Farm A's dashboard must never include Farm B's customers, totals, collections, balances or staff.

## 8. Subscription and limits

Plans should support configurable:
- Number of branches.
- Number of staff.
- Number of active customers.
- Number of farmers/suppliers.
- Feature access.
- Storage quota.
- Trial duration.
- Billing cycle and status.

Enforce limits in backend services and return actionable validation errors. Do not rely on frontend-only restrictions. Upgrades must not delete records. Define graceful read-only or over-limit behaviour for expired subscriptions and document any grace period.

## 9. Security and privacy

- Enforce authorization on every request and service boundary.
- Use secure password reset and invitation flows.
- Require verified email before sensitive customer portal access.
- Protect against IDOR, CSRF, XSS, SQL injection and mass assignment.
- Validate uploaded files by type, size and storage policy.
- Do not log passwords, tokens, bank details or sensitive payment data.
- Keep platform admin and farm roles separate.
- Audit tenant creation, owner changes, role changes, suspensions, exports and financial approvals.
- Use least-privilege access and branch-scoped permissions.
- Apply secure production cookies, TLS, secret management, backup and restore policies.

## 10. UX/UI requirements

Create distinct interfaces:
- Platform Control Centre for the SaaS owner.
- Dairy Farm Workspace for farm owners and staff.
- Customer Portal for milk customers.

Use a coherent responsive design system, clear navigation, accessible forms, meaningful empty states, inline validation, loading states, confirmation dialogs and readable financial tables. Never display an unstyled fallback page as a finished screen. Test rendered pages at 360px, 768px, 1024px and 1440px.

## 11. Engineering standards and workflow

Technology:
- Python and Django.
- PostgreSQL for production.
- Django ORM and reviewed migrations.
- Existing project authentication, audit and tenant models where suitable.
- HTML templates and maintainable CSS.
- Automated tests and GitHub Actions.

Before changing code:
1. Inspect existing models, routes, services, templates, migrations and tests.
2. Reuse correct components; do not create duplicate models or workflows.
3. Write an implementation plan and identify migration/data risks.
4. Preserve working routes, form field names and context variables unless a reviewed migration requires a change.
5. Implement in small, reviewable commits on a feature branch.
6. Generate, inspect and commit migrations.
7. Add tests for successful workflows and authorization failures.
8. Run Django checks, migration checks, PostgreSQL migrations, tests, coverage and dependency audit.
9. Review rendered pages in a browser.
10. Open a pull request with changed files, migrations, test evidence and known limitations.

## 12. Acceptance criteria

The work is not complete until demonstrated:
- Platform Owner can create Farm A and Farm B.
- Platform Owner can assign the same existing user as owner of multiple farms.
- Owner can sign in and see both farms in the workspace selector.
- Farm Owner can create at least 100 distinct customer records through the real UI or documented seed process.
- Customer codes can repeat across farms but cannot duplicate within one farm.
- Farm A owner cannot open Farm B by changing URL slug or object UUID.
- Farm A customer cannot see Farm B data.
- Staff can access only assigned organizations and branches.
- Platform dashboard totals are computed from actual database records.
- Tenant creation, membership creation and initial branch creation are atomic.
- Migrations apply cleanly on a fresh PostgreSQL database.
- Automated tests cover tenant isolation and role permissions.
- No production secrets or default passwords are committed.
- Critical screens are responsive and keyboard accessible.

## 13. Instructions for this existing repository

Target repository: Mohankewat108/milk_management_system.

The repository already contains Organization, Branch, Membership, Customer, Farmer and Subscription foundations. Extend them carefully instead of creating parallel implementations.

Implement platform-owner multi-farm creation, multiple farm ownership, farm workspace selection, tenant-scoped customer management and platform-level farm oversight. Do not claim production readiness until every acceptance criterion has test evidence.
