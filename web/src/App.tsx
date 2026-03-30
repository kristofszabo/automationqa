import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { ACTION_TYPES, ActionType, Step } from './types'

const ACTION_FIELDS: Record<ActionType, string[]> = {
  navigate: ['url'],
  click:    ['selector'],
  type:     ['selector', 'value'],
  assert:   ['selector', 'expected'],
}

const ACTION_DEFAULTS: Record<ActionType, Omit<Step, 'step' | 'action' | 'timestamp_ms'>> = {
  navigate: { url: '' } as never,
  click:    { selector: '' } as never,
  type:     { selector: '', value: '' } as never,
  assert:   { selector: '', expected: '' } as never,
}

function makeStep(stepNum: number): Step {
  return { step: stepNum, action: 'click', selector: '', timestamp_ms: 0 } as Step
}

export default function App() {
  const [steps, setSteps] = useState<Step[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetch('/api/steps').then(r => r.json()).then(setSteps)
  }, [])

  const scheduleValidate = useCallback((next: Step[]) => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(next),
      })
      const data = await res.json()
      setErrors(data.errors)
    }, 400)
  }, [])

  function updateField(index: number, field: string, value: string | number) {
    const next = steps.map((s, i) => i === index ? { ...s, [field]: value } : s)
    setSteps(next)
    scheduleValidate(next)
  }

  function updateAction(index: number, action: ActionType) {
    const s = steps[index]
    const next = steps.map((step, i) =>
      i === index
        ? { step: s.step, action, timestamp_ms: s.timestamp_ms, ...ACTION_DEFAULTS[action] } as Step
        : step
    )
    setSteps(next)
    scheduleValidate(next)
  }

  function addStep() {
    const next = [...steps, makeStep(steps.length + 1)]
    setSteps(next)
  }

  function deleteStep(index: number) {
    const next = steps.filter((_, i) => i !== index)
    setSteps(next)
    scheduleValidate(next)
  }

  async function handleSave() {
    setSaving(true)
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(steps),
    })
    if (res.ok) {
      setSaved(true)
    } else {
      const data = await res.json()
      setErrors(data.errors)
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <div className="done">
        <h1>Done!</h1>
        <p>Steps saved successfully. You can close this tab.</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <h1>Phase 4 — Step Review</h1>
        <button
          className="btn-save"
          onClick={handleSave}
          disabled={saving || errors.length > 0}
        >
          {saving ? 'Saving...' : 'Save & Continue'}
        </button>
      </header>

      {errors.length > 0 && (
        <div className="errors">
          {errors.map((e, i) => <div key={i}>{e}</div>)}
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Action</th>
            <th>Fields</th>
            <th>timestamp_ms</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {steps.map((step, i) => (
            <tr key={i}>
              <td className="num">{i + 1}</td>
              <td>
                <select
                  value={step.action}
                  onChange={e => updateAction(i, e.target.value as ActionType)}
                >
                  {ACTION_TYPES.map(a => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </td>
              <td>
                <div className="fields">
                  {ACTION_FIELDS[step.action].map(field => (
                    <div className="field-row" key={field}>
                      <span className="field-label">{field}</span>
                      <input
                        className="field-input"
                        value={(step as unknown as Record<string, string>)[field] ?? ''}
                        onChange={e => updateField(i, field, e.target.value)}
                        placeholder={field}
                      />
                    </div>
                  ))}
                </div>
              </td>
              <td>
                <input
                  className="ts-input"
                  type="number"
                  value={step.timestamp_ms}
                  onChange={e => updateField(i, 'timestamp_ms', Number(e.target.value))}
                />
              </td>
              <td>
                <button className="btn-delete" onClick={() => deleteStep(i)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <button className="btn-add" onClick={addStep}>+ Add step</button>
    </div>
  )
}
