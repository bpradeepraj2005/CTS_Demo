import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  FileText,
  Send,
} from 'lucide-react'
import {
  Link,
  useNavigate,
  useParams,
} from 'react-router-dom'

import { api } from '../lib/api'

import {
  Alert,
  Card,
  Empty,
  Field,
  Spinner,
  Status,
  fmtDate,
  pct,
} from '../components/ui'

import {
  AppealForecast,
  AttributionRail,
  DecisionLedger,
} from '../components/Explain'

const FILTERS = [
  ['', 'All requests'],
  ['AUTO_APPROVED', 'Auto-approved'],
  ['AUTO_DENIED', 'Auto-denied'],
  ['PENDING_REVIEW', 'In review'],
  ['APPROVED', 'Approved'],
  ['DENIED', 'Denied'],
  ['APPEALED', 'Appealed'],
]

export function RequestList() {
  const navigate = useNavigate()

  const [rows, setRows] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    setRows(null)

    const query = filter
      ? `?status_filter=${encodeURIComponent(filter)}`
      : ''

    api
      .get(`/api/requests${query}`)
      .then(setRows)
      .catch((e) => {
        setError(e.message)
        setRows([])
      })
  }, [filter])

  if (!rows) {
    return <Spinner label="Loading requests" />
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">Hospital management</div>
          <h1 className="mt-1 text-2xl font-semibold">
            Authorization requests
          </h1>
          <p className="mt-1.5 text-[13px] text-ink-2">
            Every submitted case, its decision source and the scores that
            supported the outcome.
          </p>
        </div>

        <Link
          to="/hospital/new"
          className="btn bg-provider text-white border-provider hover:bg-provider-deep"
        >
          New request
        </Link>
      </div>

      {error && <Alert>{error}</Alert>}

      <div className="flex flex-wrap gap-1">
        {FILTERS.map(([value, label]) => (
          <button
            key={value}
            onClick={() => setFilter(value)}
            className={`btn ${
              filter === value
                ? 'btn-dark'
                : 'btn-ghost'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <Card bodyClass="p-0">
          <Empty
            icon={FileText}
            title="No requests found"
          >
            Submit a prior-authorization packet to populate this list.
          </Empty>
        </Card>
      ) : (
        <Card
          bodyClass="p-0"
          title={`${rows.length} request${rows.length === 1 ? '' : 's'}`}
        >
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Case</th>
                  <th className="th">Diagnosis / therapy</th>
                  <th className="th">Status</th>
                  <th className="th text-right">Policy fit</th>
                  <th className="th text-right">Necessity</th>
                  <th className="th text-right">Appeal risk</th>
                  <th className="th text-right">Submitted</th>
                </tr>
              </thead>

              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.id}
                    className="row-link"
                    onClick={() =>
                      navigate(`/hospital/requests/${r.id}`)
                    }
                  >
                    <td className="td">
                      <div className="num text-2xs">
                        {r.case_number}
                      </div>
                      <div className="mt-1 text-2xs text-ink-3">
                        {r.provider_specialty}
                      </div>
                    </td>

                    <td className="td">
                      <div className="font-medium">
                        {r.diagnosis}
                      </div>
                      <div className="text-2xs text-ink-3">
                        {r.requested_treatment} ·{' '}
                        {r.disease_severity}
                      </div>
                    </td>

                    <td className="td">
                      <Status value={r.status} />
                    </td>

                    <td className="td num text-right">
                      {r.policy_fit_score?.toFixed(3) ?? '—'}
                    </td>

                    <td className="td num text-right">
                      {pct(r.necessity_score)}
                    </td>

                    <td className="td num text-right">
                      {pct(r.appeal_probability)}
                    </td>

                    <td className="td text-right text-2xs text-ink-3">
                      {fmtDate(r.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

export function RequestDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [data, setData] = useState(null)
  const [audit, setAudit] = useState([])
  const [error, setError] = useState(null)

  const [appeal, setAppeal] = useState({
    rationale: '',
    new_documentation: false,
  })

  const [appealing, setAppealing] = useState(false)

  const load = () => {
    api
      .get(`/api/requests/${id}`)
      .then(setData)
      .catch((e) => setError(e.message))

    api
      .get(`/api/requests/${id}/audit`)
      .then(setAudit)
      .catch(() => setAudit([]))
  }

  useEffect(() => {
    load()
  }, [id])

  if (error && !data) {
    return <Alert>{error}</Alert>
  }

  if (!data) {
    return <Spinner label="Loading authorization case" />
  }

  const canAppeal =
    data.decision === 'DENIED' &&
    !(data.appeals || []).some(
      (a) => a.status === 'OPEN',
    )

  const submitAppeal = async () => {
    setAppealing(true)
    setError(null)

    try {
      await api.post(
        `/api/requests/${id}/appeal`,
        appeal,
      )

      setAppeal({
        rationale: '',
        new_documentation: false,
      })

      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setAppealing(false)
    }
  }

  return (
    <div className="space-y-5">
      <Link
        to="/hospital/requests"
        className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink"
      >
        <ArrowLeft size={13} />
        Requests
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="num text-2xs text-ink-3">
              {data.case_number}
            </span>

            <Status value={data.status} />
          </div>

          <h1 className="mt-2 text-2xl font-semibold">
            {data.diagnosis}
          </h1>

          <p className="mt-1 text-[13px] text-ink-2">
            {data.requested_treatment} ·{' '}
            {data.features?.dose_category} ·{' '}
            {data.features?.frequency} ·{' '}
            {data.features?.route}
          </p>
        </div>

        <div className="grid grid-cols-3 gap-5">
          <Metric
            label="Policy fit"
            value={
              data.policy_fit_score?.toFixed(3) ?? '—'
            }
          />

          <Metric
            label="Necessity"
            value={pct(data.necessity_score)}
          />

          <Metric
            label="Processing"
            value={
              data.processing_ms != null
                ? `${data.processing_ms} ms`
                : '—'
            }
          />
        </div>
      </div>

      {data.criteria?.rationale && (
        <Alert
          tone={
            data.decision === 'APPROVED'
              ? 'approve'
              : data.decision === 'DENIED'
                ? 'deny'
                : 'review'
          }
        >
          {data.criteria.rationale}
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <DecisionLedger
          criteria={data.criteria?.criteria}
          rationale={data.criteria?.rationale}
          necessityScore={data.necessity_score}
        />

        <AttributionRail
          explanation={data.explanation}
        />
      </div>

      <AppealForecast
        prediction={data.appeal_prediction}
      />

      <Card
        eyebrow="Clinical documentation"
        title="Uploaded documents"
      >
        {data.documents?.length ? (
          <div className="space-y-2">
            {data.documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 rounded-md border border-rule bg-canvas px-3 py-3"
              >
                <FileText
                  size={16}
                  className="text-provider"
                />

                <div>
                  <div className="text-[13px] font-medium">
                    {doc.filename}
                  </div>

                  <div className="text-2xs text-ink-3">
                    {doc.page_count} pages ·{' '}
                    {(doc.extraction_confidence * 100).toFixed(1)}%
                    extraction confidence
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-ink-3">
            No document attached.
          </p>
        )}
      </Card>

      {canAppeal && (
        <Card
          eyebrow="Appeal"
          title="Challenge this denial"
        >
          {error && (
            <div className="mb-4">
              <Alert>{error}</Alert>
            </div>
          )}

          <Field
            label="Appeal rationale"
            hint="Provide at least 10 characters. This becomes part of the audit record."
          >
            <textarea
              className="input"
              rows={5}
              value={appeal.rationale}
              placeholder="Explain why the denial should be reconsidered."
              onChange={(e) =>
                setAppeal({
                  ...appeal,
                  rationale: e.target.value,
                })
              }
            />
          </Field>

          <label className="mt-4 flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={appeal.new_documentation}
              onChange={(e) =>
                setAppeal({
                  ...appeal,
                  new_documentation: e.target.checked,
                })
              }
            />

            <span className="text-[13px]">
              New clinical documentation is being submitted
            </span>
          </label>

          <button
            onClick={submitAppeal}
            disabled={
              appealing ||
              appeal.rationale.trim().length < 10
            }
            className="btn mt-4 bg-provider text-white border-provider hover:bg-provider-deep"
          >
            <Send size={14} />
            {appealing
              ? 'Filing appeal…'
              : 'File appeal'}
          </button>
        </Card>
      )}

      {data.appeals?.length > 0 && (
        <Card
          eyebrow="Appeal history"
          title="Appeals on this case"
        >
          <div className="space-y-3">
            {data.appeals.map((a) => (
              <div
                key={a.id}
                className="rounded-md border border-rule bg-canvas p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <Status value={a.status} />

                  <span className="text-2xs text-ink-3">
                    {fmtDate(a.created_at)}
                  </span>
                </div>

                <p className="mt-2 text-[13px] text-ink-2">
                  {a.rationale}
                </p>

                {a.outcome_notes && (
                  <p className="mt-2 text-[13px]">
                    <strong>Outcome:</strong>{' '}
                    {a.outcome_notes}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card
        eyebrow="Audit trail"
        title="Case history"
      >
        {audit.length === 0 ? (
          <p className="text-[13px] text-ink-3">
            No audit events recorded.
          </p>
        ) : (
          <div className="divide-y divide-rule">
            {audit.map((event) => (
              <div
                key={event.id}
                className="py-3 first:pt-0 last:pb-0"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-2xs font-medium">
                    {event.action}
                  </span>

                  <span className="text-2xs text-ink-3">
                    {fmtDate(event.created_at)}
                  </span>
                </div>

                <div className="mt-1 text-2xs text-ink-3">
                  {event.actor_email || 'System'}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div className="text-right">
      <div className="eyebrow mb-1">
        {label}
      </div>

      <div className="num text-lg font-semibold">
        {value}
      </div>
    </div>
  )
}
export function SubmittedValues({ request }) {
  if (!request) {
    return null
  }

  const values = [
    ["Patient", request.patient_name || request.patientName],
    ["Diagnosis", request.diagnosis],
    ["Medication / Procedure", request.medication || request.procedure],
    ["Payer", request.payer_name || request.payerName],
    ["Member ID", request.member_id || request.memberId],
    ["Provider", request.provider_name || request.providerName],
    ["Status", request.status],
    ["Policy Fit Score", request.policy_fit_score],
  ]

  return (
    <div className="card">
      <div className="card-header">
        <h3>Submitted Values</h3>
      </div>

      <div className="card-body">
        <div className="grid">
          {values.map(([label, value]) => (
            <div key={label} className="field">
              <div className="field-label">{label}</div>
              <div className="field-value">
                {value !== undefined && value !== null && value !== ""
                  ? String(value)
                  : "—"}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


export function AuditTrail({ request }) {
  if (!request) {
    return null
  }

  const audit =
    request.audit_trail ||
    request.auditTrail ||
    request.audit ||
    []

  if (!Array.isArray(audit) || audit.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <h3>Audit Trail</h3>
        </div>

        <div className="card-body">
          <p>No audit events available.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3>Audit Trail</h3>
      </div>

      <div className="card-body">
        <div className="audit-list">
          {audit.map((event, index) => (
            <div className="audit-item" key={event.id || index}>
              <div className="audit-content">
                <strong>
                  {event.action ||
                    event.event ||
                    event.type ||
                    "Request event"}
                </strong>

                {event.description && (
                  <div>{event.description}</div>
                )}

                {event.message && (
                  <div>{event.message}</div>
                )}

                <small>
                  {event.timestamp ||
                    event.created_at ||
                    event.createdAt ||
                    ""}
                </small>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}