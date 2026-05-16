from mmcp.application.features.tokens.service import TokenBudgetService
from mmcp.infrastructure.tokens.token_counter import TokenBudget


class FakeTokenCounter:
    def __init__(self):
        self.text_calls = []
        self.message_calls = []

    def count_tokens(self, text: str, encoding_name: str = "cl100k_base") -> int:
        self.text_calls.append((text, encoding_name))
        return 11 if text == "Hola" else 7

    def count_messages_tokens(self, messages: list[dict], encoding_name: str = "cl100k_base") -> int:
        self.message_calls.append((messages, encoding_name))
        content = messages[0].get("content", "") if messages else ""
        if len(messages) == 2:
            return 19
        if content == "Base instructions":
            return 8
        if content == "Need help":
            return 7
        return 5

    def get_cache_info(self) -> dict:
        return {"hits": 4, "misses": 1, "maxsize": 1024, "currsize": 1, "hit_rate": 80.0}


def test_count_text_consumes_budget_behind_port():
    counter = FakeTokenCounter()
    service = TokenBudgetService(counter, TokenBudget(max_tokens=100, safety_buffer=0.05))

    result = service.count_text("Hola", "cl100k_base")

    assert result == {
        "token_count": 11,
        "encoding": "cl100k_base",
        "budget": {
            "max_tokens": 100,
            "effective_limit": 95,
            "consumed": 11,
            "remaining": 84,
            "usage_percent": 11.58,
            "safety_buffer_percent": 5.0,
        },
    }
    assert counter.text_calls == [("Hola", "cl100k_base")]


def test_count_messages_preserves_breakdown_and_budget():
    counter = FakeTokenCounter()
    service = TokenBudgetService(counter, TokenBudget(max_tokens=100, safety_buffer=0.05))

    result = service.count_messages(
        [
            {"role": "system", "content": "Base instructions"},
            {"role": "user", "content": "Need help"},
        ],
        "o200k_base",
    )

    assert result == {
        "total_tokens": 19,
        "message_count": 2,
        "breakdown": [
            {"role": "system", "tokens": 8, "content_preview": "Base instructions"},
            {"role": "user", "tokens": 7, "content_preview": "Need help"},
        ],
        "encoding": "o200k_base",
        "budget": {
            "max_tokens": 100,
            "effective_limit": 95,
            "consumed": 19,
            "remaining": 76,
            "usage_percent": 20.0,
            "safety_buffer_percent": 5.0,
        },
    }
    assert counter.message_calls == [
        ([{"role": "system", "content": "Base instructions"}, {"role": "user", "content": "Need help"}], "o200k_base"),
        ([{"role": "system", "content": "Base instructions"}], "o200k_base"),
        ([{"role": "user", "content": "Need help"}], "o200k_base"),
    ]


def test_budget_snapshot_includes_cache_info_from_port():
    counter = FakeTokenCounter()
    service = TokenBudgetService(counter, TokenBudget(max_tokens=128, safety_buffer=0.0))

    result = service.budget_snapshot()

    assert result == {
        "max_tokens": 128,
        "effective_limit": 128,
        "consumed": 0,
        "remaining": 128,
        "usage_percent": 0.0,
        "safety_buffer_percent": 0.0,
        "token_count_cache": {"hits": 4, "misses": 1, "maxsize": 1024, "currsize": 1, "hit_rate": 80.0},
    }
