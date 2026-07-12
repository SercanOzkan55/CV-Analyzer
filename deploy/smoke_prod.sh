#!/usr/bin/env bash
# Production smoke test: unauthenticated surface checks.
# Usage: ./deploy/smoke_prod.sh https://cvanalyzer.dev
set -u

BASE="${1:?usage: smoke_prod.sh <base-url>}"
FAIL=0

check() {
  local name="$1" url="$2" expected="$3"  # expected: pipe-separated list, e.g. "401|403"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url")
  if echo "$code" | grep -qE "^($expected)$"; then
    echo "PASS  $name ($code)"
  else
    echo "FAIL  $name (got $code, want $expected)  $url"
    FAIL=1
  fi
}

check "health"                "$BASE/health"                        200
check "frontend index"        "$BASE/"                              200
check "privacy page (SPA)"    "$BASE/privacy"                       200
check "robots.txt"            "$BASE/robots.txt"                    200
check "sitemap.xml"           "$BASE/sitemap.xml"                   200
check "global benchmark API"  "$BASE/api/v1/benchmark/global"       200
check "auth required on API"  "$BASE/api/v1/me/data-summary"        "401|403"
check "metrics locked down"   "$BASE/metrics"                       "401|403"

# HTTPS hardening
hsts=$(curl -s -I --max-time 15 "$BASE/" | grep -ci "strict-transport-security")
if [ "$hsts" -ge 1 ]; then echo "PASS  HSTS header"; else echo "FAIL  HSTS header missing"; FAIL=1; fi

exit $FAIL
