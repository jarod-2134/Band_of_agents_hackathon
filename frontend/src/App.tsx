import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/dashboard/Layout'
import { Dashboard } from './components/dashboard/Dashboard'
import { Settings } from './components/dashboard/Settings'
import { Analytics } from './components/dashboard/Analytics'
import { TaskHistory } from './components/dashboard/TaskHistory'

import { Home } from './components/landing/Home'
import { Login } from './components/landing/Login'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />

        {/* Dashboard Routes with Layout */}
        <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
        <Route path="/settings" element={<Layout><Settings /></Layout>} />
        <Route path="/analytics" element={<Layout><Analytics /></Layout>} />
        <Route path="/history" element={<Layout><TaskHistory /></Layout>} />
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
