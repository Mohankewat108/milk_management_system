# Security model and production checklist

## Implemented controls in this branch

- Custom Django user model with Django password hashing and configured password validators.
- Username/email login; authentication failures are rate-limited by remote IP through the cache backend (10 failures per 15-minute window).
- Django session authentication, HttpOnly session cookie, SameSite=Lax, CSRF middleware and CSRF form tokens.
- Logout is POST-only.
- Production settings reject the development secret and require ALLOWED_HOSTS; they enable HTTPS redirect, secure session/CSRF cookies and HSTS.
- Shared-database tenant resolution is based on active user membership, never a client-provided tenant ID.
- Tenant-filtered form querysets, scoped querysets and explicit organisation/branch checks in core collection and finance services.
- Non-owner/admin memberships require explicit branch assignments; missing assignments do not imply organisation-wide access.
- Customer self-service portal selects the customer profile linked to the authenticated user.
- Collection and payment writes use transactions; sensitive status updates lock records.
- Password reset uses Django's signed, time-limited reset-token flow.
- AuditEvent admin is read-only; the app writes actor/tenant/action/target metadata.

## Before production

1. Generate and commit migrations; review them for destructive operations. Do not run schema changes against production data without a backup and migration rehearsal.
2. Rotate any credentials that were ever used in the legacy PHP repository. The tracked PHP connection file contains example local credentials; do not reuse them.
3. Supply a strong random `DJANGO_SECRET_KEY`, production `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, Redis URL and TLS endpoint through the deployment secret manager.
4. Configure SMTP or a transactional email provider. The current default email backend writes reset emails to the application console; password reset is not production-ready until delivery is configured and verified.
5. Use a shared Redis cache for production rate limiting. The local development cache is process-local and is not a multi-worker throttle.
6. Add IP and account-based login throttling at the edge/WAF; trust proxy headers only when the reverse proxy is configured to overwrite them.
7. Add MFA for platform superusers and privileged owners; monitor superuser creation and login.
8. Add database row-level security or a carefully tested repository/queryset policy for defence in depth. Current tenant isolation is enforced at the Django application/service layer.
9. Restrict file uploads by content type, extension, size and malware scanning before adding user-facing document/profile uploads.
10. Use immutable/off-host backups, test restore procedures and define recovery objectives.
11. Add security headers at the reverse proxy; validate TLS, HSTS, CSP and allowed origins against the final domain.
12. Add structured logs, alerting, error tracking, database monitoring and audit retention.
13. Add authorization tests for every role and every tenant-scoped endpoint before adding new views or APIs.
14. Review personal data retention, access/export/deletion workflows, privacy notice and applicable data-protection duties for deployment country.
15. Run dependency scanning, static analysis, secret scanning and an independent penetration test before commercial launch.

## Known limitations

- The current IP-only application login limiter is a first layer, not a substitute for edge throttling or bot protection.
- MFA/OTP is not implemented.
- Email verification and phone verification fields exist, but the verification delivery and challenge flows are not implemented.
- Email backend defaults to console for development.
- AuditEvent is read-only in Django admin, but a database administrator could alter/delete rows; use database permissions and external tamper-evident export for high-assurance audit requirements.
- There is no payment gateway integration. Never mark an unverified provider payment as completed.
- Branch scoping is enforced in the current web views and services; new APIs, exports, background tasks and reporting views must use the same tenant/branch policy.
- Farmer self-service access, support workflows, notification delivery and attachment security are not complete.
