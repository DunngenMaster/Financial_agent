import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Documents from './pages/Documents'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Documents />} />
        <Route path="*" element={<Documents />} />
      </Route>
    </Routes>
  )
}

export default App