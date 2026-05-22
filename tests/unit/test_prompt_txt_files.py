"""Tests for stage prompt .txt file list helpers."""
from __future__ import annotations

from pa_agent.ai.prompt_assembler import (
    COMMON_SYSTEM_PROMPT_TXT_FILES,
    STAGE1_TASK_PROMPT_TXT_FILES,
    STAGE2_BASE_PROMPT_TXT_FILES,
    STAGE2_FULL_STRATEGY_PROMPT_TXT_FILES,
    stage1_prompt_txt_files,
    stage2_prompt_txt_files,
    stage2_user_task_txt_files,
)


def test_stage1_txt_files() -> None:
    files = stage1_prompt_txt_files()
    assert files == [*COMMON_SYSTEM_PROMPT_TXT_FILES, *STAGE1_TASK_PROMPT_TXT_FILES]


def test_stage2_txt_files_order() -> None:
    routed = ["震荡区间交易策略.txt", "震荡区间分析识别.txt"]
    files = stage2_prompt_txt_files(routed)
    expected_user = stage2_user_task_txt_files(routed)
    assert files == [*COMMON_SYSTEM_PROMPT_TXT_FILES, *expected_user]
    assert files[:2] == list(COMMON_SYSTEM_PROMPT_TXT_FILES)
    assert files[-3:] == list(STAGE2_BASE_PROMPT_TXT_FILES)
    assert routed[0] in files
    assert "文件17-止损和止盈与仓位管理.txt" in files
    for name in STAGE2_FULL_STRATEGY_PROMPT_TXT_FILES:
        assert name in files
