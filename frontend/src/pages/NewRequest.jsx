import { useState } from 'react'
import { ArrowLeft, FileText, Upload } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../lib/api'
import {
  COMORBIDITIES,
  DIAGNOSES,
  DOSE_CATEGORIES,
  FREQUENCIES,
  PAYERS,
  PROVIDER_TYPES,
  REQUEST_REASONS,
  ROUTES,
  SEVERITIES,
  SPECIALTIES,
  STATES,
  TREATMENTS,
} from '../lib/vocab'

import { Alert, Card, Field, Spinner } from '../components/ui'

const INITIAL = {
  age: '',
  sex: '',
  bmi: '',
  diagnosis: '',
  diagnosis_code: '',
  disease_severity: '',
  symptom_burden_0_10: '',
  symptom_duration_months: '',
  comorbidities: 'Unknown',

  requested_treatment: '',
  dose_category: '',
  frequency: '',
  route: '',
  requested_duration_months: '',
  request_reason: '',

  previous_treatment_count: '0',
  previous_failed_count: '0',
  previous_partial_response_count: '0',
  previous_adverse_effect_count: '0',
  longest_previous_treatment_weeks: '0',

  doctor_note_present: 0,
  lab_results_present: 0,
  imaging_present: 0,
  medication_history_present: 0,
  documentation_complete: 0,

  provider_specialty: '',
  provider_state: '',
  provider_type: '',
  payer: '',

  member_eligible: 1,
  treatment_covered: 1,

  clinical_evidence_score: '',
}

const NUMERIC_FIELDS = [
  'age',
  'bmi',
  'symptom_burden_0_10',
  'symptom_duration_months',
  'requested_duration_months',
  'previous_treatment_count',
  'previous_failed_count',
  'previous_partial_response_count',
  'previous_adverse_effect_count',
  'longest_previous_treatment_weeks',
  'clinical_evidence_score',
]

function normalizeExtracted(fields) {
  const next = {}

  Object.entries(fields || {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') {
      return
    }

    next[key] = value
  })

  return next
}

