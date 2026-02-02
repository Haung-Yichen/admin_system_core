"""
Unit Tests for core.line_client module.

Tests LineClient class for LINE API communication.
"""

import pytest
import base64
import hmac
import hashlib
from unittest.mock import MagicMock, AsyncMock, patch


class TestLineClientInitialization:
    """Tests for LineClient initialization."""
    
    def test_init_with_config_loader(self, config_loader):
        """Test initialization with ConfigLoader."""
        from core.line_client import LineClient
        
        client = LineClient(config_loader)
        
        assert client._channel_secret == "test-line-secret"
        assert client._access_token == "test-line-token"
    
    def test_init_with_direct_credentials(self):
        """Test initialization with direct credentials."""
        from core.line_client import LineClient
        
        client = LineClient(
            channel_secret="direct-secret",
            access_token="direct-token"
        )
        
        assert client._channel_secret == "direct-secret"
        assert client._access_token == "direct-token"
    
    def test_direct_credentials_override_config(self, config_loader):
        """Test direct credentials take precedence over config."""
        from core.line_client import LineClient
        
        client = LineClient(
            config_loader,
            channel_secret="override-secret",
            access_token="override-token"
        )
        
        assert client._channel_secret == "override-secret"
        assert client._access_token == "override-token"
    
    def test_init_without_credentials(self):
        """Test initialization without any credentials."""
        from core.line_client import LineClient
        
        client = LineClient()
        
        assert client._channel_secret == ""
        assert client._access_token == ""


class TestLineClientIsConfigured:
    """Tests for is_configured() method."""
    
    def test_is_configured_true(self, config_loader):
        """Test is_configured() returns True when credentials exist."""
        from core.line_client import LineClient
        
        client = LineClient(config_loader)
        
        assert client.is_configured() is True
    
    def test_is_configured_false_missing_secret(self):
        """Test is_configured() returns False when secret missing."""
        from core.line_client import LineClient
        
        client = LineClient(access_token="token")
        
        assert client.is_configured() is False
    
    def test_is_configured_false_missing_token(self):
        """Test is_configured() returns False when token missing."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret")
        
        assert client.is_configured() is False


class TestLineClientVerifySignature:
    """Tests for verify_signature() method."""
    
    def test_verify_valid_signature(self):
        """Test verify_signature() returns True for valid signature."""
        from core.line_client import LineClient
        
        secret = "test-secret"
        client = LineClient(channel_secret=secret, access_token="token")
        
        body = b'{"test": "data"}'
        expected_sig = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        
        assert client.verify_signature(body, expected_sig) is True
    
    def test_verify_invalid_signature(self):
        """Test verify_signature() returns False for invalid signature."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        body = b'{"test": "data"}'
        
        assert client.verify_signature(body, "invalid-sig") is False
    
    def test_verify_no_secret_configured(self):
        """Test verify_signature() returns False when no secret."""
        from core.line_client import LineClient
        
        client = LineClient()
        
        assert client.verify_signature(b"body", "sig") is False


class TestLineClientPostReply:
    """Tests for post_reply() method."""
    
    @pytest.mark.asyncio
    async def test_post_reply_success(self):
        """Test post_reply() returns True on success."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.post_reply("reply_token", [{"type": "text", "text": "hi"}])
            
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_reply_failure(self):
        """Test post_reply() returns False on failure."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        
        with patch.object(client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.post_reply("token", [{"type": "text"}])
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_post_reply_not_configured(self):
        """Test post_reply() returns False when not configured."""
        from core.line_client import LineClient
        
        client = LineClient()
        
        result = await client.post_reply("token", [])
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_post_reply_limits_messages(self):
        """Test post_reply() limits to 5 messages."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        messages = [{"type": "text", "text": f"msg{i}"} for i in range(10)]
        
        with patch.object(client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            await client.post_reply("token", messages)
            
            call_args = mock_post.call_args
            sent_messages = call_args.kwargs["json"]["messages"]
            assert len(sent_messages) == 5


class TestLineClientPostPush:
    """Tests for post_push() method."""
    
    @pytest.mark.asyncio
    async def test_post_push_success(self):
        """Test post_push() returns True on success."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(client._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await client.post_push("user_id", [{"type": "text", "text": "hi"}])
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_post_push_not_configured(self):
        """Test post_push() returns False when not configured."""
        from core.line_client import LineClient
        
        client = LineClient()
        
        result = await client.post_push("user_id", [])
        
        assert result is False


class TestLineClientGetProfile:
    """Tests for get_profile() method."""
    
    @pytest.mark.asyncio
    async def test_get_profile_success(self):
        """Test get_profile() returns profile dict on success."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        expected_profile = {"userId": "U123", "displayName": "Test User"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_profile
        
        with patch.object(client._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await client.get_profile("U123")
            
            assert result == expected_profile
    
    @pytest.mark.asyncio
    async def test_get_profile_not_found(self):
        """Test get_profile() returns None on 404."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(client._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await client.get_profile("invalid_id")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_profile_not_configured(self):
        """Test get_profile() returns None when not configured."""
        from core.line_client import LineClient
        
        client = LineClient()
        
        result = await client.get_profile("U123")
        
        assert result is None


class TestLineClientClose:
    """Tests for close() method."""
    
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        """Test close() calls underlying client aclose."""
        from core.line_client import LineClient
        
        client = LineClient(channel_secret="secret", access_token="token")
        
        with patch.object(client._client, 'aclose', new_callable=AsyncMock) as mock_close:
            await client.close()
            
            mock_close.assert_called_once()
