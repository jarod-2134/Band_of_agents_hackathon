import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const originalFetch = window.fetch;
window.fetch = async (input, init) => {
  const url = typeof input === 'string' ? input : (input as Request).url;
  
  const isBackend = url.includes('/api/v1/') || url.includes('/orgs/') || url.includes('/api/repos');
  const isAuthPath = url.includes('/api/v1/auth/login') || url.includes('/api/v1/auth/register') || url.includes('/api/v1/auth/token');
  
  if (isBackend && !isAuthPath) {
    const rawStore = localStorage.getItem('agent-store');
    let token = null;
    if (rawStore) {
      try {
        const parsed = JSON.parse(rawStore);
        token = parsed.state?.token;
      } catch (e) {
        console.error("Error reading token from agent-store", e);
      }
    }
    
    if (token) {
      init = init || {};
      const headers = new Headers(init.headers || {});
      headers.set('Authorization', `Bearer ${token}`);
      init.headers = headers;
    }
  }
  
  const response = await originalFetch(input, init);
  if (response.status === 401 && isBackend && !isAuthPath) {
    const rawStore = localStorage.getItem('agent-store');
    if (rawStore) {
      try {
        const parsed = JSON.parse(rawStore);
        if (parsed.state) {
          parsed.state.token = null;
          localStorage.setItem('agent-store', JSON.stringify(parsed));
        }
      } catch (e) {}
    }
    window.location.href = '/login';
  }
  return response;
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
