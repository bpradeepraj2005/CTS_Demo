import {
  ArrowRight,
  Building2,
  BrainCircuit,
  FileCheck2,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <div className="min-h-screen overflow-hidden bg-canvas">
      <header className="relative z-10 border-b border-rule bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-6 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-provider text-white shadow-lg shadow-provider/20">
              <ShieldCheck size={21} />
            </div>

            <div>
              <div className="text-sm font-bold tracking-tight text-ink">
                PriorAuth AI
              </div>
              <div className="text-[10px] font-medium uppercase tracking-[.14em] text-ink-3">
                Authorization intelligence
              </div>
            </div>
          </div>

          <div className="hidden items-center gap-3 sm:flex">
            <span className="chip border-approve-line bg-approve-soft text-approve">
              <span className="status-dot bg-approve" />
              Platform online
            </span>
          </div>
        </div>
      </header>

      <main>
        <section className="relative">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_50%_0%,rgba(37,99,235,.13),transparent_48%)]" />

          <div className="mx-auto max-w-[1440px] px-6 pb-14 pt-16 lg:px-10 lg:pb-20 lg:pt-24">
            <div className="mx-auto max-w-4xl text-center">
              <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-provider-line bg-provider-soft px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[.12em] text-provider">
                <Sparkles size={13} />
                AI-powered prior authorization
              </div>

              <h1 className="mt-6 text-4xl font-bold leading-[1.05] tracking-[-.045em] text-ink sm:text-5xl lg:text-7xl">
                Faster authorization.
                <span className="block text-provider">
                  Better clinical decisions.
                </span>
              </h1>

              <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-ink-2 lg:text-lg">
                Extract clinical information from authorization packets,
                evaluate medical necessity, predict appeal risk and route
                complex cases to the right reviewer.
              </p>

              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <div className="chip border-rule bg-white text-ink-2">
                  <FileCheck2 size={12} />
                  PDF extraction
                </div>

                <div className="chip border-rule bg-white text-ink-2">
                  <BrainCircuit size={12} />
                  ML prediction
                </div>

                <div className="chip border-rule bg-white text-ink-2">
                  <Workflow size={12} />
                  Automated routing
                </div>
              </div>
            </div>

            <div className="mt-14 grid gap-5 lg:grid-cols-2">
              <PortalCard
                to="/hospital/signin"
                signupTo="/hospital/signup"
                icon={Building2}
                eyebrow="Hospital portal"
                title="Submit authorizations"
                description="Upload a prior-authorization packet and review extracted patient, treatment and coverage information before submission."
                accent="provider"
                points={[
                  "Automatic PDF field extraction",
                  "Clinical information review",
                  "Instant automated adjudication",
                  "Request and appeal tracking",
                ]}
              />

              <PortalCard
                to="/payer/signin"
                signupTo="/payer/signup"
                icon={ShieldCheck}
                eyebrow="Payer portal"
                title="Review and adjudicate"
                description="Work prioritized cases with explainable scoring, medical necessity criteria and complete audit history."
                accent="payer"
                points={[
                  "Urgency-ranked review queue",
                  "Explainable AI scoring",
                  "Reviewer assignment",
                  "Appeal propensity insights",
                ]}
              />
            </div>
          </div>
        </section>

        <section className="border-t border-rule bg-white">
          <div className="mx-auto grid max-w-[1440px] gap-6 px-6 py-10 sm:grid-cols-3 lg:px-10">
            <Feature
              icon={FileCheck2}
              title="Extract"
              text="Convert PA packet information into structured clinical fields."
            />

            <Feature
              icon={BrainCircuit}
              title="Predict"
              text="Score policy fit and estimate appeal propensity using trained models."
            />

            <Feature
              icon={Workflow}
              title="Adjudicate"
              text="Apply medical necessity rules and route unresolved cases."
            />
          </div>
        </section>
      </main>
    </div>
  );
}

function PortalCard({
  to,
  signupTo,
  icon: Icon,
  eyebrow,
  title,
  description,
  accent,
  points,
}) {
  const provider = accent === "provider";

  const styles = provider
    ? {
        icon: "bg-provider text-white",
        badge: "border-provider-line bg-provider-soft text-provider",
        button:
          "border-provider bg-provider text-white hover:bg-provider-deep",
      }
    : {
        icon: "bg-payer text-white",
        badge: "border-payer-line bg-payer-soft text-payer",
        button: "border-payer bg-payer text-white hover:bg-payer-deep",
      };

  return (
    <section className="group relative overflow-hidden rounded-2xl border border-rule bg-white p-6 shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-elevated lg:p-8">
      <div
        className={`absolute right-0 top-0 h-48 w-48 rounded-full blur-3xl ${
          provider ? "bg-blue-100/60" : "bg-violet-100/60"
        }`}
      />

      <div className="relative">
        <div className="flex items-start justify-between">
          <div className={`grid h-12 w-12 place-items-center rounded-xl shadow-lg ${styles.icon}`}>
            <Icon size={23} />
          </div>

          <span className={`chip ${styles.badge}`}>
            {eyebrow}
          </span>
        </div>

        <h2 className="mt-7 text-2xl font-bold tracking-tight">
          {title}
        </h2>

        <p className="mt-3 max-w-xl text-sm leading-6 text-ink-2">
          {description}
        </p>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {points.map((point) => (
            <div
              key={point}
              className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs font-medium text-ink-2"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  provider ? "bg-provider" : "bg-payer"
                }`}
              />
              {point}
            </div>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <Link to={to} className={`btn ${styles.button}`}>
            Enter portal
            <ArrowRight size={15} />
          </Link>

          <Link
            to={signupTo}
            className="text-sm font-semibold text-ink-2 hover:text-ink"
          >
            Create account
          </Link>
        </div>
      </div>
    </section>
  );
}

function Feature({ icon: Icon, title, text }) {
  return (
    <div className="flex gap-4 rounded-xl p-4">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-slate-100 text-provider">
        <Icon size={18} />
      </div>

      <div>
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-xs leading-5 text-ink-2">
          {text}
        </p>
      </div>
    </div>
  );
}