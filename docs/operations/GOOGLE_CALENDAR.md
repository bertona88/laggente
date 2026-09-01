# Google Calendar Activation

Repository support is not evidence that Google Calendar is active in production. Treat these
states separately: code committed, Google Cloud configured, secrets installed, migration applied,
service deployed, professional OAuth completed, and a real appointment accepted.

## Google Cloud project

The dedicated Google Cloud project is **LAGGENTE**, project ID `laggente-production`, project number
`731266066249`. The Calendar API and Google Auth Platform configuration were created on
2026-09-01. Do not reuse an unrelated product project.

1. Enable the Google Calendar API.
2. Configure Google Auth Platform branding for **LAGGENTE** with the approved support and contact
   addresses, homepage `https://app.laggente.com`, privacy policy
   `https://app.laggente.com/privacy`, and terms `https://app.laggente.com/terms`.
3. Request only `openid`, `email`, `https://www.googleapis.com/auth/calendar.freebusy`, and
   `https://www.googleapis.com/auth/calendar.events`.
4. During pilot testing, add only selected professional accounts as test users. Do not publish the
   OAuth app externally before privacy and verification requirements are reviewed.
5. Create a Web application OAuth client named `LAGGENTE production` with this exact redirect URI:
   `https://app.laggente.com/api/v1/studio/calendar/oauth/callback`.

The OAuth app currently remains **External / Testing** and has only the initial pilot account as a
test user. Generate or rotate the client secret only when it can be installed directly in the
server secret file; Google does not make an existing secret retrievable later.

For local acceptance, create a separate client rather than adding local callbacks to the production
client.

## Server configuration

Store the values only in `/opt/laggente/secrets/application.env`:

```text
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_CLIENT_ID=...
GOOGLE_CALENDAR_CLIENT_SECRET=...
GOOGLE_CALENDAR_REDIRECT_URI=https://app.laggente.com/api/v1/studio/calendar/oauth/callback
GOOGLE_CALENDAR_ENCRYPTION_KEY=...
PRIVACY_NOTICE_VERSION=2026-09-01.1
```

`GOOGLE_CALENDAR_ENCRYPTION_KEY` must be an independent random value of at least 32 characters.
Never commit the client secret, encryption key, access token, or refresh token.

## Activation sequence

1. Apply Alembic migration `a9c4e2f7b601` through the normal release process.
2. Deploy with calendar support still disabled and verify health and tenant isolation.
3. Install the production client values and enable the capability.
4. In the professional Studio, connect Google Calendar and review the Google consent screen.
5. Save bookable hours with public booking still paused.
6. Activate booking and use a controlled visitor conversation to query availability.
7. Select one exact slot and use a controlled visitor email address to create an event.
8. Verify the event, attendee invitation, persisted booking, audit event, and that the occupied slot
   is not offered again.

Do not create or cancel a real appointment without the selected participants' approval.

## Rollback

Set `GOOGLE_CALENDAR_ENABLED=false` and restart only the API to remove calendar tools and connection
entry points. This does not delete existing Google events. The professional can pause public
booking while retaining the connection, or disconnect locally from Studio. Revoke LAGGENTE access
from the Google account separately when complete provider-side revocation is required.
