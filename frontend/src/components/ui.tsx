import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return <div className="page-header"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</div>
}

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`card ${className}`} {...props} />
}

export function Button({ variant = 'primary', loading, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; loading?: boolean }) {
  return <button className={`button button-${variant}`} disabled={loading || props.disabled} {...props}>
    {loading && <LoaderCircle size={16} className="spin" />}{children}
  </button>
}

export function Badge({ tone = 'neutral', children }: { tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function StatusBadge({ status }: { status: string }) {
  const tone = ['active', 'success', 'successful', 'completed'].includes(status) ? 'success'
    : ['failed', 'error'].includes(status) ? 'danger'
    : ['running', 'queued', 'draft'].includes(status) ? 'warning' : 'neutral'
  const labels: Record<string, string> = { active: 'Aktiv', inactive: 'Deaktiviert', draft: 'Entwurf', running: 'Läuft', queued: 'Wartet', success: 'Erfolgreich', failed: 'Fehlgeschlagen', stopped: 'Abgebrochen' }
  return <Badge tone={tone}>{labels[status] || status}</Badge>
}

export function Loading({ label = 'Daten werden geladen …' }: { label?: string }) {
  return <div className="state"><LoaderCircle className="spin"/><span>{label}</span></div>
}

export function Empty({ title, text }: { title: string; text: string }) {
  return <Card className="empty"><div className="empty-icon">◇</div><h3>{title}</h3><p>{text}</p></Card>
}

export function Notice({ type = 'info', children }: { type?: 'info' | 'error' | 'success'; children: ReactNode }) {
  return <div className={`notice notice-${type}`}>{type === 'error' ? <AlertCircle size={18}/> : <CheckCircle2 size={18}/>}<div>{children}</div></div>
}

export function Field({ label, help, error, children }: { label: string; help?: string; error?: string; children: ReactNode }) {
  return <label className="field"><span className="field-label">{label}</span>{children}{help && <span className="field-help">{help}</span>}{error && <span className="field-error">{error}</span>}</label>
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><div className="modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={event => event.stopPropagation()}><div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Dialog schließen">×</button></div>{children}</div></div>
}

export const formatDate = (value?: string | null) => value ? new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '–'

