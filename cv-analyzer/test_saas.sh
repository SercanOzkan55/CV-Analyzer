#!/bin/bash
# 🔥 SaaS Backend Manual Tests - Curl Commands
# Copy and paste these into terminal or Postman

# =====================================================
# SETUP: Get your JWT token first
# =====================================================

# 1. Login via frontend (test-login.html)
# 2. Open browser console: 
#    const { data } = await supabase.auth.getSession();
#    console.log(data.session.access_token);
# 3. Copy the token and replace TOKEN_HERE below

TOKEN_HERE="your_jwt_token_here"
API_URL="http://localhost:8000"

# =====================================================
# TEST 1: NO AUTH (Should return 401)
# =====================================================

echo "🔴 TEST 1: No Authorization Header"
curl -X POST "$API_URL/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Senior Software Engineer with 5 years experience",
    "job_description": "Backend Engineer 5+ years required"
  }'

echo -e "\n✓ Expected: 401 Unauthorized\n"


# =====================================================
# TEST 2: INVALID TOKEN (Should return 401)
# =====================================================

echo "🔴 TEST 2: Tampered Token"
TAMPERED="eyJxxxxx_TAMPERED_TOKEN_xxxxx"

curl -X POST "$API_URL/api/v1/analyze" \
  -H "Authorization: Bearer $TAMPERED" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Senior Software Engineer",
    "job_description": "Backend Engineer 5+ years"
  }'

echo -e "\n✓ Expected: 401 Unauthorized\n"


# =====================================================
# TEST 3: VALID TOKEN (Should return 200)
# =====================================================

echo "🟢 TEST 3: Valid JWT Token"
curl -X POST "$API_URL/api/v1/analyze" \
  -H "Authorization: Bearer $TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Senior Software Engineer\n\nExperience:\n- 5+ years Python\n- 3+ years React\n- AWS expertise\n\nSkills: Python, JavaScript, PostgreSQL",
    "job_description": "Senior Backend Engineer\n\nRequirements:\n- 5+ years Python\n- FastAPI/Django\n- PostgreSQL\n- AWS\n\nNice: Docker, K8s"
  }'

echo -e "\n✓ Expected: 200 OK with analysis results\n"


# =====================================================
# TEST 4: GET HISTORY (JWT Protected)
# =====================================================

echo "🟢 TEST 4: Get User History"
curl -X GET "$API_URL/api/v1/history" \
  -H "Authorization: Bearer $TOKEN_HERE"

echo -e "\n✓ Expected: 200 OK with your analyses\n"


# =====================================================
# TEST 5: HISTORY WITHOUT AUTH (Should return 401)
# =====================================================

echo "🔴 TEST 5: History Without Auth"
curl -X GET "$API_URL/api/v1/history"

echo -e "\n✓ Expected: 401 Unauthorized\n"


# =====================================================
# TEST 6: WRONG AUTH SCHEME (Should return 401)
# =====================================================

echo "🔴 TEST 6: Wrong Auth Scheme (Basic instead of Bearer)"
curl -X POST "$API_URL/api/v1/analyze" \
  -H "Authorization: Basic $TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Senior Engineer",
    "job_description": "Backend Engineer"
  }'

echo -e "\n✓ Expected: 401 Unauthorized\n"


# =====================================================
# TEST 7: PDF ENDPOINT WITHOUT AUTH (Should return 401)
# =====================================================

echo "🔴 TEST 7: PDF Endpoint Without Auth"
# Need a real PDF file for this test
curl -X POST "$API_URL/api/v1/analyze-pdf" \
  -F "file=@sample.pdf" \
  -F "job_description=Backend Engineer"

echo -e "\n✓ Expected: 401 Unauthorized\n"


# =====================================================
# TEST 8: RATE LIMITING (11 requests, last should fail)
# =====================================================

echo "🟡 TEST 8: Rate Limiting (11 requests)"
for i in {1..11}; do
  echo "Request $i:"
  curl -X POST "$API_URL/api/v1/analyze" \
    -H "Authorization: Bearer $TOKEN_HERE" \
    -H "Content-Type: application/json" \
    -d '{
      "cv_text": "Engineer",
      "job_description": "Backend Engineer"
    }' \
    -w "Status: %{http_code}\n\n" \
    -o /dev/null \
    -s
  
  sleep 0.1  # Small delay between requests
done

echo "✓ Expected: First 10 return 200, 11th returns 429 Too Many Requests\n"


# =====================================================
# MANUAL DATABASE CHECKS
# =====================================================

echo "💾 DATABASE CHECKS"
echo ""
echo "1️⃣ Check users created:"
echo "   SELECT * FROM app_users ORDER BY created_at DESC LIMIT 5;"
echo ""
echo "2️⃣ Check analyses linked to users:"
echo "   SELECT a.id, a.similarity_score, u.email"
echo "   FROM analysis a"
echo "   JOIN users u ON a.user_id = u.id"
echo "   ORDER BY a.created_at DESC LIMIT 5;"
echo ""
echo "3️⃣ Check for null user_id (SHOULD be empty):"
echo "   SELECT COUNT(*) FROM analysis WHERE user_id IS NULL;"
echo ""
echo "4️⃣ Check user isolation - User A only sees own data:"
echo "   SELECT COUNT(*) FROM analysis"
echo "   WHERE user_id = (SELECT id FROM app_users WHERE email = 'user1@example.com');"
echo ""
echo "5️⃣ Check foreign key integrity:"
echo "   SELECT COUNT(*) FROM analysis a"
echo "   WHERE NOT EXISTS (SELECT 1 FROM app_users u WHERE u.id = a.user_id);"
echo "   (Result should be 0)"
echo ""


# =====================================================
# POSTMAN SETUP
# =====================================================

echo ""
echo "📮 POSTMAN SETUP"
echo ""
echo "1. Create environment variable in Postman:"
echo "   - token = your_jwt_token"
echo "   - baseUrl = http://localhost:8000"
echo ""
echo "2. Use {{token}} as Authorization header Bearer token"
echo "3. Use {{baseUrl}}/api/v1/analyze for endpoint"
echo ""
echo "🔗 Example Postman Collection: Create request with:"
echo "   - Method: POST"
echo "   - URL: {{baseUrl}}/api/v1/analyze"
echo "   - Header: Authorization: Bearer {{token}}"
echo "   - Body (raw JSON):"
echo '   {
  "cv_text": "Your CV text here",
  "job_description": "Job description here"
}'
echo ""
