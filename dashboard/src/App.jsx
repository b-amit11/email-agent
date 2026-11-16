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

function formatTime(value) {
  return new Date(value).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

function timeNow() {
  return new Date().toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

// "03-returns-and-refunds" -> "Returns and refunds"
function sheetTitle(name) {
  const words = name.replace(/^\d+-/, '').replaceAll('-', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

// Which fact sheets a reply was answered from. Older drafts carry no list.
function Sources({ sources, onSheet }) {
  if (!Array.isArray(sources)) return null
  return (
    <p className="sources">
      <span className="sources-label">Answered from</span>
      {sources.length === 0 && 'no fact sheet · passed to the team'}
      {sources.map((name) => (
        <button
          key={name}
          className="quiet source"
          onClick={() => onSheet(name)}
          title="Read this fact sheet"
        >
          {sheetTitle(name)}
        </button>
      ))}
    </p>
  )
}

// Turn the reviewer's CSV cell into something a spreadsheet reads safely.
function csvCell(value) {
  let text = String(value ?? '')
  if (/^[=+\-@]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

// ---------- one letter on the desk ----------

function Letter({ draft, number, onDone, onChanged, onSheet }) {
  const email = draft.email
  const approved = draft.status === 'approved'
  const replyText = approved ? draft.final_body : draft.body

  const [wantsEdit, setWantsEdit] = useState(false)
  const editing = wantsEdit && !approved
  const setEditing = setWantsEdit
  const [text, setText] = useState(draft.body)
  const [confirming, setConfirming] = useState(null) // 'send' | 'reject' | 'rewrite' | null
  const [note, setNote] = useState('')
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

  function rewrite(event) {
    event.preventDefault()
    return run(async () => {
      const fresh = await api(`/drafts/${draft.id}/redraft`, {
        method: 'POST',
        body: JSON.stringify({ note }),
      })
      setText(fresh.body)
      setNote('')
      onChanged()
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

        <Sources sources={draft.sources} onSheet={onSheet} />

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

        {confirming === 'rewrite' && (
          <form className="actions" onSubmit={rewrite}>
            <label className="ask" htmlFor={`note-${draft.id}`}>
              What should change?
            </label>
            <input
              id={`note-${draft.id}`}
              className="note"
              autoFocus
              maxLength={500}
              placeholder="e.g. shorter, and apologise for the delay"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              disabled={busy}
            />
            <button className="primary" type="submit" disabled={busy || !note.trim()}>
              {busy ? 'Rewriting…' : 'Rewrite'}
            </button>
            <button type="button" onClick={() => setConfirming(null)} disabled={busy}>
              Never mind
            </button>
          </form>
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
            {!approved && !editing && (
              <button onClick={() => setConfirming('rewrite')}>Ask for a rewrite</button>
            )}
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

// ---------- the filing cabinet ----------

function outcomeOf(draft) {
  if (draft.status === 'rejected') return 'Rejected'
  const edited = (draft.final_body || '').trim() !== (draft.body || '').trim()
  return edited ? 'Sent, edited' : 'Sent'
}

function FiledLetter({ draft, onSheet }) {
  const [open, setOpen] = useState(false)
  const email = draft.email
  const rejected = draft.status === 'rejected'
  const outcome = outcomeOf(draft)

  return (
    <li className="file">
      <button
        className="file-tab"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="file-date">{formatDate(draft.sent_at || draft.reviewed_at)}</span>
        <span className={`file-outcome ${rejected ? 'file-rejected' : ''}`}>{outcome}</span>
        <span className="file-who">
          {email.from_name || email.from_address} · {email.subject || '(no subject)'}
        </span>
        <span className="file-toggle" aria-hidden="true">
          {open ? '−' : '+'}
        </span>
      </button>

      {open && (
        <article className="letter filed">
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

          <section className="reply" aria-label={rejected ? 'Rejected draft' : 'Reply that was sent'}>
            <span className={`stamp ${rejected ? '' : 'stamp-approved'}`}>{outcome}</span>
            <p className="label">
              {rejected
                ? `Draft, rejected ${formatDate(draft.reviewed_at)} · never sent`
                : `Reply, sent ${formatDate(draft.sent_at)}`}
            </p>
            <pre className="sheet">{rejected ? draft.body : draft.final_body}</pre>
            <Sources sources={draft.sources} onSheet={onSheet} />
            {draft.needs_follow_up && !rejected && (
              <aside className="memo">
                <p className="memo-title">Follow-up was needed</p>
                <p className="memo-text">
                  {draft.follow_up_note || 'This reply promised that the team would do something.'}
                </p>
              </aside>
            )}
          </section>
        </article>
      )}
    </li>
  )
}

const FILTERS = [
  ['all', 'All'],
  ['sent', 'Sent'],
  ['rejected', 'Rejected'],
  ['follow-up', 'Follow-up owed'],
]

function matchesFilter(draft, filter) {
  if (filter === 'sent') return draft.status === 'sent'
  if (filter === 'rejected') return draft.status === 'rejected'
  if (filter === 'follow-up') return draft.status === 'sent' && draft.needs_follow_up
  return true
}

function matchesSearch(draft, words) {
  if (!words) return true
  const email = draft.email
  const haystack = [
    email.from_name,
    email.from_address,
    email.subject,
    email.body,
    draft.final_body || draft.body,
  ]
    .join(' ')
    .toLowerCase()
  return words.split(/\s+/).every((word) => haystack.includes(word))
}

// Save the listed letters as a file that opens in a spreadsheet.
function downloadCsv(drafts) {
  const header = ['Date', 'Outcome', 'Customer', 'Address', 'Subject', 'Follow-up', 'Reply']
  const rows = drafts.map((draft) => [
    draft.sent_at || draft.reviewed_at || '',
    outcomeOf(draft),
    draft.email.from_name || '',
    draft.email.from_address,
    draft.email.subject || '',
    draft.status === 'sent' && draft.needs_follow_up ? draft.follow_up_note || 'yes' : '',
    draft.status === 'rejected' ? draft.body : draft.final_body,
  ])
  const text = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob(['\ufeff', text], { type: 'text/csv' }))
  link.download = 'reply-desk-filing-cabinet.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

function Cabinet({ onLocked, onSheet }) {
  const [filed, setFiled] = useState(null) // null while loading
  const [problem, setProblem] = useState(null)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let stillOpen = true
    api('/history')
      .then((data) => {
        if (stillOpen) setFiled(data)
      })
      .catch((error) => {
        if (!stillOpen) return
        if (error.status === 401) onLocked()
        else setProblem(error.message)
      })
    return () => {
      stillOpen = false
    }
  }, [onLocked])

  if (problem) return <p className="problem wide">Could not open the cabinet. ({problem})</p>
  if (filed === null) return <p className="empty">Opening the drawer…</p>
  if (filed.length === 0) {
    return <p className="empty">The cabinet is empty. Letters you send or reject are filed here.</p>
  }

  const sent = filed.filter((draft) => draft.status === 'sent').length
  const words = search.trim().toLowerCase()
  const shown = filed.filter(
    (draft) => matchesFilter(draft, filter) && matchesSearch(draft, words),
  )
  return (
    <section className="cabinet" aria-label="Filing cabinet">
      <h2>
        Filing cabinet · {sent} sent · {filed.length - sent} rejected
      </h2>
      <div className="drawer">
        <input
          className="note"
          type="search"
          aria-label="Search the filing cabinet"
          placeholder="Search by name, subject, or words in the letter"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <span className="drawer-filters">
          {FILTERS.map(([value, label]) => (
            <button
              key={value}
              className={`quiet ${filter === value ? 'chosen' : ''}`}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
          <button className="quiet" onClick={() => downloadCsv(shown)} disabled={shown.length === 0}>
            Download list
          </button>
        </span>
      </div>
      {shown.length === 0 ? (
        <p className="empty">No filed letter matches.</p>
      ) : (
        <ul>
          {shown.map((draft) => (
            <FiledLetter key={draft.id} draft={draft} onSheet={onSheet} />
          ))}
        </ul>
      )}
    </section>
  )
}

// ---------- the fact sheets ----------

// The sheets are simple text: "#" headings, "-" list items, and plain lines.
function SheetText({ text }) {
  const blocks = []
  let items = []
  const flush = () => {
    if (items.length) blocks.push(<ul key={blocks.length}>{items}</ul>)
    items = []
  }
  text.split('\n').forEach((line, index) => {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ')) {
      items.push(<li key={index}>{trimmed.slice(2)}</li>)
      return
    }
    flush()
    if (trimmed.startsWith('## ')) blocks.push(<h4 key={blocks.length}>{trimmed.slice(3)}</h4>)
    else if (trimmed.startsWith('# ')) blocks.push(<h3 key={blocks.length}>{trimmed.slice(2)}</h3>)
    else if (trimmed) blocks.push(<p key={blocks.length}>{trimmed}</p>)
  })
  flush()
  return blocks
}

function FactSheets({ focus, onLocked }) {
  const [sheets, setSheets] = useState(null) // null while loading
  const [problem, setProblem] = useState(null)

  useEffect(() => {
    let stillOpen = true
    api('/knowledge')
      .then((data) => {
        if (stillOpen) setSheets(data)
      })
      .catch((error) => {
        if (!stillOpen) return
        if (error.status === 401) onLocked()
        else setProblem(error.message)
      })
    return () => {
      stillOpen = false
    }
  }, [onLocked])

  // Arriving from an "Answered from" link: bring that sheet into view.
  useEffect(() => {
    if (sheets && focus) {
      document.getElementById(`sheet-${focus}`)?.scrollIntoView({ block: 'start' })
    }
  }, [sheets, focus])

  if (problem) return <p className="problem wide">Could not fetch the fact sheets. ({problem})</p>
  if (sheets === null) return <p className="empty">Fetching the fact sheets…</p>

  return (
    <section className="rulebook" aria-label="Fact sheets">
      <h2>Fact sheets · everything the agent is allowed to know</h2>
      {sheets.map((sheet) => (
        <article
          key={sheet.name}
          id={`sheet-${sheet.name}`}
          className={`factsheet ${focus === sheet.name ? 'factsheet-focus' : ''}`}
        >
          <p className="label">{sheet.name}</p>
          <SheetText text={sheet.text} />
        </article>
      ))}
    </section>
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
  const [view, setView] = useState('tray') // 'tray' | 'cabinet' | 'sheets'
  const [focusSheet, setFocusSheet] = useState(null)

  const openSheet = useCallback((name) => {
    setFocusSheet(name)
    setView('sheets')
  }, [])
  const [counts, setCounts] = useState(null)

  const handleLocked = useCallback(() => {
    setSession('out')
    setDrafts([])
    setView('tray')
  }, [])

  // Ask the backend which drafts still need a person.
  const loadDrafts = useCallback(async () => {
    try {
      setDrafts(await api('/drafts'))
      setError(null)
      // The numbers are a nicety: if they fail, the desk still works.
      api('/summary').then(setCounts, () => {})
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
      setView('tray')
    }
  }

  // A letter was sent or rejected: take it off the desk and note it in the log.
  function handleDone(draft, outcome) {
    setDrafts((current) => current.filter((item) => item.id !== draft.id))
    api('/summary').then(setCounts, () => {})
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
              {counts?.last_mail_check && (
                <span className="checked"> · inbox checked {formatTime(counts.last_mail_check)}</span>
              )}
            </span>
            <span>
              {view === 'tray' ? (
                <button className="quiet" onClick={refresh} disabled={loading}>
                  Check again
                </button>
              ) : (
                <button className="quiet" onClick={() => setView('tray')}>
                  Back to the tray
                </button>
              )}
              {view !== 'cabinet' && (
                <button className="quiet" onClick={() => setView('cabinet')}>
                  Filing cabinet
                </button>
              )}
              {view !== 'sheets' && (
                <button className="quiet" onClick={() => openSheet(null)}>
                  Fact sheets
                </button>
              )}
              <button className="quiet" onClick={lockDesk}>
                Lock the desk
              </button>
            </span>
          </div>
        )}
        {session === 'in' && counts && (
          <dl className="ledger" aria-label="Totals so far">
            <div>
              <dt>Received</dt>
              <dd>{counts.received}</dd>
            </div>
            <div>
              <dt>Waiting</dt>
              <dd>{counts.waiting}</dd>
            </div>
            <div>
              <dt>Sent</dt>
              <dd>{counts.sent}</dd>
            </div>
            <div>
              <dt>Rejected</dt>
              <dd>{counts.rejected}</dd>
            </div>
          </dl>
        )}
      </header>

      {session === 'out' && <Login onDone={handleLoggedIn} />}

      {error && (
        <p className="problem wide">
          Could not reach the backend. Is it running? ({error})
        </p>
      )}

      {session === 'in' && view === 'cabinet' && (
        <Cabinet onLocked={handleLocked} onSheet={openSheet} />
      )}

      {session === 'in' && view === 'sheets' && (
        <FactSheets focus={focusSheet} onLocked={handleLocked} />
      )}

      {session === 'in' && view === 'tray' && !loading && !error && drafts.length === 0 && (
        <p className="empty">Nothing is waiting for you. New drafts will appear here.</p>
      )}

      {view === 'tray' &&
        drafts.map((draft, index) => (
          <Letter
            key={draft.id}
            draft={draft}
            number={index + 1}
            onDone={handleDone}
            onChanged={loadDrafts}
            onSheet={openSheet}
          />
        ))}

      {view === 'tray' && log.length > 0 && (
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
