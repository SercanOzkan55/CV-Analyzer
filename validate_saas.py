"""
🔥 Pre-Production SaaS Validation Checklist
Run this before deploying to production
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check(description: str, condition: bool, severity="INFO"):
    """Print check result"""
    symbol = "✅" if condition else "❌"
    color = "\033[92m" if condition else "\033[91m"
    reset = "\033[0m"
    
    severity_prefix = ""
    if severity == "CRITICAL":
        severity_prefix = f"\033[41m{severity}\033[0m "
    elif severity == "WARNING":
        severity_prefix = f"\033[43m{severity}\033[0m "
    
    print(f"{symbol} {severity_prefix}{description}")
    return condition


def validate_environment():
    """Check environment variables"""
    print("\n" + "="*60)
    print("🔧 ENVIRONMENT VARIABLES")
    print("="*60)
    
    required = {
        "SUPABASE_JWT_SECRET": "CRITICAL",
        "DATABASE_URL": "CRITICAL",
        "API_KEY": "WARNING"  # Optional but recommended
    }
    
    results = []
    for var, severity in required.items():
        value = os.getenv(var)
        if value:
            masked = value[:20] + "***" if len(value) > 20 else value
            result = check(f"{var}: {masked}", True, severity)
        else:
            result = check(f"{var}: NOT SET", False, severity)
        results.append(result)
    
    return all(results)


def validate_files():
    """Check required files exist"""
    print("\n" + "="*60)
    print("📄 REQUIRED FILES")
    print("="*60)
    
    required_files = {
        "main.py": "CRITICAL",
        "auth.py": "CRITICAL",
        "models.py": "CRITICAL",
        "database.py": "CRITICAL",
        "setup_db.py": "WARNING"
    }
    
    results = []
    for filename, severity in required_files.items():
        exists = os.path.exists(filename)
        result = check(f"{filename}", exists, severity)
        results.append(result)
    
    return all(results)


def validate_auth_code():
    """Check auth.py implementation"""
    print("\n" + "="*60)
    print("🔐 AUTH CODE VALIDATION")
    print("="*60)
    
    results = []
    
    try:
        with open("auth.py", "r") as f:
            content = f.read()
        
        checks = {
            "has verify_supabase_jwt": "verify_supabase_jwt" in content,
            "uses jwt.decode": "jwt.decode" in content,
            "checks for 401": "401" in content,
            "validates Bearer scheme": "Bearer" in content,
            "checks user_id (sub)": '"sub"' in content or "'sub'" in content,
        }
        
        for check_name, passed in checks.items():
            result = check(check_name, passed, "CRITICAL" if passed else "WARNING")
            results.append(result)
    
    except Exception as e:
        print(f"❌ Error reading auth.py: {e}")
        return False
    
    return all(results)


def validate_main_code():
    """Check main.py implementation"""
    print("\n" + "="*60)
    print("🚀 MAIN CODE VALIDATION")
    print("="*60)
    
    results = []
    
    try:
        with open("main.py", "r") as f:
            content = f.read()
        
        checks = {
            "analyze endpoint uses Depends": "Depends(verify_supabase_jwt)" in content and "@app.post(\"/api/v1/analyze\")" in content,
            "analyze-pdf endpoint uses Depends": "Depends(verify_supabase_jwt)" in content and "@app.post(\"/api/v1/analyze-pdf\")" in content,
            "history endpoint uses Depends": "Depends(verify_supabase_jwt)" in content and "@app.get(\"/api/v1/history\")" in content,
            "get_or_create_user function": "def get_or_create_user" in content,
            "User model imported": "from models import" in content and "User" in content,
            "Rate limiting applied": "@limiter.limit" in content,
            "user_id linked to Analysis": "Analysis(user_id=" in content or "user_id=db_user.id" in content,
        }
        
        for check_name, passed in checks.items():
            result = check(check_name, passed, "CRITICAL" if passed else "CRITICAL")
            results.append(result)
    
    except Exception as e:
        print(f"❌ Error reading main.py: {e}")
        return False
    
    return all(results)


def validate_models():
    """Check models.py implementation"""
    print("\n" + "="*60)
    print("📊 MODELS VALIDATION")
    print("="*60)
    
    results = []
    
    try:
        with open("models.py", "r") as f:
            content = f.read()
        
        checks = {
            "User model exists": "class User(Base):" in content,
            "User has supabase_id": "supabase_id" in content,
            "User has email": "email" in content,
            "User has plan_type": "plan_type" in content,
            "User has daily_usage": "daily_usage" in content,
            "User has monthly_usage": "monthly_usage" in content,
            "Analysis has user_id": "class Analysis" in content and "user_id" in content,
        }
        
        for check_name, passed in checks.items():
            result = check(check_name, passed, "CRITICAL" if passed else "CRITICAL")
            results.append(result)
    
    except Exception as e:
        print(f"❌ Error reading models.py: {e}")
        return False
    
    return all(results)


def validate_database():
    """Check database connectivity"""
    print("\n" + "="*60)
    print("💾 DATABASE VALIDATION")
    print("="*60)
    
    results = []
    
    try:
        from database import SessionLocal
        from models import User, Analysis
        
        db = SessionLocal()
        
        # Check tables exist
        try:
            user_count = db.query(User).count()
            result = check(f"Users table accessible: {user_count} users", True)
            results.append(result)
        except Exception as e:
            result = check(f"Users table: {str(e)}", False, "CRITICAL")
            results.append(result)
        
        try:
            analysis_count = db.query(Analysis).count()
            result = check(f"Analysis table accessible: {analysis_count} records", True)
            results.append(result)
        except Exception as e:
            result = check(f"Analysis table: {str(e)}", False, "CRITICAL")
            results.append(result)
        
        # Check for orphaned records
        try:
            null_user_ids = db.query(Analysis).filter(Analysis.user_id == None).count()
            has_orphans = null_user_ids > 0
            result = check(
                f"No orphaned analyses (found {null_user_ids})",
                not has_orphans,
                "WARNING" if has_orphans else "INFO"
            )
            results.append(result)
        except Exception as e:
            print(f"⚠️  Could not check orphaned records: {e}")
        
        db.close()
    
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    return all(results)


def validate_imports():
    """Check all imports work"""
    print("\n" + "="*60)
    print("📦 IMPORTS VALIDATION")
    print("="*60)
    
    results = []
    
    imports_to_check = {
        "FastAPI": "from fastapi import FastAPI",
        "JWT": "from jose import jwt",
        "SQLAlchemy": "from sqlalchemy import",
        "Pydantic": "from pydantic import",
        "PyPDF2": "import PyPDF2",
    }
    
    for lib_name, import_stmt in imports_to_check.items():
        try:
            exec(import_stmt)
            result = check(f"{lib_name} installed", True)
            results.append(result)
        except ImportError as e:
            result = check(f"{lib_name}: {str(e)}", False, "WARNING")
            results.append(result)
    
    return all(results)


def validate_endpoints():
    """Check endpoints are properly configured"""
    print("\n" + "="*60)
    print("🔌 ENDPOINTS VALIDATION")
    print("="*60)
    
    results = []
    
    try:
        with open("main.py", "r") as f:
            content = f.read()
        
        endpoints = {
            "/api/v1/analyze": True,
            "/api/v1/analyze-pdf": True,
            "/api/v1/history": True,
        }
        
        for endpoint, required in endpoints.items():
            has_endpoint = endpoint in content
            result = check(
                f"Endpoint {endpoint} defined",
                has_endpoint,
                "CRITICAL" if required else "WARNING"
            )
            results.append(result)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return all(results)


def main():
    """Run all validations"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + "  🚀 PRE-PRODUCTION SAAS VALIDATION".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    validations = [
        ("Environment Variables", validate_environment),
        ("Required Files", validate_files),
        ("Authentication Code", validate_auth_code),
        ("Main Code", validate_main_code),
        ("Models", validate_models),
        ("Database", validate_database),
        ("Imports", validate_imports),
        ("Endpoints", validate_endpoints),
    ]
    
    results = {}
    for name, validator in validations:
        try:
            results[name] = validator()
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {str(e)}")
            results[name] = False
    
    # Summary
    print("\n" + "="*60)
    print("📋 SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "="*60)
    
    if passed == total:
        print("🎉 ALL CHECKS PASSED - READY FOR PRODUCTION")
        print("\nNext steps:")
        print("1. Run: python test_saas.py")
        print("2. Test with real users in staging")
        print("3. Deploy to production")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} CHECKS FAILED")
        print("\nFix the issues above before deploying to production")
        sys.exit(1)


if __name__ == "__main__":
    main()
