import pytest
from src.core.agents import AgentFactory

@pytest.fixture(autouse=True)
def reset_agent_factory_state():
    AgentFactory.reset_rotation()
    AgentFactory.clear_cache()
    yield
    AgentFactory.reset_rotation()
    AgentFactory.clear_cache()
