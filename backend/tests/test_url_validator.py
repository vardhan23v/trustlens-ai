"""Unit tests for URL safety validator and SSRF protections."""
import pytest
from app.utils.url_validator import is_safe_url


def test_valid_https_urls():
    assert is_safe_url("https://www.reuters.com/world/news-article") is True
    assert is_safe_url("https://apnews.com/article/fact-check") is True
    assert is_safe_url("http://example.com/test") is True


def test_blocked_schemes():
    assert is_safe_url("ftp://ftp.example.com/file.txt") is False
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("gopher://127.0.0.1:70") is False
    assert is_safe_url("javascript:alert(1)") is False


def test_blocked_loopback_and_private_ips():
    assert is_safe_url("http://127.0.0.1:8000/internal") is False
    assert is_safe_url("http://localhost:8000/metrics") is False
    assert is_safe_url("http://10.0.0.1/admin") is False
    assert is_safe_url("http://192.168.1.1/router") is False
    assert is_safe_url("http://169.254.169.254/latest/meta-data") is False
    assert is_safe_url("http://[::1]/debug") is False


def test_empty_and_malformed_urls():
    assert is_safe_url("") is False
    assert is_safe_url("   ") is False
    assert is_safe_url(None) is False
    assert is_safe_url("http://") is False
    assert is_safe_url("https://") is False
    assert is_safe_url("not_a_valid_url") is False
