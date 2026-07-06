import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Токен-авторизация (когда включена на бэкенде): любой 401 → страница входа.
const _fetch = window.fetch.bind(window)
window.fetch = async (...args: Parameters<typeof fetch>) => {
  const r = await _fetch(...args)
  if (r.status === 401 && !location.pathname.startsWith('/login')) location.href = '/login'
  return r
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
