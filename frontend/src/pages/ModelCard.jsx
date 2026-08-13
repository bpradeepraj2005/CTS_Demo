import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { api } from '../lib/api'
import { Card, Meter, Spinner, pct } from '../components/ui'

/* The metrics on this page are read straight from ml/models/metrics.json,
   which the training script writes from a held-out split. Nothing is
   rounded up, relabelled, or presented against a flattering baseline. */
export default function ModelCard() {
  const [data, setData] = useState(null)
  useEffect(() => {
    api.get('/api/dashboard/model-card').then(setData).catch(() => setData({ metrics: {} }))
  }, [])

  if (!data) return <Spinner label="Loading model metrics" />
  const m = data.metrics
  if (!m?.available) {
    return (
      <Card title="No metrics recorded">
        <p className="text-[13px] text-ink-2">
          Train the models first: <code className="num">python ml/train.py --csv your.csv</code>
        </p>
      </Card>
    )
  }

  const pf = m.policy_fit
  const ap = m.appeal_propensity
  const apLift = ap.accuracy - ap.majority_class_baseline
  const apUseful = ap.macro_auc_ovr >= 0.6

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <div className="eyebrow">Transparency</div>
        <h1 className="mt-1 text-2xl font-semibold">Model card</h1>
        <p className="mt-1.5 text-[13px] text-ink-2">
          Held-out performance for the models this platform runs, measured on a 20%
          split of {m.dataset_rows.toLocaleString()} rows from{' '}
          <span className="num">{m.source_csv}</span>.
        </p>
      </div>

      <Card
        eyebrow="Model 1 of 2"
        title="Policy-fit regressor"
        action={
          <span className="chip border-approve-line bg-approve-soft text-approve">
            <CheckCircle2 size={11} /> performing
          </span>
        }
      >
        <p className="text-[13px] text-ink-2">
          Predicts how well a request aligns with payer policy, from the clinical,
          documentation and coverage features. This score carries 25% of the
          necessity weighting and sets the auto-approve and auto-deny thresholds.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Stat label="R² on held-out data" value={pf.r2.toFixed(3)} tone="approve" />
          <Stat label="Mean absolute error" value={pf.mae.toFixed(4)} />
          <Stat label="Target standard deviation" value={pf.target_std.toFixed(4)} />
        </div>
        <p className="mt-4 text-[13px] text-ink-2">
          Typical error is <span className="num">{pf.mae.toFixed(4)}</span> against a
          target that varies by <span className="num">{pf.target_std.toFixed(4)}</span> —
          roughly {Math.round((pf.mae / pf.target_std) * 100)}% of the spread. The model
          explains {pct(pf.r2, 1)} of the variance.
        </p>
      </Card>

      <Card
        eyebrow="Model 2 of 2"
        title="Appeal-propensity classifier"
        action={
          <span className={`chip ${apUseful
            ? 'border-approve-line bg-approve-soft text-approve'
            : 'border-deny-line bg-deny-soft text-deny'}`}>
            <AlertTriangle size={11} /> {apUseful ? 'performing' : 'no usable signal'}
          </span>
        }
      >
        <p className="text-[13px] text-ink-2">
          Predicts whether a denied request will be resubmitted, formally appealed,
          appealed with new evidence, or dropped.
        </p>

        <div className="mt-4 grid gap-4 sm:grid-cols-4">
          <Stat label="Accuracy" value={pct(ap.accuracy, 1)} />
          <Stat label="Majority-class baseline" value={pct(ap.majority_class_baseline, 1)} />
          <Stat
            label="Lift over baseline" value={`${apLift >= 0 ? '+' : ''}${(apLift * 100).toFixed(1)}pp`}
            tone={apLift > 0.05 ? 'approve' : 'deny'}
          />
          <Stat
            label="Macro AUC (one-vs-rest)" value={ap.macro_auc_ovr?.toFixed(3)}
            tone={apUseful ? 'approve' : 'deny'}
          />
        </div>

        <div className="mt-5">
          <div className="mb-2 flex justify-between text-2xs text-ink-3">
            <span>0.500 — random guessing</span>
            <span>1.000 — perfect</span>
          </div>
          <div className="relative">
            <Meter value={ap.macro_auc_ovr} tone={apUseful ? 'approve' : 'deny'} />
            <div className="absolute -top-1 h-3.5 w-px bg-ink" style={{ left: '50%' }} />
          </div>
        </div>

        {!apUseful && (
          <div className="mt-5 rounded-md border border-deny-line bg-deny-soft p-4">
            <h4 className="text-[13px] font-semibold text-deny">
              This model is not usable as-is, and the reason is in the data
            </h4>
            <p className="mt-2 text-[13px] leading-relaxed text-deny">
              A macro AUC of <span className="num">{ap.macro_auc_ovr?.toFixed(3)}</span> is
              a coin flip. Accuracy of <span className="num">{pct(ap.accuracy, 1)}</span>{' '}
              beats the majority-class baseline by only{' '}
              <span className="num">{(apLift * 100).toFixed(1)}</span> percentage points,
              which means the classifier has learned the class proportions rather than
              any relationship between a case and its appeal outcome.
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-deny">
              Reporting a high accuracy on the rarest class would be reporting the class
              imbalance, not model skill. The predictions are still shown in the interface,
              labelled with this caveat, so no reviewer mistakes them for evidence.
            </p>
          </div>
        )}
      </Card>

      <Card eyebrow="Not a model" title="Medical-necessity rules engine">
        <p className="text-[13px] leading-relaxed text-ink-2">
          The approve, deny and route-to-human decision is made by a deterministic,
          weighted rules engine rather than a classifier. Two reasons. First, the
          training corpus contains denied cases only, so an approve/deny boundary
          cannot be learned from it — any classifier trained on it would output one
          class. Second, a decision that affects someone's treatment has to be
          reconstructable criterion by criterion for an audit, which the decision
          ledger on every case provides.
        </p>
        <ul className="mt-3 space-y-1.5">
          {m.notes?.map((n) => (
            <li key={n} className="flex gap-2.5 text-[13px] text-ink-2">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-3" />
              {n}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

function Stat({ label, value, tone = 'ink' }) {
  const tones = { ink: 'text-ink', approve: 'text-approve', deny: 'text-deny' }
  return (
    <div className="rounded-md border border-rule bg-canvas px-3 py-2.5">
      <div className="eyebrow">{label}</div>
      <div className={`num mt-1 text-lg font-semibold leading-none ${tones[tone]}`}>
        {value ?? '—'}
      </div>
    </div>
  )
}