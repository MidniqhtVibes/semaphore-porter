import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, Boxes, CircleCheck, Server, Users } from 'lucide-react'
import { api } from '../../api'
import { Badge, Card, Loading, PageHeader, formatDate } from '../../components/ui'

type Dashboard = {
  tenant_count: number; active_user_count: number; project_count: number; running_task_count: number
  failed_task_count: number; incomplete_tenant_count: number
  semaphore: { configured: boolean; healthy: boolean | null; message: string; last_tested_at?: string | null }
  recent_audit: Array<{ id: string; occurred_at: string; event_type: string; target_type?: string; success: boolean }>
}

const eventLabels: Record<string, string> = { login: 'Anmeldung', tenant_created: 'Tenant erstellt', user_created: 'Benutzer erstellt', permission_changed: 'Berechtigung geändert', task_started: 'Task gestartet', task_policy_changed: 'Task Policy geändert' }

export function AdminDashboardPage() {
  const query = useQuery({ queryKey: ['admin-dashboard'], queryFn: () => api<Dashboard>('/admin/dashboard'), refetchInterval: 30_000 })
  if (query.isLoading) return <Loading />
  if (!query.data) throw query.error
  const data = query.data
  const stats = [
    ['Tenants', data.tenant_count, Boxes, 'info'], ['Aktive Benutzer', data.active_user_count, Users, 'success'],
    ['Semaphore-Projekte', data.project_count, Server, 'neutral'], ['Laufende Tasks', data.running_task_count, Activity, 'warning'],
    ['Fehlgeschlagen', data.failed_task_count, AlertTriangle, 'danger'], ['Unvollständig', data.incomplete_tenant_count, CircleCheck, 'warning'],
  ] as const
  return <><PageHeader title="Admin Dashboard" description="Betriebszustand und letzte Änderungen auf einen Blick." />
    <div className="stats-grid">{stats.map(([label, value, Icon, tone]) => <Card className="stat" key={label}><div className={`stat-icon tone-${tone}`}><Icon size={20}/></div><div><span>{label}</span><strong>{value}</strong></div></Card>)}</div>
    <div className="dashboard-grid"><Card><div className="card-heading"><div><h2>Semaphore-Verbindung</h2><p>Status des zentralen Servicekontos</p></div><Badge tone={data.semaphore.healthy ? 'success' : data.semaphore.configured ? 'danger' : 'warning'}>{data.semaphore.healthy ? 'Verbunden' : data.semaphore.configured ? 'Fehler' : 'Nicht konfiguriert'}</Badge></div><div className="connection-hero"><span className={`pulse ${data.semaphore.healthy ? 'pulse-ok' : ''}`}/><div><strong>{data.semaphore.message}</strong><p>Letzte Prüfung: {formatDate(data.semaphore.last_tested_at)}</p></div></div></Card>
      <Card><div className="card-heading"><div><h2>Letzte Änderungen</h2><p>Administrative und sicherheitsrelevante Aktionen</p></div></div><div className="activity-list">{data.recent_audit.map(event => <div className="activity-row" key={event.id}><span className={`activity-dot ${event.success ? '' : 'error'}`}/><div><strong>{eventLabels[event.event_type] || event.event_type}</strong><span>{event.target_type || 'Portal'} · {formatDate(event.occurred_at)}</span></div></div>)}</div></Card>
    </div>
  </>
}

