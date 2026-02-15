"""Test file that demonstrates allowed patterns in test context."""


def test_something():
    """Test that uses print (allowed in tests)."""
    print("Test output")  # OK in tests
    assert True


def test_localhost():
    """Test that references localhost (allowed in tests)."""
    url = "http://localhost:8080/api"  # OK in tests
    assert "localhost" in url
