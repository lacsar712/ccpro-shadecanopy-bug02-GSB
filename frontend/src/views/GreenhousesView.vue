<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'

const list = ref([])
const error = ref('')
const editingId = ref(null)
const form = reactive({
  name: '',
  location: '',
  areaM2: 100,
  notes: '',
})

function resetForm() {
  editingId.value = null
  form.name = ''
  form.location = ''
  form.areaM2 = 100
  form.notes = ''
}

async function load() {
  error.value = ''
  try {
    const { data } = await api.get('/greenhouses/')
    list.value = data.results || data
  } catch (e) {
    error.value = '加载温室失败'
  }
}

function edit(row) {
  editingId.value = row.id
  form.name = row.name
  form.location = row.location
  form.areaM2 = Number(row.areaM2)
  form.notes = row.notes || ''
}

async function save() {
  error.value = ''
  const payload = {
    name: form.name,
    location: form.location,
    areaM2: form.areaM2,
    notes: form.notes,
  }
  try {
    if (editingId.value) {
      await api.put(`/greenhouses/${editingId.value}/`, payload)
    } else {
      await api.post('/greenhouses/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || '保存失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该温室？分区及相关记录将一并删除。')) return
  await api.delete(`/greenhouses/${id}/`)
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>温室管理</h1>
        <p>维护温室名称、位置、面积与备注</p>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑温室' : '新建温室' }}</h3>
      <div class="form-grid">
        <label>名称<input v-model="form.name" required /></label>
        <label>位置<input v-model="form.location" /></label>
        <label>面积 (m²)<input v-model.number="form.areaM2" type="number" step="0.01" min="0" /></label>
        <label class="full">备注<textarea v-model="form.notes" rows="2" /></label>
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
            <th>名称</th>
            <th>位置</th>
            <th>面积 m²</th>
            <th>分区数</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.location }}</td>
            <td>{{ row.areaM2 }}</td>
            <td>{{ row.zoneCount }}</td>
            <td>{{ row.notes }}</td>
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
