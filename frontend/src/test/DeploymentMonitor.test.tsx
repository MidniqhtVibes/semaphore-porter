import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DeploymentMonitor, { remaining, type Deployment, type MonitoringSnapshot } from '../components/DeploymentMonitor'

const json=(value:unknown)=>Promise.resolve(new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}}))
const now=Math.floor(Date.now()/1000)
const deployment:Deployment={id:'source:demo-1',deployment_id:'demo-1',source_id:'source',host:'Zielhost',tenant_name:'Demo Tenant',tenant_slug:'demo',runtime_scope_id:'azubi-test',semaphore_project_id:77,application_id:'azubiorga',application_name:'AzubiOrga',release_id:'v1',database_type:'postgres',provider_id:'pg',database_mode:'shared_pool',dataset_id:'test-a',source_git_commit:'abc123',url:'http://10.0.0.1:30001',host_port:30001,created_at:now-200,ready_at:now-60,expires_at:now+62,observed_at:now,status:'running',lifecycle_status:'running',container_count:2,running_count:2,unhealthy_count:0,starting_count:0,stale:false,metadata_error:false}
const snapshot:MonitoringSnapshot={server_time:now,stale_after_seconds:90,sources:[{id:'source',name:'Zielhost',received_at:new Date().toISOString(),observed_at:now,stale:false,complete:true,warnings:[],deployment_count:1}],deployments:[deployment]}
const mount=()=>render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><DeploymentMonitor/></QueryClientProvider>)
beforeEach(()=>{vi.restoreAllMocks();localStorage.clear()})
afterEach(()=>vi.useRealTimers())

describe('Live-Deploymentüberwachung',()=>{
  it('zeigt Metadaten direkt gestarteter Deployments und filtert ohne TaskRun',async()=>{
    vi.stubGlobal('fetch',vi.fn(()=>json(snapshot)))
    mount();const user=userEvent.setup()
    expect(await screen.findByText('AzubiOrga')).toBeInTheDocument()
    expect(screen.getByText('00:01:02')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:'Ansehen'}))
    const dialog=screen.getByRole('dialog')
    expect(within(dialog).getByText('azubi-test')).toBeInTheDocument()
    expect(within(dialog).getByText('test-a')).toBeInTheDocument()
    expect(within(dialog).getByText('pg')).toBeInTheDocument()
    expect(within(dialog).getByRole('link',{name:'Anwendung öffnen'})).toHaveAttribute('href',deployment.url)
    await user.click(within(dialog).getByRole('button',{name:'Dialog schließen'}))
    await user.type(screen.getByLabelText('Deployment suchen'),'wordpress')
    expect(screen.getByText('Keine passenden Deployments')).toBeInTheDocument()
  })

  it('zählt jede Sekunde herunter und markiert den Ablauf ohne eine Löschung zu behaupten',async()=>{
    vi.useFakeTimers({toFake:['setInterval','clearInterval','Date']})
    vi.stubGlobal('fetch',vi.fn(()=>json({...snapshot,deployments:[{...deployment,expires_at:now+2}]})))
    mount();expect(await screen.findByText('00:00:02')).toBeInTheDocument()
    await act(async()=>{vi.advanceTimersByTime(3000)})
    expect(screen.getByText('00:00:00')).toBeInTheDocument()
    expect(screen.getByText('TTL abgelaufen',{selector:'span.badge'})).toBeInTheDocument()
    expect(screen.getByText('demo-1')).toBeInTheDocument()
  })

  it('zeigt bei veralteten Meldungen keinen laufenden Zustand und behält letzte Metadaten',async()=>{
    vi.stubGlobal('fetch',vi.fn(()=>json({...snapshot,deployments:[{...deployment,observed_at:now-120}]})))
    mount();expect(await screen.findByText('Meldung veraltet')).toBeInTheDocument()
    expect(screen.getByText('Unbekannt',{selector:'span.badge'})).toBeInTheDocument()
    expect(screen.getByText('AzubiOrga')).toBeInTheDocument()
  })

  it('legt eine Quelle an und zeigt den Token nur bis zum Ausblenden ohne Browserspeicherung',async()=>{
    let sent:unknown
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      if(String(input).endsWith('/sources')){sent=JSON.parse(String(options?.body));return json({name:'Mein Zielhost',token:'one-time-collector-token'})}
      return json({...snapshot,sources:[],deployments:[]})
    }))
    mount();const user=userEvent.setup()
    await screen.findByText('Noch keine Monitoring-Quelle')
    await user.click(screen.getByText('Monitoring-Quellen und Einrichtung (0)'))
    expect(screen.getByRole('link',{name:'Status-Exporter herunterladen'})).toHaveAttribute('href','/api/admin/deployments/exporter')
    expect(screen.getByRole('link',{name:'Sender herunterladen'})).toHaveAttribute('href','/api/admin/deployments/collector')
    await user.type(screen.getByLabelText('Name des Deployment-Zielhosts'),'Mein Zielhost')
    await user.click(screen.getByRole('button',{name:'Quelle anlegen'}))
    expect(await screen.findByLabelText('Einmaliger Collector-Token')).toHaveValue('one-time-collector-token')
    expect(sent).toEqual({name:'Mein Zielhost'})
    fireEvent.click(screen.getByRole('button',{name:'Token ausblenden'}))
    expect(screen.queryByLabelText('Einmaliger Collector-Token')).not.toBeInTheDocument()
    expect(localStorage.length).toBe(0)
  })

  it('berechnet TTL mit Stunden und lässt unbekannte Ablaufzeiten unbekannt',()=>{
    expect(remaining(now+3661,now)).toBe('01:01:01')
    expect(remaining(now-1,now)).toBe('00:00:00')
    expect(remaining(null,now)).toBe('Nicht gemeldet')
  })
})
