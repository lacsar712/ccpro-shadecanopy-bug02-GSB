<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const greenhouses = ref([])
const error = ref('')
const editingId = ref(null)
const filterGreenhouseId = ref('')
const form = reactive({
  greenhouseId: '',
  zoneCode: '',
  cropName: '',
  status: 'idle',
})

const statusLabel = { idle: '空闲', growing: '在种', fallow: '休耕' }

function resetForm() {
  editingId.value = null
  form.greenhouseId = greenhouses.value[0]?.id || ''
  form.zoneCode = ''
  form.cropName = ''
  form.status = 'idle'
}

async function loadGreenhouses() {
  const { data } = await api.get('/greenhouses/')
  greenhouses.value = data.results || data
  if (!form.greenhouseId && greenhouses.value.length) {
    form.greenhouseId = greenhouses.value[0].id
  }
}

async function load() {
  error.value = ''
  try {
    const params = {}
    if (filterGreenhouseId.value) params.greenhouseId = filterGreenhouseId.value
    const { data } = await api.get('/zones/', { params })
    list.value = data.results || data
  } catch {
    error.value = '加载分区失败'
  }
}

function edit(row) {
  editingId.value = row.id
  form.greenhouseId = row.greenhouseId
  form.zoneCode = row.zoneCode
  form.cropName = row.cropName
  form.status = row.status
}

async function save() {
  error.value = ''
  const payload = {
    greenhouseId: Number(form.greenhouseId),
    zoneCode: form.zoneCode,
    cropName: form.cropName,
    status: form.status,
  }
  try {
    if (editingId.value) {
      await api.put(`/zones/${editingId.value}/`, payload)
    } else {
      await api.post('/zones/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || '保存失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该分区？')) return
  await api.delete(`/zones/${id}/`)
  await load()
}

onMounted(async () => {
  await loadGreenhouses()
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>分区管理</h1>
        <p>同温室 zoneCode 唯一；状态 idle / growing / fallow</p>
      </div>
      <div class="actions">
        <select v-model="filterGreenhouseId" @change="load">
          <option value="">全部温室</option>
          <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑分区' : '新建分区' }}</h3>
      <div class="form-grid">
        <label>
          温室
          <select v-model="form.greenhouseId">
            <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </label>
        <label>分区编码<input v-model="form.zoneCode" required /></label>
        <label>作物<input v-model="form.cropName" /></label>
        <label>
          状态
          <select v-model="form.status">
            <option value="idle">空闲</option>
            <option value="growing">在种</option>
            <option value="fallow">休耕</option>
          </select>
        </label>
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
            <th>ID</th>
            <th>温室</th>
            <th>编码</th>
            <th>作物</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.greenhouseName }}</td>
            <td>{{ row.zoneCode }}</td>
            <td>{{ row.cropName || '—' }}</td>
            <td><span class="badge" :class="row.status">{{ statusLabel[row.status] || row.status }}</span></td>
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
