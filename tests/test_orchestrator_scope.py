import time
import unittest

from agents.base import BaseAgent
from agents.orchestrator.agent import OrchestratorAgent
from agents.orchestrator.scope import AgentScopeOrchestrationRunner
from agents.signal import Signal


class MockAgent(BaseAgent):
    def __init__(self, name, direction="neutral", confidence=0.7, behavior="success", delay=0.0):
        super().__init__(name=name, config={})
        self.signal_type = name.lower()
        self.direction = direction
        self.confidence = confidence
        self.behavior = behavior
        self.delay = delay

    def analyze(self, stock_code: str):
        if self.delay:
            time.sleep(self.delay)
        if self.behavior == "raise":
            raise RuntimeError(f"{self.name} failed")
        if self.behavior == "invalid":
            return {"not": "a signal"}
        return Signal(
            direction=self.direction,
            confidence=self.confidence,
            reasoning=f"{self.name} mock reasoning",
            source=self.name,
            signal_type=self.signal_type,
            stock_code=stock_code,
        )


class AgentScopeOrchestrationRunnerTest(unittest.TestCase):
    def test_all_agents_success(self):
        runner = AgentScopeOrchestrationRunner(config={"agent_timeout_seconds": 1})
        agents = [
            MockAgent("financial", "bullish", 0.8),
            MockAgent("technical", "bullish", 0.7),
            MockAgent("risk", "neutral", 0.7),
        ]

        scope = runner.run_stock("600519", agents)

        self.assertEqual(scope.success_count, 3)
        self.assertEqual(scope.failed_count, 0)
        self.assertEqual(scope.timeout_count, 0)
        self.assertEqual(len(scope.to_signal_bundle().signals), 3)

    def test_agent_exception_is_isolated(self):
        runner = AgentScopeOrchestrationRunner(config={"agent_timeout_seconds": 1})
        agents = [
            MockAgent("financial", "bullish", 0.8),
            MockAgent("technical", behavior="raise"),
            MockAgent("risk", "neutral", 0.7),
        ]

        scope = runner.run_stock("600519", agents)

        self.assertEqual(scope.success_count, 2)
        self.assertEqual(scope.failed_count, 1)
        self.assertIn("failed", [result.status for result in scope.execution_results])

    def test_agent_timeout_is_isolated(self):
        runner = AgentScopeOrchestrationRunner(config={"agent_timeout_seconds": 0.05})
        agents = [
            MockAgent("financial", "bullish", 0.8),
            MockAgent("technical", delay=0.2),
        ]

        scope = runner.run_stock("600519", agents)

        self.assertEqual(scope.success_count, 1)
        self.assertEqual(scope.timeout_count, 1)

    def test_invalid_agent_result_is_isolated(self):
        runner = AgentScopeOrchestrationRunner(config={"agent_timeout_seconds": 1})
        agents = [
            MockAgent("financial", "bullish", 0.8),
            MockAgent("technical", behavior="invalid"),
        ]

        scope = runner.run_stock("600519", agents)

        self.assertEqual(scope.success_count, 1)
        self.assertEqual(scope.invalid_count, 1)


class OrchestratorAgentScopeIntegrationTest(unittest.TestCase):
    def test_no_effective_signal_returns_wait_with_trace(self):
        orchestrator = OrchestratorAgent(config={"confidence_threshold": 0.6, "agent_timeout_seconds": 1})
        orchestrator.register_expert(MockAgent("financial", "neutral", 0.1))
        orchestrator.register_expert(MockAgent("technical", "neutral", 0.1))
        orchestrator.register_expert(MockAgent("risk", "neutral", 0.1))

        result = orchestrator.analyze("600519")

        self.assertEqual(result.decision, "wait")
        self.assertEqual(result.direction, "neutral")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.scope_trace["summary"]["success_count"], 3)

    def test_analyze_many_returns_result_by_stock_code(self):
        orchestrator = OrchestratorAgent(config={"confidence_threshold": 0.6, "agent_timeout_seconds": 1})
        orchestrator.register_expert(MockAgent("financial", "bullish", 0.8))
        orchestrator.register_expert(MockAgent("technical", "bullish", 0.8))
        orchestrator.register_expert(MockAgent("risk", "neutral", 0.8))

        results = orchestrator.analyze_many(["600519", "000858"])

        self.assertEqual(set(results), {"600519", "000858"})
        self.assertTrue(all(result.scope_trace for result in results.values()))


if __name__ == "__main__":
    unittest.main()
