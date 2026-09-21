<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const stats = ref(null)
const error = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    const { data } = await api.get('/dashboard/')
    stats.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || '加载看板失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>总览看板</h1>
        <p>温室规模、在种分区与近时气候 / 今日轮灌</p>
      </div>
    </div>

    <p v-if="loading">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <div v-else class="stats">
      <div class="stat">
        <div class="label">温室数量</div>
        <div class="value">{{ stats.greenhouseCount }}</div>
      </div>
      <div class="stat">
        <div class="label">在种分区</div>
        <div class="value">{{ stats.growingZoneCount }}</div>
      </div>
      <div class="stat">
        <div class="label">近 24h 气候日志</div>
        <div class="value">{{ stats.climateLogLast24h }}</div>
      </div>
      <div class="stat">
        <div class="label">今日排程轮灌</div>
        <div class="value">{{ stats.irrigationScheduledToday }}</div>
      </div>
    </div>

    <div class="panel" style="margin-top: 18px">
      <h3 style="margin-top:0;color:var(--earth-deep)">业务说明</h3>
      <p style="color:var(--muted);margin:0;line-height:1.7">
        本系统面向温室「分区气候日志与轮灌计划」，不涉及考勤 OA 或库存出入库。
        可在侧栏进入温室、分区、气候与轮灌模块进行 CRUD 操作。
      </p>
    </div>
  </div>
</template>
