from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .irrigation_state import (
    STATUS_LABELS,
    VALID_STATUSES,
    can_transit,
    illegal_transition_detail,
)
from .models import ClimateLog, Greenhouse, IrrigationCycle, Zone
from .serializers import (
    ClimateLogSerializer,
    GreenhouseSerializer,
    IrrigationCycleSerializer,
    ZoneSerializer,
)


class IllegalStatusTransition(APIException):
    """非法轮灌状态迁移 —— HTTP 409，detail 为中文说明。"""

    status_code = status.HTTP_409_CONFLICT
    default_code = "illegal_transition"

    def __init__(self, detail):
        super().__init__(detail)


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
        # 列表只读，不做任何“全局唯一 running”断言：历史脏数据也不能拖垮列表
        qs = IrrigationCycle.objects.select_related("zone", "zone__greenhouse")
        zone_id = self.request.query_params.get("zoneId")
        status_filter = self.request.query_params.get("status")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_update(self, serializer):
        instance = serializer.instance
        new_status = serializer.validated_data.get("status", instance.status)
        status_changes = new_status != instance.status

        # 所有迁移合法性只走 can_transit 这一个判定入口
        if status_changes:
            if new_status not in VALID_STATUSES:
                raise IllegalStatusTransition(f"非法状态迁移：未知状态“{new_status}”")
            if not can_transit(instance.status, new_status):
                raise IllegalStatusTransition(
                    illegal_transition_detail(instance.status, new_status)
                )

        update_kwargs = dict(serializer.validated_data)
        if not update_kwargs:
            return

        with transaction.atomic():
            # 条件更新：以数据库当前 status 为 WHERE 条件。
            # 并发把同一笔 scheduled 推进到 running 时，行锁先到先得，
            # 落败方在对方提交后重新匹配 WHERE 命中 0 行，从而只有一次成功。
            # 状态不变的普通编辑同样受此保护，不会把并发推进后的状态覆盖回去。
            updated = (
                IrrigationCycle.objects.filter(pk=instance.pk, status=instance.status)
                .update(updated_at=timezone.now(), **update_kwargs)
            )
            if updated == 0:
                current_status = (
                    IrrigationCycle.objects.filter(pk=instance.pk)
                    .values_list("status", flat=True)
                    .first()
                )
                if current_status == new_status:
                    label = STATUS_LABELS.get(new_status, new_status)
                    raise IllegalStatusTransition(
                        f"该轮灌已被其他操作推进为「{label}」，请勿重复推进"
                    )
                if current_status is None:
                    raise IllegalStatusTransition("轮灌记录不存在或已被删除")
                if status_changes:
                    raise IllegalStatusTransition(
                        illegal_transition_detail(current_status, new_status)
                    )
                raise IllegalStatusTransition("轮灌记录已被其他操作修改，请刷新后重试")

            instance.refresh_from_db()
            serializer.instance = instance


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
