import { useCallback, useEffect, useState } from 'react'

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function DraftCard({ draft }) {
  const email = draft.email
  return (
    <article className="card">
      <section className="pane">
        <h3>Customer email</h3>
        <p className="meta">
          <strong>{email.from_name || email.from_address}</strong>
          {email.from_name && <span> &lt;{email.from_address}&gt;</span>}
        </p>
        <p className="meta">
          {email.subject || '(no subject)'} · {formatDate(email.received_at)}
        </p>
        <pre className="text">{email.body}</pre>
      </section>

      <section className="pane">
        <h3>Draft reply</h3>
        <p className="meta">Written {formatDate(draft.created_at)}</p>
        <pre className="text">{draft.body}</pre>
      </section>
    </article>
  )
}

export default function App() {
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Ask the backend for the pending drafts and store the result.
  const loadDrafts = useCallback(async () => {
    try {
      const response = await fetch('/api/drafts')
      if (!response.ok) throw new Error(`The backend answered with status ${response.status}.`)
      setDrafts(await response.json())
      setError(null)
    } catch (problem) {
      setError(problem.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Load once when the page opens.
  useEffect(() => {
    loadDrafts()
  }, [loadDrafts])

  function refresh() {
    setLoading(true)
    loadDrafts()
  }

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>Drafts to review</h1>
          <p className="subtitle">
            {loading ? 'Loading…' : `${drafts.length} waiting`}
          </p>
        </div>
        <button onClick={refresh} disabled={loading}>
          Refresh
        </button>
      </header>

      {error && (
        <p className="notice error">
          Could not load drafts. Is the backend running? ({error})
        </p>
      )}

      {!loading && !error && drafts.length === 0 && (
        <p className="notice">Nothing to review right now.</p>
      )}

      {drafts.map((draft) => (
        <DraftCard key={draft.id} draft={draft} />
      ))}
    </main>
  )
}
