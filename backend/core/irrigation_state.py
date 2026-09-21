"""轮灌状态机：合法状态迁移的唯一判定来源。

合法迁移只有三类：
  已排程(scheduled) -> 进行中(running)
  进行中(running)   -> 已完成(done)
  任意非终态        -> 已跳过(skipped)
即 scheduled→running、running→done，以及 scheduled/running→skipped。
"""
from .models import IrrigationCycle

SCHEDULED = IrrigationCycle.STATUS_SCHEDULED
RUNNING = IrrigationCycle.STATUS_RUNNING
DONE = IrrigationCycle.STATUS_DONE
SKIPPED = IrrigationCycle.STATUS_SKIPPED

ALLOWED_TRANSITIONS = {
    SCHEDULED: frozenset({RUNNING, SKIPPED}),
    RUNNING: frozenset({DONE, SKIPPED}),
    DONE: frozenset(),
    SKIPPED: frozenset(),
}

TERMINAL_STATUSES = frozenset({DONE, SKIPPED})
VALID_STATUSES = frozenset(ALLOWED_TRANSITIONS.keys())

STATUS_LABELS = dict(IrrigationCycle.STATUS_CHOICES)


def can_transit(old_status, new_status):
    """判断一次状态变更（old -> new）是否合法的唯一入口。

    仅判定“迁移”，不包含同态编辑（状态不变、只改其它字段），
    同态请求由调用方自行放行。
    """
    return new_status in ALLOWED_TRANSITIONS.get(old_status, frozenset())


def illegal_transition_detail(old_status, new_status):
    """非法迁移对应的中文说明。"""
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    if old_status in TERMINAL_STATUSES:
        return f"非法状态迁移：轮灌已{old_label}，终态不可再变更为{new_label}"
    if old_status == SCHEDULED and new_status == DONE:
        return "非法状态迁移：已排程的轮灌不能直接标记为已完成，请先推进到进行中"
    if old_status == RUNNING and new_status == SCHEDULED:
        return "非法状态迁移：进行中的轮灌不能退回已排程"
    return f"非法状态迁移：{old_label} → {new_label} 不被允许"
