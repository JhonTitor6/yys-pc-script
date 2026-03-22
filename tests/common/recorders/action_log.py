# tests/common/recorders/action_log.py
from dataclasses import dataclass, field
from typing import List


@dataclass
class ActionRecord:
    """单次操作记录"""
    action_type: str
    x: int
    y: int
    timestamp: float
    extra: dict = field(default_factory=dict)


class ActionLog:
    """操作日志容器"""

    def __init__(self):
        self._records: List[ActionRecord] = []

    def add(self, record: ActionRecord) -> None:
        """添加一条操作记录"""
        self._records.append(record)

    def clear(self) -> None:
        """清空所有记录"""
        self._records.clear()

    @property
    def records(self) -> List[ActionRecord]:
        """获取所有记录的副本"""
        return self._records.copy()

    def get_last(self, n: int = 1) -> List[ActionRecord]:
        """获取最后 n 条记录"""
        return self._records[-n:] if n <= len(self._records) else self._records.copy()

    def find_by_type(self, action_type: str) -> List[ActionRecord]:
        """查找指定类型的操作"""
        return [r for r in self._records if r.action_type == action_type]

    def assert_click_at(self, x: int, y: int, tolerance: int = 10) -> None:
        """断言存在一次点击在指定坐标（误差范围 tolerance）"""
        for record in self._records:
            if record.action_type in ("left_click", "right_click"):
                if abs(record.x - x) <= tolerance and abs(record.y - y) <= tolerance:
                    return
        raise AssertionError(f"No click found near ({x}, {y}) within tolerance {tolerance}")

    def assert_click_count(self, count: int, action_type: str = "left_click") -> None:
        """断言指定类型的点击次数"""
        actual = len(self.find_by_type(action_type))
        if actual != count:
            raise AssertionError(f"Expected {count} {action_type} actions, got {actual}")

    def __len__(self) -> int:
        return len(self._records)

    def __bool__(self) -> bool:
        """始终返回 True，确保 ActionLog 对象在 or 表达式中始终被视为有效"""
        return True

    def __repr__(self) -> str:
        return f"ActionLog({len(self._records)} records)"