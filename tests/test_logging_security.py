"""
Tests for secure logging - verifies sensitive data masking.
"""
import logging
import re

import pytest

from core.logging_config import SensitiveDataFormatter, LOG_FORMAT, DATE_FORMAT


@pytest.fixture
def test_logger():
    """Create a test logger with SensitiveDataFormatter."""
    logger = logging.getLogger("test_security_logging")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    # Create a string handler to capture output
    import io
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SensitiveDataFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
    
    return logger, stream


class TestSensitiveDataFormatter:
    """Test cases for sensitive data masking in logs."""
    
    def test_mask_password_equals(self, test_logger):
        """Test masking password=value patterns."""
        logger, stream = test_logger
        logger.info("User login with password=mysecretpassword")
        output = stream.getvalue()
        
        assert "mysecretpassword" not in output
        assert "password=***" in output
    
    def test_mask_password_colon(self, test_logger):
        """Test masking password: value patterns."""
        logger, stream = test_logger
        logger.info("Config: password: 'supersecret123'")
        output = stream.getvalue()
        
        assert "supersecret123" not in output
        assert "password=***" in output
    
    def test_mask_token(self, test_logger):
        """Test masking token values."""
        logger, stream = test_logger
        logger.info("Request with token=abc123xyz789")
        output = stream.getvalue()
        
        assert "abc123xyz789" not in output
        assert "token=***" in output
    
    def test_mask_access_token(self, test_logger):
        """Test masking access_token values."""
        logger, stream = test_logger
        logger.info("OAuth access_token='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'")
        output = stream.getvalue()
        
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in output
        assert "access_token=***" in output
    
    def test_mask_api_key(self, test_logger):
        """Test masking api_key values."""
        logger, stream = test_logger
        logger.info("Using api_key=sk_live_1234567890abcdef")
        output = stream.getvalue()
        
        assert "sk_live_1234567890abcdef" not in output
        assert "api_key=***" in output
    
    def test_mask_secret(self, test_logger):
        """Test masking secret values."""
        logger, stream = test_logger
        logger.info("Channel secret=my_channel_secret_value")
        output = stream.getvalue()
        
        assert "my_channel_secret_value" not in output
        assert "secret=***" in output
    
    def test_mask_bearer_token(self, test_logger):
        """Test masking Bearer tokens in headers."""
        logger, stream = test_logger
        # Test standalone Bearer token (not after Authorization:)
        logger.info("Using Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.sig for auth")
        output = stream.getvalue()
        
        assert "eyJhbGciOiJIUzI1NiJ9" not in output
        assert "Bearer ***" in output
    
    def test_mask_url_token_param(self, test_logger):
        """Test masking token in URL query parameters."""
        logger, stream = test_logger
        logger.info("Request: /api/verify?token=abc123def456&user=john")
        output = stream.getvalue()
        
        assert "abc123def456" not in output
        assert "token=***" in output
        assert "user=john" in output  # Non-sensitive param should remain
    
    def test_mask_url_key_param(self, test_logger):
        """Test masking key in URL query parameters."""
        logger, stream = test_logger
        logger.info("Webhook: /callback?key=secret_key_123")
        output = stream.getvalue()
        
        assert "secret_key_123" not in output
        assert "key=***" in output
    
    def test_mask_email_address(self, test_logger):
        """Test partial masking of email addresses."""
        logger, stream = test_logger
        logger.info("Sending email to john.doe@example.com")
        output = stream.getvalue()
        
        # Should mask middle part but keep first 2 chars and domain
        assert "john.doe@example.com" not in output
        assert "jo***@example.com" in output
    
    def test_mask_multiple_emails(self, test_logger):
        """Test masking multiple email addresses."""
        logger, stream = test_logger
        logger.info("From: admin@test.org To: user@company.com")
        output = stream.getvalue()
        
        assert "admin@test.org" not in output
        assert "user@company.com" not in output
        assert "ad***@test.org" in output
        assert "us***@company.com" in output
    
    def test_no_false_positive_normal_text(self, test_logger):
        """Test that normal text is not masked."""
        logger, stream = test_logger
        logger.info("User ID is 12345, order ID is 67890")
        output = stream.getvalue()
        
        assert "User ID is 12345" in output
        assert "order ID is 67890" in output
    
    def test_no_false_positive_file_path(self, test_logger):
        """Test that file paths are not masked."""
        logger, stream = test_logger
        logger.info("Loading config from /etc/app/config.yaml")
        output = stream.getvalue()
        
        assert "/etc/app/config.yaml" in output
    
    def test_mask_channel_secret(self, test_logger):
        """Test masking LINE channel_secret."""
        logger, stream = test_logger
        logger.info("LINE channel_secret=abc123def456ghi789")
        output = stream.getvalue()
        
        assert "abc123def456ghi789" not in output
        assert "channel_secret=***" in output
    
    def test_mask_channel_access_token(self, test_logger):
        """Test masking LINE channel_access_token."""
        logger, stream = test_logger
        logger.info("Using channel_access_token=very_long_access_token_here")
        output = stream.getvalue()
        
        assert "very_long_access_token_here" not in output
        assert "channel_access_token=***" in output
    
    def test_case_insensitive_masking(self, test_logger):
        """Test that masking is case-insensitive."""
        logger, stream = test_logger
        logger.info("PASSWORD=secret1 Token=secret2 API_KEY=secret3")
        output = stream.getvalue()
        
        assert "secret1" not in output
        assert "secret2" not in output
        assert "secret3" not in output
    
    def test_mask_database_url(self, test_logger):
        """Test masking database URL with credentials."""
        logger, stream = test_logger
        logger.info("Connecting to postgresql+asyncpg://admin:supersecret123@db.example.com:5432/mydb")
        output = stream.getvalue()
        
        assert "supersecret123" not in output
        assert "postgresql+asyncpg://admin:***@db.example.com" in output
    
    def test_mask_line_user_id(self, test_logger):
        """Test partial masking of LINE user ID."""
        logger, stream = test_logger
        logger.info("User LINE ID: Uabcdef1234567890abcdef1234567890")
        output = stream.getvalue()
        
        # Should keep first 9 chars (U + 8 hex) and mask rest
        assert "Uabcdef1234567890abcdef1234567890" not in output
        assert "Uabcdef12***" in output
    
    def test_mask_jwt_standalone(self, test_logger):
        """Test masking standalone JWT tokens."""
        logger, stream = test_logger
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        logger.info(f"Processing JWT {jwt} in request")
        output = stream.getvalue()
        
        assert jwt not in output
        assert "[JWT:***]" in output
    
    def test_mask_id_token(self, test_logger):
        """Test masking id_token key-value."""
        logger, stream = test_logger
        logger.info("Received id_token=eyJhbGciOiJIUzI1NiJ9")
        output = stream.getvalue()
        
        assert "eyJhbGciOiJIUzI1NiJ9" not in output
        assert "id_token=***" in output
    
    def test_mask_line_sub(self, test_logger):
        """Test masking line_sub key-value."""
        logger, stream = test_logger
        logger.info("User line_sub=abc123def456ghi789")
        output = stream.getvalue()
        
        assert "abc123def456ghi789" not in output
        assert "line_sub=***" in output