export default function NewRequest() {
  const navigate = useNavigate()

  const [form, setForm] = useState(INITIAL)
  const [documentId, setDocumentId] = useState(null)
  const [filename, setFilename] = useState('')
  const [extraction, setExtraction] = useState(null)

  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const [error, setError] = useState(null)

  const update = (key, value) => {
    setForm((current) => ({
      ...current,
      [key]: value,
    }))
  }

  const uploadPdf = async (event) => {
    const file = event.target.files?.[0]

    if (!file) return

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF prior-authorization packet.')
      return
    }

    setUploading(true)
    setError(null)
    setExtraction(null)

    try {
      const result = await api.upload(
        '/api/documents/upload',
        file,
      )

      setDocumentId(result.document_id)
      setFilename(result.filename)

      const extracted = normalizeExtracted(result.fields)

      setForm((current) => ({
        ...current,
        ...extracted,
      }))

      setExtraction(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const submit = async (event) => {
    event.preventDefault()

    setSubmitting(true)
    setError(null)

    try {
      const features = {
        ...form,
      }

      for (const field of NUMERIC_FIELDS) {
        if (
          features[field] !== '' &&
          features[field] !== null &&
          features[field] !== undefined
        ) {
          features[field] = Number(features[field])
        }
      }

      for (const field of [
        'doctor_note_present',
        'lab_results_present',
        'imaging_present',
        'medication_history_present',
        'documentation_complete',
        'member_eligible',
        'treatment_covered',
      ]) {
        features[field] = Number(features[field] || 0)
      }

      const result = await api.post('/api/requests', {
        features,
        document_id: documentId,
        patient_name: form.patient_name || null,
        mrn: form.mrn || null,
      })

      navigate(`/hospital/requests/${result.id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const missing =
    extraction?.missing_required || []

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <Link
        to="/hospital"
        className="inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink"
      >
        <ArrowLeft size={13} />
        Hospital dashboard
      </Link>

      <div>
        <div className="eyebrow">Prior authorization</div>
        <h1 className="mt-1 text-2xl font-semibold">
          New authorization request
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-2">
          Upload the PA packet first. The extraction service will populate
          what it can identify; review every field before submitting.
        </p>
      </div>

      {error && (
        <Alert onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card
        eyebrow="Step 1"
        title="Upload the prior-authorization packet"
      >
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-ruleStrong bg-canvas px-6 py-10 text-center hover:bg-surface">
          <Upload size={24} className="text-provider" />

          <div className="mt-3 text-sm font-medium">
            {uploading
              ? 'Extracting clinical information…'
              : 'Choose a PDF packet'}
          </div>

          <div className="mt-1 text-[13px] text-ink-3">
            The backend extracts labelled fields and controlled vocabulary
            matches.
          </div>

          <input
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={uploadPdf}
            disabled={uploading}
          />
        </label>

        {filename && (
          <div className="mt-4 flex items-center gap-2 rounded-md border border-rule bg-canvas px-3 py-2.5">
            <FileText size={15} className="text-provider" />

            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium">
                {filename}
              </div>

              {extraction && (
                <div className="text-2xs text-ink-3">
                  {extraction.page_count} pages ·{' '}
                  {extraction.char_count} characters ·{' '}
                  {(extraction.extraction_confidence * 100).toFixed(1)}%
                  extraction confidence
                </div>
              )}
            </div>
          </div>
        )}

        {missing.length > 0 && (
          <div className="mt-4 rounded-md border border-review-line bg-review-soft px-3 py-2.5 text-[13px] text-review">
            <strong>Fields requiring review:</strong>{' '}
            {missing.join(', ')}
          </div>
        )}
      </Card>

      <form onSubmit={submit} className="space-y-5">
        <Card eyebrow="Step 2" title="Patient and condition">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Age">
              <input
                className="input"
                type="number"
                min="0"
                max="120"
                required
                value={form.age}
                onChange={(e) => update('age', e.target.value)}
              />
            </Field>

            <Field label="Sex">
              <select
                className="input"
                required
                value={form.sex}
                onChange={(e) => update('sex', e.target.value)}
              >
                <option value="">Select</option>
                <option value="F">Female</option>
                <option value="M">Male</option>
              </select>
            </Field>

            <Field label="BMI">
              <input
                className="input"
                type="number"
                min="5"
                max="100"
                step="0.1"
                required
                value={form.bmi}
                onChange={(e) => update('bmi', e.target.value)}
              />
            </Field>

            <Field label="Symptom burden (0–10)">
              <input
                className="input"
                type="number"
                min="0"
                max="10"
                step="0.1"
                required
                value={form.symptom_burden_0_10}
                onChange={(e) =>
                  update('symptom_burden_0_10', e.target.value)
                }
              />
            </Field>

            <Field label="Diagnosis">
              <select
                className="input"
                required
                value={form.diagnosis}
                onChange={(e) => update('diagnosis', e.target.value)}
              >
                <option value="">Select diagnosis</option>
                {DIAGNOSES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Diagnosis code">
              <input
                className="input"
                value={form.diagnosis_code}
                placeholder="Auto-filled from diagnosis"
                onChange={(e) =>
                  update('diagnosis_code', e.target.value)
                }
              />
            </Field>

            <Field label="Disease severity">
              <select
                className="input"
                required
                value={form.disease_severity}
                onChange={(e) =>
                  update('disease_severity', e.target.value)
                }
              >
                <option value="">Select severity</option>
                {SEVERITIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Symptom duration (months)">
              <input
                className="input"
                type="number"
                min="0"
                step="1"
                required
                value={form.symptom_duration_months}
                onChange={(e) =>
                  update('symptom_duration_months', e.target.value)
                }
              />
            </Field>
          </div>

          <div className="mt-4">
            <Field label="Comorbidities">
              <select
                className="input"
                value={form.comorbidities}
                onChange={(e) =>
                  update('comorbidities', e.target.value)
                }
              >
                <option value="Unknown">Unknown</option>
                {COMORBIDITIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Card>

        <Card eyebrow="Step 3" title="Requested therapy">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Requested treatment">
              <select
                className="input"
                required
                value={form.requested_treatment}
                onChange={(e) =>
                  update('requested_treatment', e.target.value)
                }
              >
                <option value="">Select treatment</option>
                {TREATMENTS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Dose category">
              <select
                className="input"
                required
                value={form.dose_category}
                onChange={(e) =>
                  update('dose_category', e.target.value)
                }
              >
                <option value="">Select</option>
                {DOSE_CATEGORIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Frequency">
              <select
                className="input"
                required
                value={form.frequency}
                onChange={(e) =>
                  update('frequency', e.target.value)
                }
              >
                <option value="">Select</option>
                {FREQUENCIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Route">
              <select
                className="input"
                required
                value={form.route}
                onChange={(e) =>
                  update('route', e.target.value)
                }
              >
                <option value="">Select</option>
                {ROUTES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Requested duration (months)">
              <select
                className="input"
                required
                value={form.requested_duration_months}
                onChange={(e) =>
                  update(
                    'requested_duration_months',
                    e.target.value,
                  )
                }
              >
                <option value="">Select</option>
                <option value="3">3 months</option>
                <option value="6">6 months</option>
                <option value="12">12 months</option>
              </select>
            </Field>

            <Field label="Reason for request">
              <select
                className="input"
                required
                value={form.request_reason}
                onChange={(e) =>
                  update('request_reason', e.target.value)
                }
              >
                <option value="">Select reason</option>
                {REQUEST_REASONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Card>

        <Card eyebrow="Step 4" title="Previous treatment history">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <NumberField
              label="Previous treatments"
              value={form.previous_treatment_count}
              onChange={(v) =>
                update('previous_treatment_count', v)
              }
            />

            <NumberField
              label="Failed treatments"
              value={form.previous_failed_count}
              onChange={(v) =>
                update('previous_failed_count', v)
              }
            />

            <NumberField
              label="Partial responses"
              value={form.previous_partial_response_count}
              onChange={(v) =>
                update('previous_partial_response_count', v)
              }
            />

            <NumberField
              label="Adverse effects"
              value={form.previous_adverse_effect_count}
              onChange={(v) =>
                update('previous_adverse_effect_count', v)
              }
            />

            <NumberField
              label="Longest trial (weeks)"
              value={form.longest_previous_treatment_weeks}
              onChange={(v) =>
                update('longest_previous_treatment_weeks', v)
              }
            />
          </div>
        </Card>

        <Card eyebrow="Step 5" title="Documentation and coverage">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <CheckField
              label="Clinical note attached"
              checked={form.doctor_note_present}
              onChange={(v) =>
                update('doctor_note_present', v ? 1 : 0)
              }
            />

            <CheckField
              label="Lab results attached"
              checked={form.lab_results_present}
              onChange={(v) =>
                update('lab_results_present', v ? 1 : 0)
              }
            />

            <CheckField
              label="Imaging attached"
              checked={form.imaging_present}
              onChange={(v) =>
                update('imaging_present', v ? 1 : 0)
              }
            />

            <CheckField
              label="Medication history attached"
              checked={form.medication_history_present}
              onChange={(v) =>
                update('medication_history_present', v ? 1 : 0)
              }
            />

            <CheckField
              label="Member eligible"
              checked={form.member_eligible}
              onChange={(v) =>
                update('member_eligible', v ? 1 : 0)
              }
            />

            <CheckField
              label="Treatment is covered"
              checked={form.treatment_covered}
              onChange={(v) =>
                update('treatment_covered', v ? 1 : 0)
              }
            />
          </div>
        </Card>

        <Card eyebrow="Step 6" title="Provider and payer information">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Provider specialty">
              <select
                className="input"
                required
                value={form.provider_specialty}
                onChange={(e) =>
                  update('provider_specialty', e.target.value)
                }
              >
                <option value="">Select</option>
                {SPECIALTIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Provider state">
              <select
                className="input"
                required
                value={form.provider_state}
                onChange={(e) =>
                  update('provider_state', e.target.value)
                }
              >
                <option value="">Select</option>
                {STATES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Provider type">
              <select
                className="input"
                required
                value={form.provider_type}
                onChange={(e) =>
                  update('provider_type', e.target.value)
                }
              >
                <option value="">Select</option>
                {PROVIDER_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Payer">
              <select
                className="input"
                required
                value={form.payer}
                onChange={(e) =>
                  update('payer', e.target.value)
                }
              >
                <option value="">Select</option>
                {PAYERS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Card>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting || uploading}
            className="btn bg-provider text-white border-provider hover:bg-provider-deep"
          >
            {submitting
              ? 'Processing authorization…'
              : 'Submit for automated adjudication'}
          </button>
        </div>
      </form>
    </div>
  )
}

function NumberField({ label, value, onChange }) {
  return (
    <Field label={label}>
      <input
        className="input"
        type="number"
        min="0"
        step="1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  )
}

function CheckField({ label, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-md border border-rule bg-canvas px-3 py-3">
      <input
        type="checkbox"
        checked={Boolean(checked)}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-sky-700"
      />

      <span className="text-[13px]">
        {label}
      </span>
    </label>
  )
}