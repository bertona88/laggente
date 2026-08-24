# SES inbound relay

This is the deployable Python AWS Lambda handler for the flow recorded in
`docs/operations/AGENT_NATIVE_EMAIL.md`. It reads the raw message previously written by the SES S3
receipt action, signs an exact JSON envelope, and posts it to the application. It never interprets
or logs message content.

The Lambda runtime already provides boto3, so the deployment ZIP contains `lambda_function.py`
only. Configure the handler as `lambda_function.lambda_handler`, place the S3 action before the
Lambda action in the same SES receipt rule, and set:

- `MAIL_BUCKET` — private inbound bucket;
- `MAIL_PREFIX` — S3 action object prefix, normally `incoming/`;
- `MAIL_MAX_BYTES` — normally `5242880`;
- `LAGGENTE_INBOUND_URL` — the exact HTTPS application endpoint;
- `LAGGENTE_INBOUND_SECRET` — the same random secret as the API.

Grant only `s3:GetObject` for the configured prefix and CloudWatch Logs permissions. SES must have
permission to invoke the function. Failed calls should be allowed to retry; the FastAPI endpoint is
idempotent by SES receipt ID.

Run the standard-library unit tests from this directory:

```bash
python3 -m unittest -v
```
