# Customer Portal and Milk Quality / Rate Improvements

This branch extends the existing Django customer portal and collection process. It is intentionally additive; existing approved historical collections and pricing versions are preserved.

## Customer self-service
- Customer signs in through the existing account login and opens /portal/.
- The account is linked by Customer.user (OneToOne); users without a linked active profile receive 403.
- The portal displays the customer's own profile, customer code, organisation/branch, approved milk collections, quality metrics, rate details, and completed payments.
- Data is always scoped through the logged-in user's linked Customer record. Customers cannot select another customer by URL or query parameter.
- Profile editing is not enabled in this release; contact the dairy to correct identity and transactional data.

## Milk testing
- Record SNF, fat, lactose, optional lactometer reading, optional milk temperature, sample reference, testing method, tester and notes.
- Lactometer reading is optional because equipment and operating practice vary between dairies. The unit and temperature correction method must be documented by each dairy before using a reading for automated pricing or milk-density calculations.
- SNF/fat/lactose values remain checked against the effective, approved quality profile for the collection date and branch.

## Daily rates
- The existing PricingConfiguration is effective-dated, versioned, branch-aware and approval-controlled.
- New collections use the approved pricing row effective on the collection date. Historical collections retain their PricingConfiguration foreign key and a JSON calculation snapshot.
- Each collection snapshot stores the version, effective dates, rate coefficients and individual component results to explain the applied rate later.
- Formula currently implemented: (SNF × SNF rate) + (FAT × FAT rate) + (Lactose × Lactose rate). The dairy must verify its business formula, coefficient units and currency before commercial use.

## Production-readiness notes
- Add formal pricing tests for date boundaries, branch override/fallback, overlapping effective windows and auditability.
- Add review/approval tests for collections and customer portal visibility.
- Add downloadable customer statements, pagination and date filters, automated notifications, consent/privacy retention rules, customer onboarding/invitation and multi-factor authentication in subsequent releases.
- Run migrations and test suite before deployment. Do not treat this branch as production-certified until CI and deployment checks pass.
