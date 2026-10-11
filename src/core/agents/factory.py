from __future__ import annotations

import threading
from typing import TypeVar
from pydantic import BaseModel
from pydantic_ai.models import Model
from src.config import Settings, setup_logger, read_text, read_yaml, exists, list_files, get_rel_path
from src.schema import AgentProfile, AgentOutput
from src.core.validators import GeneralAgentValidator
from src.helpers import NotFoundError, ValidationError
from .base import Agent, ModelValidator

T = TypeVar("T", bound=BaseModel)
logger = setup_logger(boss_name="core.agents.main.txt", his_name="core.agents.factory.txt")
_SHARED_ROTATION_COUNTERS: dict[str, int] = {}
_ROTATION_LOCK = threading.Lock()
_PROFILE_CACHE: dict[str, dict[str, AgentProfile]] = {}
_PROFILE_CACHE_LOCK = threading.Lock()


class AgentFactory:
    def __init__(self, directory: str = Settings.AGENT_PORFILE, auto_discover: bool = True) -> None:
        self.directory: str = directory
        self._profiles: dict[str, AgentProfile] = {}
        self._rotation_counters: dict[str, int] = {}
        if auto_discover:
            self.auto_discover(self.directory)

    def register(self, agent: AgentProfile | str) -> AgentProfile:
        if isinstance(agent, AgentProfile):
            if not agent.name or not agent.name.strip():
                raise ValidationError("Agent profile name cannot be empty")
            self._profiles[agent.name] = agent
            logger.info(f"Registered agent profile: '{agent.name}'")
            return agent
        return self.register_from_yaml(agent)

    def register_from_yaml(self, agent_path: str) -> AgentProfile:
        if not exists(agent_path):
            raise NotFoundError(f"Agent config YAML not found: {agent_path}")
        data = read_yaml(agent_path)
        if not isinstance(data, dict):
            raise ValidationError(f"Invalid YAML content in {agent_path}, expected dictionary")
        profile = AgentProfile.model_validate(data)
        self._profiles[profile.name] = profile
        logger.info(f"Registered agent profile: '{profile.name}'")
        return profile


    def auto_discover(self, directory: str = Settings.AGENT_PORFILE) -> list[AgentProfile]:
        with _PROFILE_CACHE_LOCK:
            if directory in _PROFILE_CACHE:
                cached = _PROFILE_CACHE[directory]
                self._profiles.update(cached)
                return list(cached.values())

            loaded: list[AgentProfile] = []
            if exists(directory):
                for p in list_files(directory, "*.yaml"):
                    try:
                        rel = get_rel_path(p)
                        loaded.append(self.register(rel))
                    except Exception as exc:
                        logger.warning(f"Skipping invalid agent config in {p}: {exc}")
                for p in list_files(directory, "*.yml"):
                    try:
                        rel = get_rel_path(p)
                        loaded.append(self.register(rel))
                    except Exception as exc:
                        logger.warning(f"Skipping invalid agent config in {p}: {exc}")
            _PROFILE_CACHE[directory] = dict(self._profiles)
            return loaded

    def get_profile(self, name: str) -> AgentProfile:
        if name in self._profiles:
            return self._profiles[name]
        for key, prof in self._profiles.items():
            if key == name or prof.name == name or prof.name.startswith(f"{name}_") or name.startswith(f"{prof.name}_"):
                return prof
        raise NotFoundError(f"Agent profile '{name}' not found")

    def list_profiles(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    @classmethod
    def reset_rotation(cls, name: str | None = None) -> None:
        with _ROTATION_LOCK:
            if name:
                _SHARED_ROTATION_COUNTERS.pop(name, None)
            else:
                _SHARED_ROTATION_COUNTERS.clear()

    @classmethod
    def clear_cache(cls) -> None:
        with _PROFILE_CACHE_LOCK:
            _PROFILE_CACHE.clear()

    def _current_client_index(
        self,
        profile: AgentProfile,
        explicit_index: int | None,
        explicit_indices: list[int] | None = None,
    ) -> int:
        if explicit_index is not None:
            return explicit_index
        total_clients = len(Settings.LLM_CLIENTS)
        if total_clients == 0:
            return profile.client_index

        pool = [idx for idx in (explicit_indices or profile.client_indices) if idx >= 1]
        if not profile.is_rotate:
            return pool[0] if pool else profile.client_index

        if not pool:
            pool = list(range(1, total_clients + 1))

        counter_key = f"{profile.name}:{','.join(map(str, pool))}" if explicit_indices else profile.name
        with _ROTATION_LOCK:
            current_pos = _SHARED_ROTATION_COUNTERS.get(counter_key, 0)
            selected = pool[current_pos % len(pool)]
            _SHARED_ROTATION_COUNTERS[counter_key] = (current_pos + 1) % len(pool)
            return selected

    def _resolve_prompt(self, profile: AgentProfile) -> str:
        if profile.prompt_instruction:
            return profile.prompt_instruction
        if profile.prompt_path:
            if exists(profile.prompt_path):
                return read_text(profile.prompt_path)
            raise NotFoundError(f"Prompt file not found for agent '{profile.name}': {profile.prompt_path}")
        raise NotFoundError(f"No prompt configured for agent '{profile.name}'")

    def create(self, agent_name: str = "", client_index: int | None = None,
        client_indices: list[int] | None = None, model: Model | None = None,
        enable_tools: bool | None = None, output_type: type[T] = AgentOutput) -> Agent[T]:
        if not agent_name.strip():
            raise ValidationError("At least one Agent Name is required.")

        profile = self.get_profile(agent_name)
        system_prompt = self._resolve_prompt(profile)
        client_index = self._current_client_index(profile, client_index, client_indices)
        tools = enable_tools if enable_tools is not None else profile.enable_tools
        validator = GeneralAgentValidator() if output_type is AgentOutput else ModelValidator()

        return Agent[T](
            output_type=output_type,
            system_prompt=system_prompt,
            validator=validator,
            agent_name=f"agent.{profile.name}",
            client_index=client_index,
            model=model,
            enable_tools=tools,
        )
