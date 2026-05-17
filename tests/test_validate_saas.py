import pytest
from unittest.mock import patch, MagicMock, mock_open
import sys

from validate_saas import (
    check,
    validate_environment,
    validate_files,
    validate_auth_code,
    validate_main_code,
    validate_models,
    validate_database,
    validate_imports,
    validate_endpoints,
    main
)

def test_check():
    assert check("Test check true", True) is True
    assert check("Test check false", False, severity="WARNING") is False
    assert check("Test check critical", False, severity="CRITICAL") is False

@patch("validate_saas.os.getenv")
def test_validate_environment(mock_getenv):
    mock_getenv.side_effect = lambda x: "some_value" if x != "API_KEY" else None
    assert validate_environment() is False # API_KEY optional but we check all results?
    # Wait, required is:
    # SUPABASE_JWT_SECRET, DATABASE_URL, API_KEY.
    # Results is all check results.
    # If API_KEY is None, it returns check("API_KEY: NOT SET", False) -> False.
    # So all(results) will be False.
    
    mock_getenv.side_effect = lambda x: "some_long_secret_value_more_than_20_chars"
    assert validate_environment() is True

@patch("validate_saas.os.path.exists")
def test_validate_files(mock_exists):
    mock_exists.return_value = True
    assert validate_files() is True

    mock_exists.return_value = False
    assert validate_files() is False

def test_validate_auth_code():
    m_open = mock_open(read_data="verify_supabase_jwt jwt.decode 401 Bearer 'sub'")
    with patch("builtins.open", m_open):
        assert validate_auth_code() is True

    m_open_fail = mock_open(read_data="no_auth")
    with patch("builtins.open", m_open_fail):
        assert validate_auth_code() is False

    with patch("builtins.open", side_effect=Exception("Read error")):
        assert validate_auth_code() is False

def test_validate_main_code():
    m_open = mock_open(read_data="Depends(verify_supabase_jwt) @app.post(\"/api/v1/analyze\") @app.post(\"/api/v1/analyze-pdf\") @app.get(\"/api/v1/history\") def get_or_create_user from models import User @limiter.limit Analysis(user_id=")
    with patch("builtins.open", m_open):
        assert validate_main_code() is True

    m_open_fail = mock_open(read_data="no_main")
    with patch("builtins.open", m_open_fail):
        assert validate_main_code() is False

    with patch("builtins.open", side_effect=Exception("Read error")):
        assert validate_main_code() is False

def test_validate_models():
    m_open = mock_open(read_data="class User(Base): supabase_id email plan_type daily_usage monthly_usage class Analysis user_id")
    with patch("builtins.open", m_open):
        assert validate_models() is True

    m_open_fail = mock_open(read_data="no_models")
    with patch("builtins.open", m_open_fail):
        assert validate_models() is False

    with patch("builtins.open", side_effect=Exception("Read error")):
        assert validate_models() is False

@patch("database.SessionLocal")
def test_validate_database(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Successful query
    mock_db.query().count.return_value = 5
    mock_db.query().filter().count.return_value = 0
    assert validate_database() is True

    # Database fail on count
    mock_db.query().count.side_effect = Exception("DB error")
    assert validate_database() is False

    # Database fails on orphaned records check but rest succeeds
    mock_db.query().count.side_effect = None
    mock_db.query().count.return_value = 5
    mock_db.query().filter().count.side_effect = Exception("Orphan check failed")
    assert validate_database() is True

    # Import fails or other error
    with patch("database.SessionLocal", side_effect=Exception("Connection error")):
        assert validate_database() is False

def test_validate_imports():
    with patch("builtins.exec", return_value=None):
        assert validate_imports() is True

    with patch("builtins.exec", side_effect=ImportError("No module")):
        assert validate_imports() is False

def test_validate_endpoints():
    m_open = mock_open(read_data="/api/v1/analyze /api/v1/analyze-pdf /api/v1/history")
    with patch("builtins.open", m_open):
        assert validate_endpoints() is True

    m_open_fail = mock_open(read_data="no_endpoints")
    with patch("builtins.open", m_open_fail):
        assert validate_endpoints() is False

    with patch("builtins.open", side_effect=Exception("Read error")):
        assert validate_endpoints() is False

@patch("validate_saas.sys.exit")
@patch("validate_saas.validate_environment")
@patch("validate_saas.validate_files")
@patch("validate_saas.validate_auth_code")
@patch("validate_saas.validate_main_code")
@patch("validate_saas.validate_models")
@patch("validate_saas.validate_database")
@patch("validate_saas.validate_imports")
@patch("validate_saas.validate_endpoints")
def test_main_pass(
    mock_endpoints, mock_imports, mock_db, mock_models,
    mock_main, mock_auth, mock_files, mock_env, mock_exit
):
    mock_endpoints.return_value = True
    mock_imports.return_value = True
    mock_db.return_value = True
    mock_models.return_value = True
    mock_main.return_value = True
    mock_auth.return_value = True
    mock_files.return_value = True
    mock_env.return_value = True
    
    main()
    mock_exit.assert_called_once_with(0)

@patch("validate_saas.sys.exit")
@patch("validate_saas.validate_environment")
@patch("validate_saas.validate_files")
@patch("validate_saas.validate_auth_code")
@patch("validate_saas.validate_main_code")
@patch("validate_saas.validate_models")
@patch("validate_saas.validate_database")
@patch("validate_saas.validate_imports")
@patch("validate_saas.validate_endpoints")
def test_main_fail(
    mock_endpoints, mock_imports, mock_db, mock_models,
    mock_main, mock_auth, mock_files, mock_env, mock_exit
):
    mock_endpoints.return_value = False # Force failure
    mock_imports.return_value = True
    mock_db.return_value = True
    mock_models.return_value = True
    mock_main.return_value = True
    mock_auth.return_value = True
    mock_files.return_value = True
    mock_env.return_value = True
    
    main()
    mock_exit.assert_called_once_with(1)

@patch("validate_saas.sys.exit")
@patch("validate_saas.validate_environment")
@patch("validate_saas.validate_files")
@patch("validate_saas.validate_auth_code")
@patch("validate_saas.validate_main_code")
@patch("validate_saas.validate_models")
@patch("validate_saas.validate_database")
@patch("validate_saas.validate_imports")
@patch("validate_saas.validate_endpoints")
def test_main_exception(
    mock_endpoints, mock_imports, mock_db, mock_models,
    mock_main, mock_auth, mock_files, mock_env, mock_exit
):
    mock_endpoints.side_effect = Exception("Validator crashed")
    mock_imports.return_value = True
    mock_db.return_value = True
    mock_models.return_value = True
    mock_main.return_value = True
    mock_auth.return_value = True
    mock_files.return_value = True
    mock_env.return_value = True
    
    main()
    mock_exit.assert_called_once_with(1)
