import threading
import unittest
from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, TransactionTestCase

from accounts.models import User
from core.irrigation_state import can_transit
from core.models import Greenhouse, IrrigationCycle, Zone
from core.views import Conflict, save_with_status_guard

S = IrrigationCycle.STATUS_SCHEDULED
R = IrrigationCycle.STATUS_RUNNING
D = IrrigationCycle.STATUS_DONE
K = IrrigationCycle.STATUS_SKIPPED


class TransitionMatrixTests(unittest.TestCase):
    """纯函数层：合法迁移判定只有这一个入口。"""

    def test_allowed(self):
        self.assertTrue(can_transit(S, R))  # 已排程 → 进行中
        self.assertTrue(can_transit(R, D))  # 进行中 → 已完成
        self.assertTrue(can_transit(S, K))  # 任意非终态 → 已跳过
        self.assertTrue(can_transit(R, K))

    def test_no_change_is_allowed(self):
        for s in (S, R, D, K):
            self.assertTrue(can_transit(s, s))

    def test_illegal(self):
        self.assertFalse(can_transit(S, D))  # 不允许已排程直接完成
        self.assertFalse(can_transit(R, S))
        self.assertFalse(can_transit(D, R))
        self.assertFalse(can_transit(D, K))
        self.assertFalse(can_transit(K, R))
        self.assertFalse(can_transit(K, D))
        self.assertFalse(can_transit(S, "bogus"))


class IrrigationApiMixin:
    def _setup_data(self):
        self.user = User.objects.create_user(username="tester", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.gh = Greenhouse.objects.create(name="测试棚")
        self.zone = Zone.objects.create(
            greenhouse=self.gh, zone_code="Z1", status=Zone.STATUS_GROWING
        )
        self.list_url = reverse("irrigation-cycle-list")

    def _put_status(self, cycle, new_status):
        payload = {
            "zoneId": self.zone.pk,
            "startAt": cycle.start_at.isoformat(),
            "durationMin": cycle.duration_min,
            "waterLiters": str(cycle.water_liters),
            "status": new_status,
        }
        url = reverse("irrigation-cycle-detail", args=[cycle.pk])
        return self.client.put(url, payload, format="json")

    def _create(self, status_value=S):
        return IrrigationCycle.objects.create(
            zone=self.zone,
            start_at=timezone.now() + timedelta(hours=1),
            duration_min=30,
            water_liters=Decimal("100.00"),
            status=status_value,
        )


class IrrigationTransitionApiTests(IrrigationApiMixin, TransactionTestCase):
    def setUp(self):
        self._setup_data()

    def test_legal_chain(self):
        c = self._create(S)
        resp = self._put_status(c, R)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        c.refresh_from_db()
        self.assertEqual(c.status, R)

        resp = self._put_status(c, D)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        c.refresh_from_db()
        self.assertEqual(c.status, D)

    def test_skip_from_non_terminal(self):
        c = self._create(S)
        resp = self._put_status(c, K)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        c2 = self._create(S)
        self._put_status(c2, R)
        c2.refresh_from_db()
        resp = self._put_status(c2, K)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_scheduled_to_done_is_409_chinese(self):
        c = self._create(S)
        resp = self._put_status(c, D)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        detail = str(resp.data["detail"])
        self.assertIn("不允许", detail)
        self.assertIn("已排程", detail)
        self.assertIn("已完成", detail)
        c.refresh_from_db()
        self.assertEqual(c.status, S)  # 失败不得改库

    def test_terminal_cannot_move(self):
        c = self._create(D)
        resp = self._put_status(c, R)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("不允许", str(resp.data["detail"]))

        c2 = self._create(K)
        resp = self._put_status(c2, D)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("不允许", str(resp.data["detail"]))

    def test_running_back_to_scheduled_is_409(self):
        c = self._create(S)
        self._put_status(c, R)
        c.refresh_from_db()
        resp = self._put_status(c, S)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_invalid_status_value_is_400(self):
        c = self._create(S)
        resp = self._put_status(c, "wat")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_works_after_failed_advance(self):
        # 先制造一次非法推进失败
        c = self._create(S)
        bad = self._put_status(c, D)
        self.assertEqual(bad.status_code, status.HTTP_409_CONFLICT)

        # 再模拟历史脏数据：存在两条 running（老版本并发漏洞留下的）
        c2 = self._create(R)
        IrrigationCycle.objects.filter(pk=c.pk).update(status=R)

        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        results = resp.data["results"]
        statuses = sorted(r["status"] for r in results)
        self.assertEqual(statuses, [R, R])

        # 带过滤参数同样可用
        resp = self.client.get(self.list_url, {"status": R})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 2)


@unittest.skipUnless(
    connection.vendor == "postgresql",
    "select_for_update 的真实行锁互斥只在 PostgreSQL 上验证",
)
class ParallelAdvanceTests(IrrigationApiMixin, TransactionTestCase):
    def setUp(self):
        self._setup_data()

    def test_parallel_scheduled_to_running_wins_once(self):
        cycle = self._create(S)
        outcomes = []
        entered_lock = threading.Event()
        release_lock = threading.Event()

        def slow_mutate(locked):
            # 先占住行锁，确认第二个请求已在锁上等待再放行
            entered_lock.set()
            self.assertTrue(release_lock.wait(timeout=5))
            locked.status = R
            locked.save()

        def advance(slow):
            try:
                save_with_status_guard(
                    cycle.pk,
                    S,  # 两个请求进入时读到的都是 scheduled
                    R,
                    slow_mutate if slow else (lambda c: None),
                )
                outcomes.append("ok")
            except Conflict as exc:
                outcomes.append(("409", str(exc.detail)))
            except Exception as exc:  # noqa: BLE001 - 测试要暴露任何非预期异常
                outcomes.append(("other", repr(exc)))
            finally:
                connection.close()

        t1 = threading.Thread(target=advance, args=(True,))
        t2 = threading.Thread(target=advance, args=(False,))
        t1.start()
        self.assertTrue(entered_lock.wait(timeout=5))
        t2.start()
        # 给 t2 时间发起 select_for_update 并真正阻塞在 t1 的行锁上
        release_lock.set()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertFalse(t1.is_alive() or t2.is_alive())
        self.assertEqual(outcomes.count("ok"), 1, outcomes)
        self.assertEqual(len(outcomes), 2)
        conflict = [o for o in outcomes if isinstance(o, tuple) and o[0] == "409"]
        self.assertEqual(len(conflict), 1)
        self.assertIn("已被其他操作推进", conflict[0][1])

        cycle.refresh_from_db()
        self.assertEqual(cycle.status, R)
        self.assertEqual(
            IrrigationCycle.objects.filter(pk=cycle.pk, status=R).count(), 1
        )

        # 冲突之后列表仍可用
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
