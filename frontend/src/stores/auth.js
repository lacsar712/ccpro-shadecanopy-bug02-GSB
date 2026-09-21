import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('sc_access') || '')
  const refreshToken = ref(localStorage.getItem('sc_refresh') || '')
  const user = ref(null)

  const isAuthenticated = computed(() => !!accessToken.value)

  function setTokens(access, refresh) {
    accessToken.value = access || ''
    if (refresh !== undefined) refreshToken.value = refresh || ''
    if (accessToken.value) localStorage.setItem('sc_access', accessToken.value)
    else localStorage.removeItem('sc_access')
    if (refreshToken.value) localStorage.setItem('sc_refresh', refreshToken.value)
    else localStorage.removeItem('sc_refresh')
  }

  async function login(username, password) {
    const { data } = await api.post('/auth/token/', { username, password })
    setTokens(data.access, data.refresh)
    await fetchMe()
  }

  async function fetchMe() {
    if (!accessToken.value) return null
    const { data } = await api.get('/auth/me/')
    user.value = data
    return data
  }

  function logout() {
    setTokens('', '')
    user.value = null
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    setTokens,
    login,
    fetchMe,
    logout,
  }
})
