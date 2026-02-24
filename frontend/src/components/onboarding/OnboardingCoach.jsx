import React, { useMemo, useState } from 'react'

const STORAGE_KEY = 'jarvis-onboarding-v1'

const STEPS = [
  {
    id: 'nav',
    title: 'Navigation',
    body: 'Use the top navigation to switch between trading, AI control, research, and roadmap views.',
  },
  {
    id: 'safety',
    title: 'Safety Gates',
    body: 'Before enabling automation, verify Sentinel status and kill switch readiness in AI Control.',
  },
  {
    id: 'context',
    title: 'Context Engine',
    body: 'Confirm supermemory hooks and consensus availability before running long-lived agents.',
  },
]

function readProgress() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return { dismissed: false, index: 0 }
    const parsed = JSON.parse(raw)
    return {
      dismissed: Boolean(parsed.dismissed),
      index: Number.isFinite(parsed.index) ? Math.max(0, parsed.index) : 0,
    }
  } catch {
    return { dismissed: false, index: 0 }
  }
}

function writeProgress(payload) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Ignore storage failures in constrained environments.
  }
}

export default function OnboardingCoach() {
  const initial = useMemo(() => readProgress(), [])
  const [dismissed, setDismissed] = useState(initial.dismissed)
  const [index, setIndex] = useState(initial.index)

  const step = STEPS[Math.min(index, STEPS.length - 1)]
  const isComplete = index >= STEPS.length - 1

  if (dismissed) {
    return null
  }

  const onDismiss = () => {
    setDismissed(true)
    writeProgress({ dismissed: true, index })
  }

  const onNext = () => {
    if (isComplete) {
      setDismissed(true)
      writeProgress({ dismissed: true, index })
      return
    }
    const nextIndex = index + 1
    setIndex(nextIndex)
    writeProgress({ dismissed: false, index: nextIndex })
  }

  return (
    <section
      className="card"
      style={{
        marginBottom: 'var(--space-lg)',
        borderColor: 'rgba(59, 130, 246, 0.35)',
        background: 'linear-gradient(135deg, rgba(59,130,246,0.12), rgba(16,185,129,0.08))',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
        <div>
          <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1rem' }}>
            Onboarding Coach: {step.title}
          </h3>
          <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            {step.body}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-ghost" onClick={onDismiss} type="button">
            Dismiss
          </button>
          <button className="btn btn-primary" onClick={onNext} type="button">
            {isComplete ? 'Finish' : 'Next'}
          </button>
        </div>
      </div>
    </section>
  )
}
