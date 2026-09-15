# TDD：评测数据绑定清单

以下测试先按 RED 记录，完成实现并通过后改为 GREEN。

## GREEN

- [x] RED-01：有效清单绑定实际数据集和来源清单。
- [x] RED-02：绑定清单不存在或 JSON 损坏时失败关闭。
- [x] RED-03：数据集 SHA-256 漂移时失败关闭。
- [x] RED-04：清单路径与 CLI 实际路径不一致时失败关闭。
- [x] RED-05：CLI 传入绑定清单但缺少 `--source-inventory` 时把审计结果写入元数据并返回失败码。
- [x] RED-06：CLI 不传绑定清单时保持既有流程入口不变。

- 测试结果：`tests/test_evaluation_source_binding.py` **5 passed**。
- 候选种子清单：`evals/datasets/core-source-binding.manifest.json`，锁定 `core.jsonl` 与来源清单的 SHA-256；种子来源文件仍未装配，因此完整 CLI 运行按预期失败关闭。
