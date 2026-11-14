import { useCallback, useEffect, useState } from 'react'

// ---------- talking to the backend ----------

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    let reason = `status ${response.status}`
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') reason = data.detail
    } catch {
      // The backend did not send a readable reason; keep the status code.
    }
    const error = new Error(reason)
    error.status = response.status
    throw error
  }
  return response.json()
}

// ---------- small helpers ----------

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function timeNow() {
  return new Date().toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

// ---------- one letter on the desk ----------

function Letter({ draft, number, onDone, onChanged }) {
  const email = draft.email
  const approved = draft.status === 'approved'
  const replyText = approved ? draft.final_body : draft.body

  const [wantsEdit, setWantsEdit] = useState(false)
  const editing = wantsEdit && !approved
  const setEditing = setWantsEdit
  const [text, setText] = useState(draft.body)
  const [confirming, setConfirming] = useState(null) // 'send' | 'reject' | null
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState(null)

  const edited = editing && text.trim() !== draft.body.trim()

  async function run(action) {
    setBusy(true)
    setProblem(null)
    try {
      await action()
    } catch (error) {
      setProblem(error.message)
      onChanged()
    } finally {
      setBusy(false)
      setConfirming(null)
    }
  }

  function send() {
    return run(async () => {
      if (!approved) {
        await api(`/drafts/${draft.id}/approve`, {
          method: 'POST',
          body: JSON.stringify(edited ? { final_body: text } : {}),
        })
      }
      await api(`/drafts/${draft.id}/send`, { method: 'POST' })
      onDone(draft, edited ? 'Sent, with your edits' : 'Sent')
    })
  }

  function reject() {
    return run(async () => {
      await api(`/drafts/${draft.id}/reject`, { method: 'POST' })
      onDone(draft, 'Rejected')
    })
  }

  return (
    <article className="letter">
      <div className="letter-number">No. {String(number).padStart(2, '0')}</div>

      <section className="incoming" aria-label="Customer email">
        <p className="label">Received {formatDate(email.received_at)}</p>
        <dl className="slip">
          <dt>From</dt>
          <dd>
            {email.from_name ? `${email.from_name} ` : ''}
            <span className="address">{email.from_address}</span>
          </dd>
          <dt>Subject</dt>
          <dd>{email.subject || '(no subject)'}</dd>
        </dl>
        <pre className="typed">{email.body}</pre>
      </section>

      <section className="reply" aria-label="Draft reply">
        <span className={`stamp ${approved ? 'stamp-approved' : ''}`}>
          {approved ? 'Approved · not sent' : 'Awaiting review'}
        </span>
        <p className="label">Reply, drafted {formatDate(draft.created_at)}</p>

        {editing ? (
          <textarea
            className="sheet editor"
            aria-label="Edit the reply"
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={Math.max(10, text.split('\n').length + 2)}
            disabled={busy}
          />
        ) : (
          <pre className="sheet">{replyText}</pre>
        )}

        {draft.needs_follow_up && (
          <aside className="memo">
            <p className="memo-title">Follow-up needed</p>
            <p className="memo-text">
              {draft.follow_up_note || 'This reply promises that the team will do something.'}
            </p>
          </aside>
        )}

        {problem && <p className="problem">That did not work: {problem}</p>}

        {confirming === 'send' && (
          <div className="actions">
            <span className="ask">
              Send this to <strong>{email.from_address}</strong>?
            </span>
            <button className="primary" onClick={send} disabled={busy}>
              {busy ? 'Sending…' : 'Yes, send'}
            </button>
            <button onClick={() => setConfirming(null)} disabled={busy}>
              Not yet
            </button>
          </div>
        )}

        {confirming === 'reject' && (
          <div className="actions">
            <span className="ask">Reject this draft? It will never be sent.</span>
            <button className="danger" onClick={reject} disabled={busy}>
              {busy ? 'Rejecting…' : 'Yes, reject'}
            </button>
            <button onClick={() => setConfirming(null)} disabled={busy}>
              Keep it
            </button>
          </div>
        )}

        {confirming === null && (
          <div className="actions">
            <button
              className="primary"
              onClick={() => setConfirming('send')}
              disabled={busy || (editing && !text.trim())}
            >
              {approved ? 'Send' : edited ? 'Approve edits & send' : 'Approve & send'}
            </button>
            {!approved && !editing && <button onClick={() => setEditing(true)}>Edit</button>}
            {editing && (
              <button
                onClick={() => {
                  setEditing(false)
                  setText(draft.body)
                }}
              >
                Discard edits
              </button>
            )}
            {!approved && (
              <button className="quiet" onClick={() => setConfirming('reject')}>
                Reject
              </button>
            )}
          </div>
        )}
      </section>
    </article>
  )
}

// ---------- the locked door ----------

function Login({ onDone }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setProblem(null)
    try {
      await api('/login', { method: 'POST', body: JSON.stringify({ password }) })
      onDone()
    } catch (error) {
      setProblem(error.message)
      setBusy(false)
    }
  }

  return (
    <form className="door" onSubmit={submit}>
      <p className="door-note">The desk is locked. Enter the password to open it.</p>
      <label className="label" htmlFor="password">
        Password
      </label>
      <div className="door-row">
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={busy}
        />
        <button className="primary" type="submit" disabled={busy || !password}>
          {busy ? 'Opening…' : 'Open the desk'}
        </button>
      </div>
      {problem && <p className="problem">{problem}</p>}
    </form>
  )
}

