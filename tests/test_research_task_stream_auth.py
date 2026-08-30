"""C2.5 新任务事件流必须保留 API key 鉴权。"""


def test_research_task_event_endpoint_is_not_in_auth_skip_paths():
    from src import api_service

    path = "/api/research/tasks/task-1/events"

    assert path not in api_service.APIAuthMiddleware.SKIP_PATHS
    assert not path.startswith(api_service.APIAuthMiddleware.SKIP_PREFIXES)
