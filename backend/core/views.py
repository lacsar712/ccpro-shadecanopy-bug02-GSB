from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .irrigation_state import can_transit, illegal_transition_message
from .models import ClimateLog, Greenhouse, IrrigationCycle, Zone
from .serializers import (
    ClimateLogSerializer,
    GreenhouseSerializer,
    IrrigationCycleSerializer,
    ZoneSerializer,
)

STATUS_LABELS = dict(IrrigationCycle.STATUS_CHOICES)


class Conflict(APIException):
    """状态迁移冲突，固定返回 409 与中文说明。"""

    status_code = 409
    default_detail = "操作冲突，请刷新后重试"
    default_code = "conflict"


def save_with_status_guard(cycle_pk, stale_status, target, mutate):
    """在行锁内完成状态迁移判定与落库，是迁移的唯一执行入口。

    - SELECT FOR UPDATE 锁定本行，并发推进时后到者必须等先到者提交；
    - stale_status 为请求进入时读到的状态，若与锁内最新状态不一致，
      说明本行已被别的请求改动 → 409；
    - 合法迁移判定统一走 irrigation_state.can_transit，非法 → 409；
    - mutate(locked_instance) 在锁内执行实际保存。
    """
    with transaction.atomic():
        current = IrrigationCycle.objects.select_for_update().get(pk=cycle_pk)
        current_status = current.status
        if current_status != stale_status:
            if target == current_status:
                raise Conflict(
                    f"该轮灌已被其他操作推进为"
                    f"「{STATUS_LABELS.get(current_status, current_status)}」，"
                    f"请勿重复操作"
                )
            raise Conflict("轮灌状态已被其他操作变更，请刷新后重试")
        if target != current_status and not can_transit(current_status, target):
            raise Conflict(illegal_transition_message(current_status, target))
        mutate(current)
        return current


class GreenhouseViewSet(viewsets.ModelViewSet):
    queryset = Greenhouse.objects.annotate(zone_count=Count("zones")).all()
    serializer_class = GreenhouseSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        qs = Zone.objects.select_related("greenhouse").all()
        greenhouse_id = self.request.query_params.get("greenhouseId")
        status = self.request.query_params.get("status")
        if greenhouse_id:
            qs = qs.filter(greenhouse_id=greenhouse_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class ClimateLogViewSet(viewsets.ModelViewSet):
    serializer_class = ClimateLogSerializer

    def get_queryset(self):
        qs = ClimateLog.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        return qs


class IrrigationCycleViewSet(viewsets.ModelViewSet):
    serializer_class = IrrigationCycleSerializer

    def get_queryset(self):
        # 纯只读查询：不对数据做任何断言。哪怕历史数据存在多条 running，
        # 列表接口也必须照常返回，不能因为状态异常而整体 500。
        qs = IrrigationCycle.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        status = self.request.query_params.get("status")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def perform_update(self, serializer):
        stale = serializer.instance
        validated = serializer.validated_data
        if "status" not in validated:
            serializer.save()
            return
        target = validated["status"]

        def mutate(locked):
            # 绑定到锁内读出的最新行后再保存
            serializer.instance = locked
            serializer.save()

        save_with_status_guard(stale.pk, stale.status, target, mutate)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    data = {
        "greenhouseCount": Greenhouse.objects.count(),
        "growingZoneCount": Zone.objects.filter(status=Zone.STATUS_GROWING).count(),
        "climateLogLast24h": ClimateLog.objects.filter(
            recorded_at__gte=since_24h
        ).count(),
        "irrigationScheduledToday": IrrigationCycle.objects.filter(
            status=IrrigationCycle.STATUS_SCHEDULED,
            start_at__gte=today_start,
            start_at__lt=today_end,
        ).count(),
    }
    return Response(data)
