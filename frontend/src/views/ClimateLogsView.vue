<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const zones = ref([])
const error = ref('')
const editingId = ref(null)
const filterZoneId = ref('')

function localInputValue(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const form = reactive({
  zoneId: '',
  recordedAt: localInputValue(),
  tempC: 24,
  humidityPct: 65,
  parUmol: 300,
  co2Ppm: 600,
})

function resetForm() {
  editingId.value = null
  form.zoneId = zones.value[0]?.id || ''
  form.recordedAt = localInputValue()
  form.tempC = 24
  form.humidityPct = 65
  form.parUmol = 300
  form.co2Ppm = 600
}

async function loadZones() {
  const { data } = await api.get('/zones/')
  zones.value = data.results || data
  if (!form.zoneId && zones.value.length) form.zoneId = zones.value[0].id
}

async function load() {
  error.value = ''
  try {
    const params = {}
    if (filterZoneId.value) params.zoneId = filterZoneId.value
    const { data } = await api.get('/climate-logs/', { params })
    list.value = data.results || data
  } catch {
    error.value = '加载气候日志失败'
  }
}

function edit(row) {
  editingId.value = row.id
  form.zoneId = row.zoneId
  form.recordedAt = localInputValue(new Date(row.recordedAt))
  form.tempC = Number(row.tempC)
  form.humidityPct = Number(row.humidityPct)
  form.parUmol = Number(row.parUmol)
  form.co2Ppm = Number(row.co2Ppm)
}

async function save() {
  error.value = ''
  if (form.humidityPct < 20 || form.humidityPct > 100) {
    error.value = '湿度 humidityPct 须在 20～100'
    return
  }
  const payload = {
    zoneId: Number(form.zoneId),
    recordedAt: new Date(form.recordedAt).toISOString(),
    tempC: form.tempC,
    humidityPct: form.humidityPct,
    parUmol: form.parUmol,
    co2Ppm: form.co2Ppm,
  }
  try {
    if (editingId.value) {
      await api.put(`/climate-logs/${editingId.value}/`, payload)
    } else {
      await api.post('/climate-logs/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || '保存失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该气候日志？')) return
  await api.delete(`/climate-logs/${id}/`)
  await load()
}

onMounted(async () => {
  await loadZones()
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>气候日志</h1>
        <p>记录温湿度、PAR、CO₂；湿度须 ∈ [20, 100]</p>
      </div>
      <div class="actions">
        <select v-model="filterZoneId" @change="load">
          <option value="">全部分区</option>
          <option v-for="z in zones" :key="z.id" :value="z.id">
            {{ z.greenhouseName }} / {{ z.zoneCode }}
          </option>
        </select>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑日志' : '新建日志' }}</h3>
      <div class="form-grid">
        <label>
          分区
          <select v-model="form.zoneId">
            <option v-for="z in zones" :key="z.id" :value="z.id">
              {{ z.greenhouseName }} / {{ z.zoneCode }}
            </option>
          </select>
        </label>
        <label>记录时间<input v-model="form.recordedAt" type="datetime-local" /></label>
        <label>温度 ℃<input v-model.number="form.tempC" type="number" step="0.01" /></label>
        <label>湿度 %<input v-model.number="form.humidityPct" type="number" step="0.01" min="20" max="100" /></label>
        <label>PAR µmol<input v-model.number="form.parUmol" type="number" step="0.01" /></label>
        <label>CO₂ ppm<input v-model.number="form.co2Ppm" type="number" step="0.01" /></label>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">保存</button>
        <button v-if="editingId" class="btn ghost" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>温室/分区</th>
            <th>温度</th>
            <th>湿度</th>
            <th>PAR</th>
            <th>CO₂</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ new Date(row.recordedAt).toLocaleString() }}</td>
            <td>{{ row.greenhouseName }} / {{ row.zoneCode }}</td>
            <td>{{ row.tempC }}</td>
            <td>{{ row.humidityPct }}</td>
            <td>{{ row.parUmol }}</td>
            <td>{{ row.co2Ppm }}</td>
            <td class="actions">
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
