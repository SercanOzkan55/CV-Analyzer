# AWS Edge Security Runbook

Use CloudFront and AWS WAF in front of the API before production traffic.
The app already has application-level limits; edge controls stop noisy or
malicious requests before they reach the server.

## Recommended CloudFront Setup

- Put CloudFront in front of the API origin.
- Require HTTPS viewer protocol.
- Send `X-Forwarded-For` and set `TRUSTED_PROXY_COUNT=1` only when the proxy
  chain is known.
- Lock the origin so only CloudFront can reach it:
  - security group allowlist to CloudFront managed prefix list, or
  - custom origin header validated by the load balancer/reverse proxy.
- Enable access logs to a private, encrypted S3 bucket with lifecycle expiry.
- Add response headers policy:
  - HSTS
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - strict `Referrer-Policy`

## WAF Web ACL

Attach a WAF Web ACL to CloudFront with these managed rule groups:

- AWSManagedRulesCommonRuleSet
- AWSManagedRulesKnownBadInputsRuleSet
- AWSManagedRulesAmazonIpReputationList
- AWSManagedRulesAnonymousIpList
- AWSManagedRulesSQLiRuleSet

Add rate-based rules:

- `/api/v1/analyze*`: 100 requests per 5 minutes per IP
- `/api/v1/recruiter/*`: 200 requests per 5 minutes per IP
- `/api/v1/cv/auto-fix`: 60 requests per 5 minutes per IP
- `/api/v1/upload*`: 60 requests per 5 minutes per IP
- `/admin/*`: 20 requests per 5 minutes per IP

Add size rules:

- Block request bodies larger than your `MAX_REQUEST_BODY_BYTES`.
- Block unsupported upload extensions at the edge where possible.

## Admin Endpoints

Set these in production:

```env
ADMIN_TOKEN=use-a-strong-random-value-at-least-32-chars
ADMIN_IP_ALLOWLIST=203.0.113.10/32,198.51.100.0/24
ADMIN_RATE_LIMIT_PER_MIN=20
```

WAF should also restrict `/admin/*` to the same office/VPN IP ranges.

## CSRF

Bearer-token API calls are not CSRF-prone in the same way as cookie auth.
If any browser flow uses cookies for auth, keep:

```env
CSRF_PROTECTION_ENABLED=1
```

Unsafe cookie-authenticated requests must send `X-CSRF-Token` matching the
`csrf_token` or `XSRF-TOKEN` cookie.

## Logging

- Do not log raw CV text, job descriptions, tokens, emails, or phone numbers.
- Keep WAF logs in a private S3 bucket.
- Use short retention for raw edge logs unless compliance requires longer.
