import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { CredentialsPage } from '../pages/admin/CredentialsPage'
import { SshProfilesWizard } from '../components/SshProfilesWizard'
import type { SshBinding, SshProfile, SshUse } from '../credentials'

const json=(value:unknown)=>Promise.resolve(new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}}))
const profile:SshProfile={id:'host-profile',name:'CAYO Test',purpose:'host',login:'deploy',vault_path:'automation-credentials/ssh/cayo',vault_version:2,
  allowed_targets:['10.0.0.1'],is_active:true,fingerprint:'SHA256:public-fingerprint',public_key:'ssh-ed25519 public-test-key',revision:'profile-revision'}
const store={configured:true,base_url:'https://vault.example',namespace:'',kv_mount:'kv',auth_mount:'semaphore-ansible',role_id_present:true,secret_id_present:true}
const mount=(node:React.ReactNode)=>render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>)

beforeEach(()=>{vi.restoreAllMocks();localStorage.clear()})

describe('Zentrale SSH-Profile',()=>{
  it('hinterlegt den eigenen Vault-Lesezugang und leert die Zugangsfelder nach dem Speichern',async()=>{
    let sent:Record<string,unknown>|undefined
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      if(String(input).endsWith('/config')){if(options?.method==='PUT')sent=JSON.parse(String(options.body));return json(store)}
      return json([])
    }))
    mount(<CredentialsPage/>);const user=userEvent.setup()
    const role=await screen.findByLabelText(/^Profil-Lesezugang: Role-ID/),secret=screen.getByLabelText(/^Profil-Lesezugang: Secret-ID/)
    await user.type(role,'role-entered-once');await user.type(secret,'secret-entered-once')
    await user.click(screen.getByRole('button',{name:'Lesezugang speichern'}))
    await screen.findByText('Profil-Lesezugang gespeichert.')
    expect(sent).toMatchObject({auth_mount:'semaphore-ansible',role_id:'role-entered-once',secret_id:'secret-entered-once'})
    expect(role).toHaveValue('');expect(secret).toHaveValue('');expect(localStorage.length).toBe(0)
  })

  it('ordnet Host- und Git-Profile getrennt zu und speichert nur Profilreferenzen im Entwurf',async()=>{
    let selected:SshBinding[]=[]
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).endsWith('/profiles')
      ?json([profile,{...profile,id:'git-profile',name:'Git Lesen',purpose:'git'}])
      :json({inventories:[{name:'Host'}],repositories:[{name:'Git'}]})))
    function Harness(){const [bindings,setBindings]=useState<SshBinding[]>([]);selected=bindings;return <SshProfilesWizard templateId="template" bindings={bindings} onChange={setBindings}/>}
    mount(<Harness/>);const user=userEvent.setup()
    const inventory=await screen.findByLabelText('Inventory: Host')
    await screen.findByRole('option',{name:'CAYO Test · Version 2'})
    expect(inventory).not.toHaveTextContent('Git Lesen')
    await user.selectOptions(inventory,'host-profile')
    await user.selectOptions(screen.getByLabelText('Repository: Git'),'git-profile')
    expect(selected).toEqual([{profile_id:'host-profile',resource_kind:'inventories',resource_name:'Host'},
      {profile_id:'git-profile',resource_kind:'repositories',resource_name:'Git'}])
    expect(JSON.stringify(selected)).not.toContain('private_key');expect(localStorage.length).toBe(0)
  })

  it('zeigt Verwendungen und aktualisiert ein Projekt erst nach ausdrücklicher Bestätigung',async()=>{
    const use:SshUse={id:'use-a',profile_id:profile.id,creation_job_id:'job-a',semaphore_project_id:77,semaphore_key_id:8,
      vault_version:1,fingerprint:'SHA256:old',status:'installed',bindings:[{kind:'inventories',name:'Host',targets:['10.0.0.1']}]}
    let sent:Record<string,unknown>|undefined
    const confirm=vi.spyOn(window,'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const path=String(input)
      if(path.endsWith('/config'))return json(store)
      if(path.endsWith('/profiles'))return json([profile])
      if(path.endsWith('/sync')){sent=JSON.parse(String(options?.body));return json({...use,vault_version:2})}
      return json([use])
    }))
    mount(<CredentialsPage/>)
    const button=await screen.findByRole('button',{name:'Version übernehmen'})
    fireEvent.click(button);expect(sent).toBeUndefined()
    fireEvent.click(button)
    await waitFor(()=>expect(sent).toEqual({confirm:true,expected_version:1,desired_version:2,profile_revision:'profile-revision'}))
    expect(confirm).toHaveBeenCalledTimes(2)
    expect(screen.getByLabelText(/^Öffentlicher Schlüssel/)).toHaveValue(profile.public_key)
    expect(screen.queryByLabelText('Privater Schlüssel')).not.toBeInTheDocument()
  })
})
