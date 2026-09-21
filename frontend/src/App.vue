<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isLogin = computed(() => route.name === 'login')

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div v-if="isLogin">
    <router-view />
  </div>
  <div v-else class="layout">
    <aside class="sidebar">
      <div class="brand">
        ShadeCanopy
        <small>分区气候日志 · 轮灌计划</small>
      </div>
      <nav class="nav">
        <router-link to="/">总览看板</router-link>
        <router-link to="/greenhouses">温室管理</router-link>
        <router-link to="/zones">分区管理</router-link>
        <router-link to="/climate-logs">气候日志</router-link>
        <router-link to="/irrigation">轮灌计划</router-link>
      </nav>
      <div class="sidebar-foot">
        <div>{{ auth.user?.username }} · {{ auth.user?.role }}</div>
        <button class="btn ghost" style="margin-top: 10px; color: #fff; border-color: rgba(255,255,255,.25)" @click="logout">
          退出登录
        </button>
      </div>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>
