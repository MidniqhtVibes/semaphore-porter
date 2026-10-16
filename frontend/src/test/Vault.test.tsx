import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { VaultWizard } from '../components/VaultWizard'
import { VaultPage } from '../pages/admin/VaultPage'
import { TenantWizardPage } from '../pages/admin/TenantWizardPage'
import type { VaultInputs, VaultPlan } from '../vault'

const plan:VaultPlan={kv_mount:'kv',objects:[{id:'azubiorga',kind:'application',path:'semaphore/tenants/test-a/azubiorga',fields:[
  {key:'registry_password',source:'registry',generate:null,input_id:'application:azubiorga.registry_password',min_length:1,max_length:4096,hex:false,even_length:false,forbid_whitespace:false},
  {key:'crypto_salt',source:'input',generate:'hex',input_id:'application:azubiorga.crypto_salt',min_length:16,max_length:4096,hex:true,even_length:true,forbid_whitespace:true},
]}]}
const json=(value:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}}))

beforeEach(()=>{vi.restoreAllMocks();localStorage.clear()})

describe('Vault-Onboarding',()=>{
  it('verlangt die bewusste Wahl einer Generierung und hält manuelle Werte aus dem Browser-Speicher',async()=>{
    let current:VaultInputs={}
    function Harness(){const [inputs,setInputs]=useState<VaultInputs>({});current=inputs;return <VaultWizard plan={plan} inputs={inputs} onChange={setInputs} saved={false} jobId="job-a" onResolved={async()=>{}} disabled={false}/>}
    render(<Harness/>);const user=userEvent.setup()
    expect(screen.getByRole('combobox')).toHaveValue('manual')
    const input=screen.getByLabelText(/^azubiorga: crypto_saltHex/)
    expect(input).toHaveAttribute('type','password')
    await user.type(input,'0123456789abcdef')
    expect(current['application:azubiorga.crypto_salt']).toEqual({mode:'manual',value:'0123456789abcdef'})
    expect(localStorage.length).toBe(0)
    await user.selectOptions(screen.getByRole('combobox'),'generate')
    expect(current['application:azubiorga.crypto_salt']).toEqual({mode:'generate',value:''})
    expect(screen.queryByDisplayValue('0123456789abcdef')).not.toBeInTheDocument()
    expect(screen.getByText(/Nur verwenden, wenn dein Image neue Crypto-Werte erlaubt/)).toBeInTheDocument()
  })

  it('zeigt bei Wiederaufnahme keine gespeicherten Secret-Inhalte und sperrt Änderungen',()=>{
    render(<VaultWizard plan={plan} inputs={{}} onChange={()=>{}} saved jobId="job-a" onResolved={async()=>{}} disabled={false}/>)
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(document.querySelector('input[type="password"]')).toBeNull()
    expect(screen.getByText(/bereits geschützt gespeichert/)).toBeInTheDocument()
  })

  it('verlangt eine ausdrückliche Prüfung zur Zuordnung eines unklaren Schreibergebnisses',async()=>{
    const fetchMock=vi.fn(()=>json({message:'OK'}));vi.stubGlobal('fetch',fetchMock)
    const resolved=vi.fn(async()=>{})
    render(<VaultWizard plan={plan} inputs={{}} onChange={()=>{}} saved progress={{objects:{[plan.objects[0].path]:{state:'uncertain'}}}} jobId="job-a" onResolved={resolved} disabled={false}/>)
    const user=userEvent.setup(),button=screen.getByRole('button',{name:'Eigene Anlage bestätigen'})
    expect(button).toBeDisabled()
    await user.click(screen.getByRole('checkbox'));await user.click(button)
    await waitFor(()=>expect(resolved).toHaveBeenCalledOnce())
    const [url,options]=fetchMock.mock.calls[0] as unknown as [string,RequestInit]
    expect(url).toBe('/api/admin/creation-jobs/job-a/vault/resolve')
    expect(JSON.parse(String(options.body))).toEqual({path:plan.objects[0].path,decision:'created_by_this_job',confirm_checked_in_vault:true})
  })

  it('speichert zentrale Credentials separat und leert erfolgreiche Eingaben',async()=>{
    let submitted:Record<string,unknown>|undefined
    const config={configured:true,enabled:true,base_url:'https://vault.example',credentials_present:{reader_secret_id:true},registry_configured:{azubiorga:true}}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      if(String(input).endsWith('/vault/catalog'))return json({source_revision:'stack-1',applications:{azubiorga:{display_name:'AzubiOrga',database_types:{postgresql:'postgresql-v1'},datasets:{}}}})
      if(options?.method==='PUT')submitted=JSON.parse(String(options.body))
      return json(config)
    }))
    const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})
    render(<QueryClientProvider client={client}><MemoryRouter><VaultPage/></MemoryRouter></QueryClientProvider>)
    const user=userEvent.setup()
    const input=await screen.findByLabelText(/^Semaphore-Lesezugang: Secret-ID/)
    expect(input).toHaveValue('')
    await user.type(input,'once-entered-secret')
    await user.click(screen.getByRole('button',{name:'Konfiguration speichern'}))
    await screen.findByText('Vault-Konfiguration gespeichert.')
    expect(submitted?.reader_secret_id).toBe('once-entered-secret')
    expect(input).toHaveValue('')
    expect(localStorage.length).toBe(0)
  })

  it('behält Secret-Eingaben beim Zurückgehen und sendet sie ausschließlich zur Ausführung',async()=>{
    let saved:Record<string,unknown>|undefined,executed:Record<string,unknown>|undefined
    const draft={project_name:'Vault Tenant',tenant_slug:'test-a',runtime_scope_id:'scope-a',display_name:'Vault Tenant',wizard_step:6,
      application_ids:['azubiorga'],database_types:['postgresql'],dataset_ids:['none'],task_template_names:['deploy'],environment_names:['Semaphore-Defaults'],provision_vault:true}
    const job={id:'job-a',project_template_id:'template-a',status:'validated',draft_data:draft,vault_plan:plan,vault_values_saved:false,validation_result:{errors:[],warnings:[]}}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const url=String(input)
      if(url.endsWith('/vault'))return json({configured:true,enabled:true})
      if(url.endsWith('/vault/catalog'))return json({source_revision:'stack-1',applications:{}})
      if(url.endsWith('/project-templates'))return json([{id:'template-a',name:'Source',survey_catalog:{},task_templates:['deploy'],environments:['Semaphore-Defaults']}])
      if(url.endsWith('/creation-jobs'))return json([job])
      if(url.endsWith('/job-a')&&options?.method==='PUT'){saved=JSON.parse(String(options.body));return json({...job,validation_result:null})}
      if(url.endsWith('/job-a/validate'))return json(job)
      if(url.endsWith('/job-a/execute')){executed=JSON.parse(String(options?.body));return json({...job,status:'completed',tenant_id:'tenant-a'})}
      return json([])
    }))
    const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})
    render(<QueryClientProvider client={client}><MemoryRouter><TenantWizardPage/></MemoryRouter></QueryClientProvider>)
    const user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:'Fortsetzen'}))
    await user.type(screen.getByLabelText(/^azubiorga: crypto_saltHex/),'0123456789abcdef')
    await user.click(screen.getByRole('button',{name:'Zurück'}))
    await user.click(screen.getByRole('button',{name:'Speichern & weiter'}))
    expect(await screen.findByLabelText(/^azubiorga: crypto_saltHex/)).toHaveValue('0123456789abcdef')
    expect(JSON.stringify(saved)).not.toContain('0123456789abcdef')
    await user.click(screen.getByRole('button',{name:'Projekt verbindlich erstellen'}))
    await screen.findByRole('heading',{name:'Tenant-Projekt wurde registriert'})
    expect(executed?.vault_inputs).toEqual({'application:azubiorga.crypto_salt':{mode:'manual',value:'0123456789abcdef'}})
    expect(localStorage.length).toBe(0)
  })
})
