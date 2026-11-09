import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { Shell } from './components/Shell'
import { SessionProvider, useSession } from './lib/session'
import Actions from './pages/Actions'
import DecisionIntelligence from './pages/DecisionIntelligence'
import Insights from './pages/Insights'
import Merchant360 from './pages/Merchant360'
import Overview from './pages/Overview'
import Portfolio from './pages/Portfolio'
import Queue from './pages/Queue'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import Studio from './pages/Studio'
import UploadWizard from './pages/UploadWizard'
import Welcome from './pages/Welcome'

function MerchantIndex() {
  const { merchants, s } = useSession()
  const first = [...merchants].sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999) || a.risk_rank - b.risk_rank)[0]
  return <Navigate to={`/a/${s.id}/merchant/${first?.id ?? ''}`} replace />
}

function Scoped() {
  const { sid } = useParams()
  return <SessionProvider sid={sid!}><Shell /></SessionProvider>
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Welcome />} />
      <Route path="/new" element={<UploadWizard />} />
      <Route path="/a/:sid" element={<Scoped />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="intelligence" element={<DecisionIntelligence />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="queue" element={<Queue />} />
        <Route path="merchant" element={<MerchantIndex />} />
        <Route path="merchant/:mid" element={<Merchant360 />} />
        <Route path="studio" element={<Studio />} />
        <Route path="actions" element={<Actions />} />
        <Route path="insights" element={<Insights />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
