import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { Inbox } from 'lucide-react'
import { api } from '../lib/api'
import { Card, Empty, Kpi, Meter, Spinner, pct } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#94A3B8', fontFamily: 'JetBrains Mono' }
const tooltipStyle = {
  fontSize: 12, borderRadius: 6, border: '1px solid #E2E8F0',
  boxShadow: '0 8px 24px -8px rgba(15,23,42,0.18)', fontFamily: 'Inter',
}
const URGENCY_COLORS = ['#B91C1C', '#B45309', '#0369A1', '#94A3B8']

export default function PayerDashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/api/dashboard/payer').then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <Card><p className="text-deny">{error}</p></Card>
  if (!data) return <Spinner label="Loading review activity" />

  if (data.empty) {
    return (
      <Card bodyClass="p-0">
        <Empty icon={Inbox} title="No cases have been submitted yet">
          This dashboard aggregates live case data. Once a hospital account files a
          request, the queue, routing and override figures populate from it.
        </Empty>
      </Card>
    )
  }

  const k = data.kpis
  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <div className="eyebrow">Insurance organization</div>
          <h1 className="mt-1 text-2xl font-semibold">Review operations</h1>
        </div>
        <Link to="/payer/queue" className="btn bg-payer text-white border-payer hover:bg-payer-deep">
          Open my queue ({k.my_queue})
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Cases received" value={k.total_requests} />
        <Kpi
          label="Cleared without a human" value={k.instant_decision_rate} unit="%"
          tone="payer" sub={`${k.under_5s_rate}% decided under 5 s`}
        />
        <Kpi label="Waiting on a reviewer" value={k.pending_review} tone="review"
          sub={`${k.unassigned} unassigned`} />
        <Kpi label="In my queue" value={k.my_queue} tone="payer" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Auto-reassigned" value={k.auto_reassigned}
          sub="First-choice reviewer was unavailable or full"
        />
        <Kpi
          label="Reviewer override rate" value={k.reviewer_override_rate} unit="%"
          sub="Decisions against the engine's leaning"
        />
        <Kpi label="Open appeals" value={k.open_appeals} tone="review"
          sub={`${k.appeal_overturn_rate}% of appeals overturned`} />
        <Kpi
          label="Reviewers taking cases" value={k.active_reviewers}
          unit={`/ ${k.total_reviewers}`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Case volume and outcomes" eyebrow="Last 14 days" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={data.trend} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="date" tick={AXIS} tickLine={false}
                axisLine={{ stroke: '#E2E8F0' }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="submitted" stroke="#4338CA" strokeWidth={2} dot={false} name="Received" />
              <Line type="monotone" dataKey="approved" stroke="#15803D" strokeWidth={2} dot={false} name="Approved" />
              <Line type="monotone" dataKey="denied" stroke="#B91C1C" strokeWidth={2} dot={false} name="Denied" />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Queue by clinical urgency" eyebrow="Pending cases">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={data.urgency_bands} layout="vertical"
              margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="#E2E8F0" horizontal={false} />
              <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="band" width={110}
                tick={{ fontSize: 11, fill: '#475569' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#F7F8FA' }} />
              <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={18}>
                {data.urgency_bands.map((b, i) => (
                  <Cell key={b.band} fill={URGENCY_COLORS[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Reviewer load" eyebrow="Live utilization" bodyClass="p-0">
          {data.reviewer_load.length === 0 ? (
            <p className="px-4 py-10 text-center text-[13px] text-ink-3">
              No reviewers registered.
            </p>
          ) : (
            <div className="divide-y divide-rule">
              {data.reviewer_load.map((r) => (
                <div key={r.name} className="px-4 py-3">
                  <div className="mb-1.5 flex items-baseline justify-between gap-3">
                    <div className="min-w-0">
                      <span className="text-[13px] font-medium">{r.name}</span>
                      <span className="ml-2 text-2xs text-ink-3">{r.specialty}</span>
                    </div>
                    <span className="num shrink-0 text-2xs text-ink-3">
                      {r.open_cases} / {r.daily_capacity}
                    </span>
                  </div>
                  <Meter
                    value={r.open_cases} max={r.daily_capacity}
                    tone={!r.is_available ? 'review' : r.utilization > 80 ? 'deny' : 'payer'}
                  />
                  {!r.is_available && (
                    <p className="mt-1 text-2xs text-review">Paused — not receiving new cases</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Most common denial drivers" eyebrow="Failed criteria">
          {data.top_denial_reasons.length === 0 ? (
            <p className="py-10 text-center text-[13px] text-ink-3">No denials yet.</p>
          ) : (
            <div className="space-y-3">
              {data.top_denial_reasons.map((r) => (
                <div key={r.code}>
                  <div className="mb-1 flex items-baseline justify-between gap-3">
                    <span className="truncate text-[13px]">{r.label}</span>
                    <span className="num text-2xs text-ink-3">{r.count}</span>
                  </div>
                  <Meter value={r.count} max={data.top_denial_reasons[0].count} tone="deny" />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}