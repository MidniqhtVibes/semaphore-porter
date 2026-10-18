import { ArrowLeft } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import './doom.css'

export default function DoomPage() {
  const { isAdmin } = useAuth()
  const location = useLocation()
  const candidate: unknown = location.state?.returnTo
  const back = typeof candidate === 'string' && /^\/(?:admin|portal)(?:\/|\?|$)/.test(candidate) &&
    !candidate.startsWith('/portal/iddqd') && (isAdmin || !candidate.startsWith('/admin'))
    ? candidate : isAdmin ? '/admin' : '/portal'

  return <main className="doom-page" aria-label="Doom Easter Egg">
    <header className="doom-header">
      <Link className="button button-secondary" to={back} replace><ArrowLeft size={16}/>Zurück zum Portal</Link>
      <span>E1M1 <span aria-hidden="true">/</span> Hangar</span>
      <span className="doom-secret">Secret found.</span>
    </header>
    <iframe className="doom-frame" title="Doom · E1M1 Hangar" src="/arcade/index.html"
      sandbox="allow-scripts allow-same-origin allow-downloads" allow="fullscreen" allowFullScreen/>
  </main>
}
