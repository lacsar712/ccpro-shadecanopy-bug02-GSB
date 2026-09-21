import json
import threading
import urllib.error
import urllib.request
from datetime import timedelta
from decimal import Decimal

from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITransactionTestCase
from rest_framework_simplejwt.tokens import RefreshToken
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer

from accounts.models import User
from core.irrigation_state import can_transit
from core.models import Greenhouse, IrrigationCycle, Zone

from .irrigation_state import (
    DONE,
    RUNNING,
    SCHEDULED,
    SKIPPED,
)


def make_cycle(status=SCHEDULED, **kw):
    greenhouse = Greenhouse.objects.create(name="测试棚", location="测试区")
    zone = Zone.objects.create(greenhouse=greenhouse, zone_code="Z-1")
    return IrrigationCycle.objects.create(
        zone=zone,
        start_at=kw.get("start_at", timezone.now() + timedelta(hours=1)),
        duration_min=kw.get("duration_min", 30),
        water_liters=kw.get("water_liters", Decimal("100.00")),
        status=status,
    )


class TransitionMatrixTests(APITransactionTestCase):
    def test_matrix(self):
        # 合法：scheduled -> running
        self.assertTrue(can_transit(SCHEDULED, RUNNING))
        # 合法：running -> done
        self.assertTrue(can_transit(RUNNING, DONE))
        # 合法：任意非终态 -> skipped
        self.assertTrue(can_transit(SCHEDULED, SKIPPED))
        self.assertTrue(can_transit(RUNNING, SKIPPED))
        # 非法：scheduled -> done（不能跳过进行中）
        self.assertFalse(can_transit(SCHEDULED, DONE))
        # 非法：running -> scheduled（不能回退）
        self.assertFalse(can_transit(RUNNING, SCHEDULED))
        # 非法：终态 -> 任意其它状态
        for terminal in (DONE, SKIPPED):
            for target in (SCHEDULED, RUNNING, DONE, SKIPPED):
                if target == terminal:
                    continue
                self.assertFalse(can_transit(terminal, target))
        # 未知原状态一律非法
        self.assertFalse(can_transit("bogus", RUNNING))


