import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Graph from './pages/Graph'
import Ontology from './pages/Ontology'
import Memories from './pages/Memories'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/ontology" element={<Ontology />} />
        <Route path="/memories" element={<Memories />} />
      </Routes>
    </Layout>
  )
}
