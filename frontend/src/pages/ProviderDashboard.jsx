import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, FileCheck2, Inbox, Plus, Timer } from 'lucide-react'

import { api } from '../lib/api'
import { Card, Empty, Kpi, Meter, Spinner } from '../components/ui'

export default function ProviderDashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get('/api/dashboard/provider')
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <Card>
        <p className="text-deny">{error}</p>
      </Card>
    )
  }

  if (!data) {
    return <Spinner label="Loading authorization activity" />
  }

  if (data.empty) {
    return (
      <div className="space-y-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="eyebrow">Hospital management</div>
            <h1 className="mt-1 text-2xl font-semibold">
              Authorization operations
            </h1>
            <p className="mt-1.5 text-[13px] text-ink-2">
              Submit a prior-authorization packet and the platform will extract,
              score, adjudicate and route it.
            </p>
          </div>

          <Link
            to="/hospital/new"
            className="btn bg-provider text-white border-provider hover:bg-provider-deep"
          >
            <Plus size={14} />
            New request
          </Link>
        </div>

        <Card bodyClass="p-0">
          <Empty icon={Inbox} title="No authorization requests yet">
            Upload your first PA packet to start the automated
            medical-necessity workflow.
          </Empty>
        </Card>
      </div>
    )
  }

  const k = data.kpis

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">Hospital management</div>
          <h1 className="mt-1 text-2xl font-semibold">
            Authorization operations
          </h1>
          <p className="mt-1.5 text-[13px] text-ink-2">
            Live performance across your prior-authorization requests.
          </p>
        </div>

        <Link
          to="/hospital/new"
          className="btn bg-provider text-white border-provider hover:bg-provider-deep"
        >
          <Plus size={14} />
          New request
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Requests submitted"
          value={k.total_requests}
          tone="provider"
        />

        <Kpi
          label="Instant decision rate"
          value={k.instant_decision_rate}
          unit="%"
          tone="approve"
          sub={`${k.under_5s_rate}% processed under 5 seconds`}
        />

        <Kpi
          label="Approval rate"
          value={k.approval_rate}
          unit="%"
          tone="approve"
        />

        <Kpi
          label="Pending human review"
          value={k.pending_review}
          tone="review"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Denial rate"
          value={k.denial_rate}
          unit="%"
          tone="deny"
        />

        <Kpi
          label="Average processing"
          value={k.avg_processing_ms}
          unit="ms"
          sub="End-to-end adjudication"
        />

        <Kpi
          label="P95 processing"
          value={k.p95_processing_ms}
          unit="ms"
        />

        <Kpi
          label="Documents processed"
          value={k.documents_processed}
          tone="provider"
          sub={`${(k.avg_extraction_confidence * 100).toFixed(1)}% avg extraction confidence`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card
          title="Processing performance"
          eyebrow="Automation"
          className="lg:col-span-2"
        >
          <div className="grid gap-5 sm:grid-cols-3">
            <MetricBlock
              icon={Timer}
              label="Average"
              value={`${k.avg_processing_ms} ms`}
            />

            <MetricBlock
              icon={Activity}
              label="P95"
              value={`${k.p95_processing_ms} ms`}
            />

            <MetricBlock
              icon={FileCheck2}
              label="Under 5 seconds"
              value={`${k.under_5s_rate}%`}
            />
          </div>
        </Card>

        <Card title="Appeal risk" eyebrow="Denied requests">
          <div className="text-3xl font-semibold num">
            {(k.mean_appeal_risk_on_denials * 100).toFixed(1)}%
          </div>

          <p className="mt-1.5 text-[13px] text-ink-2">
            Mean predicted probability that a denied request will be
            challenged.
          </p>

          <div className="mt-4">
            <Meter
              value={k.mean_appeal_risk_on_denials}
              tone="payer"
            />
          </div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card
          title="Top denial reasons"
          eyebrow="Medical-necessity criteria"
        >
          {data.top_denial_reasons.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-ink-3">
              No denial criteria recorded yet.
            </p>
          ) : (
            <div className="space-y-3">
              {data.top_denial_reasons.map((r) => (
                <div key={r.code}>
                  <div className="mb-1 flex justify-between gap-3">
                    <span className="text-[13px]">
                      {r.label}
                    </span>
                    <span className="num text-2xs text-ink-3">
                      {r.count}
                    </span>
                  </div>

                  <Meter
                    value={r.count}
                    max={data.top_denial_reasons[0].count}
                    tone="deny"
                  />
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Requests by specialty" eyebrow="Clinical mix">
          {data.by_specialty.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-ink-3">
              No specialty data yet.
            </p>
          ) : (
            <div className="space-y-3">
              {data.by_specialty.map((r) => (
                <div key={r.name}>
                  <div className="mb-1 flex justify-between gap-3">
                    <span>{r.name}</span>
                    <span className="num text-2xs text-ink-3">
                      {r.count}
                    </span>
                  </div>

                  <Meter
                    value={r.count}
                    max={data.by_specialty[0].count}
                    tone="provider"
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="Recent 14-day activity" eyebrow="Live case trend">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Date</th>
                <th className="th text-right">Submitted</th>
                <th className="th text-right">Approved</th>
                <th className="th text-right">Denied</th>
              </tr>
            </thead>

            <tbody>
              {data.trend.map((r) => (
                <tr key={r.date}>
                  <td className="td num">{r.date}</td>
                  <td className="td num text-right">{r.submitted}</td>
                  <td className="td num text-right text-approve">
                    {r.approved}
                  </td>
                  <td className="td num text-right text-deny">
                    {r.denied}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function MetricBlock({ icon: Icon, label, value }) {
  return (
    <div className="rounded-md border border-rule bg-canvas p-4">
      <Icon size={17} className="text-provider" />
      <div className="eyebrow mt-3">{label}</div>
      <div className="num mt-1 text-lg font-semibold">
        {value}
      </div>
    </div>
  )
}