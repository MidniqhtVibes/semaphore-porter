import { useLayoutEffect, useRef, useState } from 'react'
import { ArrowDownToLine } from 'lucide-react'
import { Badge, Button, Card } from './ui'

type OutputLine = { time: string; output: string }

export function TaskOutput({ runId, lines, live }: { runId: string; lines: OutputLine[]; live: boolean }) {
  const terminal = useRef<HTMLDivElement>(null)
  const follow = useRef(true)
  const [following, setFollowing] = useState(true)

  const scrollToEnd = () => {
    const element = terminal.current
    if (element) element.scrollTop = Math.max(0, element.scrollHeight - element.clientHeight)
  }

  useLayoutEffect(() => {
    follow.current = true
    setFollowing(true)
  }, [runId])

  useLayoutEffect(() => {
    if (follow.current) scrollToEnd()
  }, [runId, lines])

  const resume = () => {
    follow.current = true
    setFollowing(true)
    scrollToEnd()
  }

  return <Card className="terminal-card">
    <div className="terminal-head"><div><span/><span/><span/></div><strong>Task-Ausgabe</strong><Badge tone={live ? 'warning' : 'neutral'}>{live ? 'LIVE' : 'LOG'}</Badge></div>
    {(live || !following) && <div className="terminal-toolbar">
      <p className="account-note">{live ? 'Status und Ausgabe werden alle zwei Sekunden aktualisiert.' : 'Task abgeschlossen.'}{!following && ' Automatisches Scrollen pausiert.'}</p>
      {!following && <Button type="button" variant="secondary" onClick={resume}><ArrowDownToLine size={15}/>Zum neuesten Eintrag</Button>}
    </div>}
    <div className="terminal" role="log" aria-label="Task-Ausgabe" tabIndex={0} ref={terminal} onScroll={event => {
      const element = event.currentTarget
      const atEnd = element.scrollHeight - element.clientHeight - element.scrollTop <= 32
      follow.current = atEnd
      setFollowing(atEnd)
    }}>
      {lines.length ? lines.map((line, index) => <div key={`${line.time}-${index}`}><time>{new Date(line.time).toLocaleTimeString('de-DE')}</time><code>{line.output}</code></div>) : <span className="terminal-empty">Warte auf Ausgabe …</span>}
    </div>
  </Card>
}