// ---------- the whole desk ----------

export default function App() {
  const [session, setSession] = useState('checking') // 'checking' | 'out' | 'in'
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [log, setLog] = useState([])

  // Ask the backend which drafts still need a person.
  const loadDrafts = useCallback(async () => {
    try {
      setDrafts(await api('/drafts'))
      setError(null)
    } catch (problem) {
      if (problem.status === 401) {
        // The pass ran out or was never there: back to the locked door.
        setSession('out')
        setDrafts([])
      } else {
        setError(problem.message)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  // When the page opens: are we logged in? If so, load the drafts.
  useEffect(() => {
    let stillOpen = true
    api('/session')
      .then((data) => {
        if (!stillOpen) return
        if (data.logged_in) {
          setSession('in')
          loadDrafts()
        } else {
          setSession('out')
          setLoading(false)
        }
      })
      .catch((problem) => {
        if (!stillOpen) return
        setSession('in')
        setError(problem.message)
        setLoading(false)
      })
    return () => {
      stillOpen = false
    }
  }, [loadDrafts])

  // While the desk is open, look for new letters every 30 seconds.
  useEffect(() => {
    if (session !== 'in') return undefined
    const timer = setInterval(loadDrafts, 30000)
    return () => clearInterval(timer)
  }, [session, loadDrafts])

  function refresh() {
    setLoading(true)
    loadDrafts()
  }

  function handleLoggedIn() {
    setSession('in')
    refresh()
  }

  async function lockDesk() {
    try {
      await api('/logout', { method: 'POST' })
    } finally {
      setSession('out')
      setDrafts([])
      setLog([])
    }
  }

  // A letter was sent or rejected: take it off the desk and note it in the log.
  function handleDone(draft, outcome) {
    setDrafts((current) => current.filter((item) => item.id !== draft.id))
    setLog((current) => [
      {
        id: draft.id,
        time: timeNow(),
        outcome,
        who: draft.email.from_address,
        subject: draft.email.subject,
        // A sent reply that made a promise leaves a job behind; a rejected one does not.
        todo: outcome !== 'Rejected' && draft.needs_follow_up ? draft.follow_up_note || 'Follow up with the customer.' : null,
      },
      ...current,
    ])
  }

  const [today] = useState(() =>
    new Date().toLocaleDateString(undefined, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    }),
  )

  return (
    <main className="desk">
      <header className="masthead">
        <p className="dateline">{today}</p>
        <h1>The Reply Desk</h1>
        {session === 'in' && (
          <div className="tally">
            <span>
              {loading
                ? 'Checking the tray…'
                : drafts.length === 0
                  ? 'The tray is empty'
                  : `${drafts.length} ${drafts.length === 1 ? 'letter' : 'letters'} in the tray`}
            </span>
            <span>
              <button className="quiet" onClick={refresh} disabled={loading}>
                Check again
              </button>
              <button className="quiet" onClick={lockDesk}>
                Lock the desk
              </button>
            </span>
          </div>
        )}
      </header>

      {session === 'out' && <Login onDone={handleLoggedIn} />}

      {error && (
        <p className="problem wide">
          Could not reach the backend. Is it running? ({error})
        </p>
      )}

      {session === 'in' && !loading && !error && drafts.length === 0 && (
        <p className="empty">Nothing is waiting for you. New drafts will appear here.</p>
      )}

      {drafts.map((draft, index) => (
        <Letter
          key={draft.id}
          draft={draft}
          number={index + 1}
          onDone={handleDone}
          onChanged={loadDrafts}
        />
      ))}

      {log.length > 0 && (
        <section className="log" aria-label="What you did this session">
          <h2>Out tray, this session</h2>
          <ul>
            {log.map((entry) => (
              <li key={entry.id}>
                <span className="log-time">{entry.time}</span>
                <span className="log-outcome">{entry.outcome}</span>
                <span className="log-who">
                  {entry.who} · {entry.subject || '(no subject)'}
                  {entry.todo && <span className="log-todo">To do: {entry.todo}</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}
