# -*- coding: utf-8 -*-
"""
TDD 测试: LangSmith 监控模块 (src/monitoring.py)

测试用例: TC-MON-01 ~ TC-MON-08
覆盖 traceable / is_available / get_client 三个公开 API

编码: UTF-8
"""

import pytest
from unittest.mock import MagicMock, patch

import src.monitoring as monitoring_mod


class TestTraceable:
    """测试 traceable() 装饰器工厂"""

    def test_tc_mon_01_traceable_real(self):
        """
        TC-MON-01: traceable 在 langsmith 可用时返回真实装饰器
        前置条件: langsmith 包已安装, LANGSMITH_API_KEY 已配置, LANGCHAIN_TRACING_V2=true
        预期: 返回的装饰器来自 langsmith.traceable, 不是透传函数
        """
        # 模拟 langsmith 可用
        mock_real_traceable = MagicMock(return_value=lambda f: f)
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", True), \
             patch.object(monitoring_mod, "_ls_traceable", mock_real_traceable):
            decorator = monitoring_mod.traceable(name="test-trace")
            # 应该调用了真实的 _ls_traceable
            mock_real_traceable.assert_called_once_with(
                name="test-trace",
                project_name=monitoring_mod.LANGSMITH_PROJECT,
            )
            # 返回的不应该是 passthrough（passthrough 函数被调用时不会走 _ls_traceable）
            assert decorator is not None

    def test_tc_mon_02_traceable_passthrough(self):
        """
        TC-MON-02: traceable 在 langsmith 不可用时返回透传
        前置条件: langsmith 不可用（未安装或未配置）
        预期: 返回原函数本身（透传），不抛异常
        """
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", False):
            def dummy_func(x):
                return x + 1

            decorator = monitoring_mod.traceable(name="test-passthrough")
            wrapped = decorator(dummy_func)

            # 透传装饰器返回原函数本身
            assert wrapped is dummy_func
            # 调用结果不变
            assert wrapped(41) == 42

    def test_tc_mon_03_is_available_true(self):
        """
        TC-MON-03: is_available 在 API Key 配置时返回 True
        前置条件: langsmith 包已安装, LANGSMITH_API_KEY 已配置, LANGCHAIN_TRACING_V2=true
        预期: is_available() 返回 True
        """
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", True):
            assert monitoring_mod.is_available() is True

    def test_tc_mon_04_is_available_false(self):
        """
        TC-MON-04: is_available 在 API Key 未配置时返回 False
        前置条件: LANGSMITH_API_KEY 为空或 LANGCHAIN_TRACING_V2 不为 true
        预期: is_available() 返回 False
        """
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", False):
            assert monitoring_mod.is_available() is False

    def test_tc_mon_05_get_client_instance(self):
        """
        TC-MON-05: get_client 在可用时返回 LangSmith Client 实例
        前置条件: langsmith 可用
        预期: 返回的实例不是 None, 且来自 langsmith.Client
        """
        mock_client = MagicMock()
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", True), \
             patch.object(monitoring_mod, "_LangSmithClient", mock_client), \
             patch.object(monitoring_mod, "_client", None):
            client = monitoring_mod.get_client()
            assert client is not None

    def test_tc_mon_06_get_client_none(self):
        """
        TC-MON-06: get_client 不可用时返回 None
        前置条件: langsmith 不可用
        预期: get_client() 返回 None
        """
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", False):
            client = monitoring_mod.get_client()
            assert client is None

    def test_tc_mon_07_passthrough_no_change(self):
        """
        TC-MON-07: traceable 透传装饰器不改变函数行为
        前置条件: langsmith 不可用
        预期: 被装饰函数行为完全不变（返回值、副作用均保留）
        """
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", False):
            side_effect_log = []

            def func_with_side_effect(a, b):
                side_effect_log.append((a, b))
                return a * b

            decorator = monitoring_mod.traceable(name="noop")
            wrapped = decorator(func_with_side_effect)

            # 函数行为不变
            assert wrapped(3, 5) == 15
            assert wrapped(10, 2) == 20
            # 副作用不变
            assert side_effect_log == [(3, 5), (10, 2)]
            # 函数元信息不变
            assert wrapped.__name__ == func_with_side_effect.__name__

    def test_tc_mon_08_get_client_singleton(self):
        """
        TC-MON-08: get_client 重复调用返回同一单例
        前置条件: langsmith 可用
        预期: 多次调用 get_client() 返回同一个实例
        """
        mock_client_class = MagicMock()
        with patch.object(monitoring_mod, "LANGSMITH_ENABLED", True), \
             patch.object(monitoring_mod, "_LangSmithClient", mock_client_class), \
             patch.object(monitoring_mod, "_client", None):
            client1 = monitoring_mod.get_client()
            client2 = monitoring_mod.get_client()
            # 应该是同一个实例
            assert client1 is client2
            # _LangSmithClient 只被构造了一次
            assert mock_client_class.call_count == 1