class IrrigationTransitionApiTests(APITransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pw123456")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def url(self, cycle):
        return f"/api/irrigation-cycles/{cycle.pk}/"

    def patch_status(self, cycle, new_status):
        return self.client.patch(self.url(cycle), {"status": new_status}, format="json")

    def test_legal_transitions_succeed(self):
        c = make_cycle(SCHEDULED)
        resp = self.patch_status(c, RUNNING)
        self.assertEqual(resp.status_code, 200, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.status, RUNNING)

        resp = self.patch_status(c, DONE)
        self.assertEqual(resp.status_code, 200, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.status, DONE)

    def test_skip_from_running_succeeds(self):
        c = make_cycle(RUNNING)
        resp = self.patch_status(c, SKIPPED)
        self.assertEqual(resp.status_code, 200, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.status, SKIPPED)

    def test_scheduled_to_done_is_409_chinese(self):
        c = make_cycle(SCHEDULED)
        resp = self.patch_status(c, DONE)
        self.assertEqual(resp.status_code, 409)
        detail = resp.data["detail"]
        self.assertIn("非法状态迁移", str(detail))
        self.assertIn("已完成", str(detail))
        c.refresh_from_db()
        self.assertEqual(c.status, SCHEDULED)

    def test_running_back_to_scheduled_is_409(self):
        c = make_cycle(RUNNING)
        resp = self.patch_status(c, SCHEDULED)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("非法状态迁移", str(resp.data["detail"]))

    def test_terminal_cannot_change(self):
        for terminal in (DONE, SKIPPED):
            c = make_cycle(terminal)
            resp = self.patch_status(c, RUNNING)
            self.assertEqual(resp.status_code, 409, (terminal, resp.content))
            c.refresh_from_db()
            self.assertEqual(c.status, terminal)

    def test_put_full_payload_scheduled_to_done_is_409(self):
        c = make_cycle(SCHEDULED)
        payload = {
            "zoneId": c.zone_id,
            "startAt": c.start_at.isoformat(),
            "durationMin": c.duration_min,
            "waterLiters": str(c.water_liters),
            "status": DONE,
        }
        resp = self.client.put(self.url(c), payload, format="json")
        self.assertEqual(resp.status_code, 409)
        c.refresh_from_db()
        self.assertEqual(c.status, SCHEDULED)

    def test_same_status_edit_of_other_fields_succeeds(self):
        # 状态不变只改其它字段不算迁移，必须允许
        c = make_cycle(RUNNING)
        resp = self.client.patch(
            self.url(c), {"waterLiters": "250.00"}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        c.refresh_from_db()
        self.assertEqual(c.status, RUNNING)
        self.assertEqual(c.water_liters, Decimal("250.00"))

    def test_illegal_transition_does_not_partial_save(self):
        c = make_cycle(SCHEDULED)
        resp = self.client.patch(
            self.url(c),
            {"status": DONE, "waterLiters": "999.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 409)
        c.refresh_from_db()
        self.assertEqual(c.status, SCHEDULED)
        self.assertEqual(c.water_liters, Decimal("100.00"))

    def test_list_still_works_after_failed_transition(self):
        # 推进失败后下一次拉列表必须正常
        c = make_cycle(SCHEDULED)
        fail = self.patch_status(c, DONE)
        self.assertEqual(fail.status_code, 409)

        resp = self.client.get("/api/irrigation-cycles/")
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], SCHEDULED)

    def test_list_works_with_dirty_multiple_running(self):
        # 历史脏数据：存在多个 running 也不能拖垮列表
        make_cycle(RUNNING)
        make_cycle(RUNNING)
        resp = self.client.get("/api/irrigation-cycles/")
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 2)


def http_patch_json(url, token, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


class ConcurrentAdvanceTests(TransactionTestCase):
    """真实多线程 WSGI 服务器上的并发推进测试。

    不用 LiveServerTestCase —— 它内置的 runserver 是单线程的，两个请求
    会被串行接受，无法真正并发。这里每个请求一个线程、一个数据库连接。
    """

    def setUp(self):
        from django.core.handlers.wsgi import WSGIHandler

        self.httpd = ThreadingWSGIServer(("127.0.0.1", 0), QuietWSGIRequestHandler)
        self.httpd.set_app(WSGIHandler())
        self.server_thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.server_thread.join(timeout=5)

    def _race_pair(self, url, token, payload):
        results = []
        barrier = threading.Barrier(2)

        def race():
            barrier.wait()
            results.append(http_patch_json(url, token, payload))

        threads = [threading.Thread(target=race), threading.Thread(target=race)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def test_parallel_scheduled_to_running_only_one_succeeds(self):
        user = User.objects.create_user(username="racer", password="pw123456")
        cycle = make_cycle(SCHEDULED)
        token = str(RefreshToken.for_user(user).access_token)
        url = f"{self.base_url}/api/irrigation-cycles/{cycle.pk}/"

        results = self._race_pair(url, token, {"status": RUNNING})

        statuses = sorted(code for code, _ in results)
        self.assertEqual(statuses, [200, 409], results)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, RUNNING)
        self.assertEqual(
            IrrigationCycle.objects.filter(pk=cycle.pk, status=RUNNING).count(), 1
        )

    def test_list_works_after_conflict(self):
        # 并发落败方拿到 409 后，紧接着拉列表必须正常
        user = User.objects.create_user(username="lister", password="pw123456")
        cycle = make_cycle(SCHEDULED)
        token = str(RefreshToken.for_user(user).access_token)
        url = f"{self.base_url}/api/irrigation-cycles/{cycle.pk}/"

        results = self._race_pair(url, token, {"status": RUNNING})
        loser_body = next(body for code, body in results if code == 409)
        self.assertIn("已被其他操作推进", loser_body)

        req = urllib.request.Request(
            f"{self.base_url}/api/irrigation-cycles/",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            rows = data.get("results", data)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], RUNNING)
