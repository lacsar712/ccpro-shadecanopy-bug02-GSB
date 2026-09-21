<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('grower')
const password = ref('123456')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.replace(route.query.redirect || '/')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1>ShadeCanopy</h1>
      <p>温室分区气候日志与轮灌计划</p>
      <div class="form-grid">
        <label>
          用户名
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          密码
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top: 16px">
        <button class="btn" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '进入棚区' }}
        </button>
      </div>
      <p class="hint">演示账号：admin / 123456 · grower / 123456</p>
    </form>
  </div>
</template>
