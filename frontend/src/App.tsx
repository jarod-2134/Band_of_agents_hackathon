import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/dashboard/Layout'
import { Dashboard } from './components/dashboard/Dashboard'
import { Settings } from './components/dashboard/Settings'
import { Analytics } from './components/dashboard/Analytics'
import { TaskHistory } from './components/dashboard/TaskHistory'

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/history" element={<TaskHistory />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
