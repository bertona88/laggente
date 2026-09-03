# Consent-Qualified Studio Outreach

## Current state

The repository implements a disabled-by-default outreach foundation on top of private Studio web
research and sealed professional email. It is not deployed or activated merely because the source
exists. `OUTREACH_ENABLED=false` is the production-safe default.

The first intended use is a maximum-five pack of real-estate professionals who may want to create a
LAGGENTE space. Real estate is the first commercial cohort, not the product identity or a permanent
campaign ontology.

## Deterministic flow

```text
professional asks Studio to research
                 ↓ cited public sources
       research-only candidate pack
                 ↓ exact human permission evidence
      consent-qualified recipient
                 ↓ Studio seals exact email + LAGGENTE link
       privacy + opaque unsubscribe token
                 ↓ exact bundle review
       human authorizes the campaign
                 ↓
           Resend transport
```

A public email address, professional profile, connection request, inferred interest, or purchased
list never crosses the permission gate. The supported bases are `explicit_consent` and the narrow
`existing_customer_similar_services` exception. LAGGENTE records the professional's evidence note;
it does not independently prove an offline conversation or sale.

## Activation gates

Do not set `OUTREACH_ENABLED=true` until all of these are true:

1. the exact release containing migration `d4f6a8c9b012` is deployed and read back;
2. agent-native mail is live, the sending domain and webhook are verified, and the existing
   outbound/reply acceptance path still passes;
3. the public privacy notice and controller/contact details have received human legal/privacy
   review for the intended acquisition process;
4. the first cohort is selected, every stored candidate has a visible source, and no address came
   from scraping, guessing, purchase, or an inferred permission basis;
5. consent or existing-customer evidence is available for each exact recipient before any email is
   sealed;
6. `OUTREACH_MAX_RECIPIENTS=5` and `OUTREACH_CANDIDATE_RETENTION_DAYS=30` are retained for the first
   acceptance pack;
7. one selected recipient has agreed to the controlled outbound, unsubscribe, and reply round trip;
8. the operator has separate explicit authorization to deploy and then the professional performs
   the exact campaign authorization inside Studio.

Repository implementation does not authorize a production deploy, migration, privacy approval, or
real email delivery.

## Expected controls

- research-only candidates expire automatically after the configured short window;
- every sendable recipient has one recorded permitted basis and a concrete evidence note tied to
  the current authenticated professional message;
- each sealed body contains the exact campaign link, privacy link, and opaque-token unsubscribe link;
- one action authorizes only the displayed artifact IDs and content hashes;
- individual email authorization rejects campaign artifacts;
- opaque-token unsubscribe and Resend bounce, suppression, or complaint events block later preparation;
- no failure or ambiguous provider result is retried automatically;
- campaign statuses describe execution only and must not be reused as CRM lead stages.

## Repository verification

```bash
cd services/api
.venv/bin/pytest -q
DATABASE_URL=sqlite:////tmp/laggente-outreach-migration.db .venv/bin/alembic upgrade head

cd ../../apps/web
npm test
npm run typecheck
npm run lint
npm run build

cd ../..
bash scripts/validate-infrastructure.sh
```
