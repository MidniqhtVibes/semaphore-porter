import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { FlaskConical } from 'lucide-react'
import { useRuntime } from './runtime'

export function DemoFrame({children}:{children:ReactNode}){
  const runtime=useRuntime()
  if(runtime.mode!=='demo')return children
  return <div className="demo-frame"><div className="demo-ribbon" role="status"><div><FlaskConical size={19} aria-hidden="true"/><strong>DEMO · ausschließlich Beispieldaten</strong><span>Integrationen sind simuliert. Neustart verwirft die Daten.</span></div><div><Link className="button button-secondary" to="/">Demo-Steuerung</Link><a className="button button-secondary" href="/">Zurück zum Portal</a></div></div>{children}</div>
}
