"""轮灌状态机：所有状态迁移必须经由本模块的单一判定。

合法迁移只有三类：
- 已排程 scheduled → 进行中 running
- 进行中 running → 已完成 done
- 任意非终态（scheduled/running）→ 已跳过 skipped

终态 done/skipped 不可再迁出；未变化的状态不算迁移。
"""

from .models import IrrigationCycle

# 单一事实来源：old -> {可迁入的 new}
ALLOWED_TRANSITIONS = {
    IrrigationCycle.STATUS_SCHEDULED: {
        IrrigationCycle.STATUS_RUNNING,
        IrrigationCycle.STATUS_SKIPPED,
    },
    IrrigationCycle.STATUS_RUNNING: {
        IrrigationCycle.STATUS_DONE,
        IrrigationCycle.STATUS_SKIPPED,
    },
    IrrigationCycle.STATUS_DONE: set(),
    IrrigationCycle.STATUS_SKIPPED: set(),
}


def can_transit(old, new):
    """返回是否允许从 old 迁移到 new（状态未变视为允许，不触发迁移）。"""
    if old == new:
        return True
    return new in ALLOWED_TRANSITIONS.get(old, set())


def illegal_transition_message(old, new):
    """非法迁移的统一中文说明。"""
    labels = dict(IrrigationCycle.STATUS_CHOICES)
    return (
        f"轮灌状态不允许从「{labels.get(old, old)}」"
        f"变更为「{labels.get(new, new)}」"
    )
