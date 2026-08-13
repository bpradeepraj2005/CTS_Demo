import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import {
  FileUp, Gavel, LayoutDashboard, ListChecks, ScrollText, Users,
} from 'lucide-react'
import { AuthProvider, RequireRole } from './lib/auth'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import { SignIn, SignUpPayer, SignUpProvider } from './pages/Auth'
import ProviderDashboard from './pages/ProviderDashboard'
import NewRequest from './pages/NewRequest'
import { RequestDetail, RequestList } from './pages/Requests'
import PayerDashboard from './pages/PayerDashboard'
import { Appeals, ReviewCase, ReviewQueue, Reviewers } from './pages/Review'
import ModelCard from './pages/ModelCard'

const PROVIDER_NAV = [
  { to: '/hospital', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/hospital/new', label: 'New request', icon: FileUp },
  { to: '/hospital/requests', label: 'Requests', icon: ListChecks },
  { to: '/hospital/models', label: 'Model card', icon: ScrollText },
]

const PAYER_NAV = [
  { to: '/payer', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/payer/queue', label: 'Review queue', icon: ListChecks },
  { to: '/payer/appeals', label: 'Appeals', icon: Gavel },
  { to: '/payer/reviewers', label: 'Reviewers', icon: Users },
  { to: '/payer/models', label: 'Model card', icon: ScrollText },
]

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Landing />} />

          <Route path="/hospital/signin" element={<SignIn portal="provider" />} />
          <Route path="/hospital/signup" element={<SignUpProvider />} />
          <Route path="/payer/signin" element={<SignIn portal="payer" />} />
          <Route path="/payer/signup" element={<SignUpPayer />} />

          <Route
            path="/hospital"
            element={
              <RequireRole role="PROVIDER_STAFF">
                <Layout portal="provider" nav={PROVIDER_NAV} />
              </RequireRole>
            }
          >
            <Route index element={<ProviderDashboard />} />
            <Route path="new" element={<NewRequest />} />
            <Route path="requests" element={<RequestList />} />
            <Route path="requests/:id" element={<RequestDetail />} />
            <Route path="models" element={<ModelCard />} />
          </Route>

          <Route
            path="/payer"
            element={
              <RequireRole role="PAYER_REVIEWER">
                <Layout portal="payer" nav={PAYER_NAV} />
              </RequireRole>
            }
          >
            <Route index element={<PayerDashboard />} />
            <Route path="queue" element={<ReviewQueue />} />
            <Route path="cases/:id" element={<ReviewCase />} />
            <Route path="appeals" element={<Appeals />} />
            <Route path="reviewers" element={<Reviewers />} />
            <Route path="models" element={<ModelCard />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  )
}