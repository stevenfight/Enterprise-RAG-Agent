# -*- coding: utf-8 -*-
"""统一 API 会话记忆入口测试。"""

from src import api_service


def test_session_memory_uses_loaded_configuration(monkeypatch):
    api_service._shared_state["ag_cfg"] = {
        "memory_working_memory_limit": 7,
        "memory_episodic_memory_turns": 3,
        "memory_enable_long_term": True,
    }
    api_service.conversation_store = api_service.ConversationStore()

    cm, memory = api_service._get_or_create_conversation_memory("session-a")

    assert cm.agent_memory is memory
    assert memory.working_memory_limit == 7
    assert memory.episodic_memory_turns == 3
    assert memory.enable_long_term is True
    assert memory.session_id == "session-a"


def test_session_memory_reuses_existing_instance(monkeypatch):
    api_service._shared_state["ag_cfg"] = {
        "memory_working_memory_limit": 10,
        "memory_episodic_memory_turns": 5,
        "memory_enable_long_term": False,
    }
    api_service.conversation_store = api_service.ConversationStore()

    _, first = api_service._get_or_create_conversation_memory("session-a")
    _, second = api_service._get_or_create_conversation_memory("session-a")

    assert first is second


def test_session_memory_isolated_by_conversation_id():
    api_service._shared_state["ag_cfg"] = {
        "memory_working_memory_limit": 10,
        "memory_episodic_memory_turns": 5,
        "memory_enable_long_term": True,
    }
    api_service.conversation_store = api_service.ConversationStore()

    _, first = api_service._get_or_create_conversation_memory("session-a")
    _, second = api_service._get_or_create_conversation_memory("session-b")

    assert first is not second
    assert first.session_id != second.session_id
