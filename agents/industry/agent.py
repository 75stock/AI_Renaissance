"""
行业景气 Agent - 专家5组

signal_type: industry
Skill 域: skills/industry/
核心能力：产业链景气度、行业拐点、竞争格局
"""

from typing import Optional
from agents.base import BaseAgent
from agents.signal import Signal, neutral_signal, bullish_signal, bearish_signal

try:
    from skills.industry.industrial_sentinel.runtime import run_industrial_sentinel
except Exception:
    run_industrial_sentinel = None


class IndustryAgent(BaseAgent):
    """行业景气 Agent（专家5组）"""

    signal_type = "industry"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(name="行业景气Agent", config=config or {})
        self.load_skills_from_domain("industry")

    def analyze(self, stock_code: str) -> Signal:
        """运行 industrial-sentinel skill，返回行业景气度 Signal。

        调用 skills/industry/industrial-sentinel/runtime.py 的
        run_industrial_sentinel()，将其返回的 dict 包装为标准 Signal。
        """
        self.log(f"开始行业景气分析：{stock_code}")

        if run_industrial_sentinel is None:
            return neutral_signal(
                confidence=0.1,
                reasoning="industrial-sentinel runtime 导入失败",
                source=self.name,
                stock_code=stock_code,
                signal_type=self.signal_type,
            )

        try:
            result = run_industrial_sentinel(stock_code, self.config)
        except Exception as exc:
            self.log(f"industrial-sentinel 执行失败：{exc}", level="error")
            return neutral_signal(
                confidence=0.1,
                reasoning=f"industrial-sentinel 执行异常: {exc}",
                source=self.name,
                stock_code=stock_code,
                signal_type=self.signal_type,
            )

        direction = result.get("direction", "neutral")
        confidence = float(result.get("confidence", 0.1))
        reasoning = result.get("reasoning", "")
        signals = result.get("signals", [])
        meta = result.get("meta", {})

        if direction == "bullish":
            return bullish_signal(
                confidence=confidence,
                reasoning=reasoning,
                signals=signals,
                source=self.name,
                stock_code=stock_code,
                signal_type=self.signal_type,
                meta=meta,
            )
        elif direction == "bearish":
            return bearish_signal(
                confidence=confidence,
                reasoning=reasoning,
                signals=signals,
                source=self.name,
                stock_code=stock_code,
                signal_type=self.signal_type,
                meta=meta,
            )
        else:
            return neutral_signal(
                confidence=confidence,
                reasoning=reasoning,
                source=self.name,
                stock_code=stock_code,
                signal_type=self.signal_type,
                meta=meta,
            )
