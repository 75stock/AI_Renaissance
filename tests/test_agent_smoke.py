import importlib

import pytest

from agents.signal import Signal
from main import EXPERT_AGENTS


class FakeNewsSource:
    def get_posts(self, stock_code: str, pages: int = 1, fetch_content: bool = False):
        return {
            "status": "success",
            "stock_code": stock_code,
            "posts": [
                {"title": "offline post 1", "content": "fixture", "reads": 100, "post_time": "", "source_type": "test"},
                {"title": "offline post 2", "content": "fixture", "reads": 90, "post_time": "", "source_type": "test"},
                {"title": "offline post 3", "content": "fixture", "reads": 80, "post_time": "", "source_type": "test"},
                {"title": "offline post 4", "content": "fixture", "reads": 70, "post_time": "", "source_type": "test"},
                {"title": "offline post 5", "content": "fixture", "reads": 60, "post_time": "", "source_type": "test"},
            ],
        }

    def get_sentiment_data(self):
        return {
            "status": "success",
            "score": 50.0,
            "stage": {"name": "neutral", "position": "30-50%", "direction": "neutral"},
            "direction": "neutral",
            "confidence": 0.3,
            "indicators": {},
            "raw_data": {},
            "special_signals": [],
            "uncertainties": [],
        }

    def get_industry_sentiment(self, stock_code: str):
        return {
            "status": "success",
            "industry_name": "test industry",
            "score": 50.0,
            "stage": {"name": "neutral", "position": "30-50%", "direction": "neutral"},
            "direction": "neutral",
            "confidence": 0.3,
            "position_suggestion": "30-50%",
            "special_signals": [],
            "indicators": {},
            "raw_data_summary": {},
            "uncertainties": [],
        }


def offline_config(signal_type: str):
    if signal_type != "news":
        return {}

    fake_news_source = FakeNewsSource()
    return {
        "pages": 1,
        "fetch_content": False,
        "guba_data_source": fake_news_source,
        "market_sentiment_source": fake_news_source,
        "industry_sentiment_source": fake_news_source,
    }


@pytest.mark.parametrize("agent_name,agent_info", EXPERT_AGENTS.items())
def test_registered_expert_agent_can_run_offline(agent_name, agent_info):
    module = importlib.import_module(agent_info["module"])
    agent_class = getattr(module, agent_info["class"])
    agent = agent_class(config=offline_config(agent_info["signal_type"]))

    signal = agent.analyze("000001")

    assert isinstance(signal, Signal)
    assert signal.stock_code == "000001"
    assert signal.signal_type == agent_info["signal_type"]
    assert signal.direction in {"bullish", "bearish", "neutral"}
    assert 0.0 <= signal.confidence <= 1.0
    assert signal.reasoning
