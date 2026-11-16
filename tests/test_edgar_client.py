import pytest

from stockrag.edgar.client import EdgarClient


def test_sec_user_agent_needs_a_contact_address():
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        EdgarClient(user_agent="StockRAG/0.1")
    assert EdgarClient(user_agent="StockRAG/0.1 ops@example.com").user_agent.endswith("example.com")
