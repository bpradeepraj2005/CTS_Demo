import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Alert, Field } from '../components/ui'

const THEME = {
  provider: {
    name: 'Hospital management',
    home: '/hospital',
    cta: 'bg-provider text-white border-provider hover:bg-provider-deep',
    link: 'text-provider',
    badge: 'bg-provider-soft text-provider border-provider-line',
  },
  payer: {
    name: 'Insurance organization',
    home: '/payer',
    cta: 'bg-payer text-white border-payer hover:bg-payer-deep',
    link: 'text-payer',
    badge: 'bg-payer-soft text-payer border-payer-line',
  },
}

function Shell({ portal, title, subtitle, children, footer }) {
  const t = THEME[portal]
  return (
    <div className="grid min-h-screen place-items-center px-5 py-12">
      <div className="w-full max-w-[420px]">
        <Link
          to="/"
          className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink"
        >
          <ArrowLeft size={13} /> Choose a different portal
        </Link>

        <div className="card p-7">
          <div className={`chip ${t.badge}`}>{t.name}</div>
          <h1 className="mt-4 text-2xl font-semibold">{title}</h1>
          <p className="mt-1.5 text-[13px] text-ink-2">{subtitle}</p>
          <div className="mt-6 space-y-4">{children}</div>
        </div>

        <p className="mt-5 text-center text-[13px] text-ink-2">{footer}</p>
      </div>
    </div>
  )
}

export function SignIn({ portal }) {
  const t = THEME[portal]
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login({ ...form, portal })
      navigate(t.home, { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell
      portal={portal}
      title="Sign in"
      subtitle="Use the account registered to this portal."
      footer={
        <>
          No account yet?{' '}
          <Link to={`/${portal === 'provider' ? 'hospital' : 'payer'}/signup`} className={`font-medium ${t.link} hover:underline`}>
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
        <Field label="Work email">
          <input
            className="input" type="email" required autoFocus autoComplete="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field label="Password">
          <input
            className="input" type="password" required autoComplete="current-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        <button className={`btn w-full ${t.cta}`} disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </Shell>
  )
}

export function SignUpProvider() {
  const { signupProvider } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    full_name: '', email: '', password: '', organization_name: '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signupProvider(form)
      navigate('/hospital', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell
      portal="provider"
      title="Create a hospital account"
      subtitle="Submit authorization requests and track them to a decision."
      footer={
        <>
          Already registered?{' '}
          <Link to="/hospital/signin" className="font-medium text-provider hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
        <Field label="Full name">
          <input className="input" required autoFocus value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </Field>
        <Field label="Hospital or clinic" hint="Colleagues who enter the same name share a case list.">
          <input className="input" required value={form.organization_name}
            onChange={(e) => setForm({ ...form, organization_name: e.target.value })} />
        </Field>
        <Field label="Work email">
          <input className="input" type="email" required autoComplete="email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Password" hint="At least 8 characters.">
          <input className="input" type="password" required minLength={8} autoComplete="new-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <button className="btn w-full bg-provider text-white border-provider hover:bg-provider-deep" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </Shell>
  )
}

export function SignUpPayer() {
  const { signupPayer } = useAuth()
  const navigate = useNavigate()
  const [specialties, setSpecialties] = useState([])
  const [form, setForm] = useState({
    full_name: '', email: '', password: '', organization_name: '',
    specialty: '', license_number: '', daily_capacity: 12,
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/api/auth/specialties')
      .then((r) => {
        setSpecialties(r.specialties)
        setForm((f) => ({ ...f, specialty: f.specialty || r.specialties[0] }))
      })
      .catch(() => {})
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signupPayer({ ...form, daily_capacity: Number(form.daily_capacity) })
      navigate('/payer', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell
      portal="payer"
      title="Create a reviewer account"
      subtitle="Your specialty and capacity decide which cases route to you."
      footer={
        <>
          Already registered?{' '}
          <Link to="/payer/signin" className="font-medium text-payer hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
        <Field label="Full name">
          <input className="input" required autoFocus value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </Field>
        <Field label="Insurance organization">
          <input className="input" required value={form.organization_name}
            onChange={(e) => setForm({ ...form, organization_name: e.target.value })} />
        </Field>
        <Field label="Review specialty" hint="Cases matching this specialty route to you first.">
          <select className="input" required value={form.specialty}
            onChange={(e) => setForm({ ...form, specialty: e.target.value })}>
            {specialties.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="License number">
            <input className="input" value={form.license_number}
              onChange={(e) => setForm({ ...form, license_number: e.target.value })} />
          </Field>
          <Field label="Cases per day" hint="Routing stops at this number.">
            <input className="input num" type="number" min={1} max={100} required
              value={form.daily_capacity}
              onChange={(e) => setForm({ ...form, daily_capacity: e.target.value })} />
          </Field>
        </div>
        <Field label="Work email">
          <input className="input" type="email" required autoComplete="email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Password" hint="At least 8 characters.">
          <input className="input" type="password" required minLength={8} autoComplete="new-password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <button className="btn w-full bg-payer text-white border-payer hover:bg-payer-deep" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </Shell>
  )
}