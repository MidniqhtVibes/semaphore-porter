import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, ChevronLeft, ChevronRight, CircleCheck, Database, FileCheck2, Layers3, PackageCheck, Rocket, Settings2, ShieldCheck, Users } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../../api'
import { Button, Card, Field, Loading, Notice, PageHeader } from '../../components/ui'
import type { User } from '../../types'
import { Link } from 'react-router-dom'
import { VaultWizard } from '../../components/VaultWizard'
import { SshProfilesWizard } from '../../components/SshProfilesWizard'
import type { SshBinding, SshPlan } from '../../credentials'
import type { VaultCatalog, VaultConfig, VaultInputs, VaultPlan, VaultProgress } from '../../vault'

type Template = {id:string;name:string;description:string;survey_catalog:Record<string,unknown[]>;task_templates:string[];environments:string[]}
type Preset = {id:string;name:string;category:string;description:string}
type Group = {id:string;name:string}
type Resources = Record<'environments'|'repositories'|'inventories'|'templates',Array<Record<string,unknown>>>
type CreationJob = {id:string;project_template_id:string;status:string;draft_data:Draft;validation_result?:{errors:string[];warnings:string[]}|null;tenant_id?:string|null;last_error?:string|null;vault_plan?:VaultPlan|null;vault_progress?:VaultProgress|null;vault_values_saved?:boolean;credential_plan?:SshPlan[]|null;credential_progress?:{started?:boolean;installed?:boolean}|null}
type Draft = {
  project_name:string;tenant_slug:string;runtime_scope_id:string;display_name:string;description:string
  application_id:string;database_type:string;dataset_id:string
  application_ids:string[];database_types:string[];dataset_ids:string[];wizard_step:number;ttl_minutes:number
  task_template_names:string[];environment_names:string[];preset_ids:string[];resource_overrides?:Resources
  repository_url?:string;repository_branch?:string
  access_assignments:Array<{user_id?:string;group_id?:string;role_code:string}>
  create_default_policies:boolean;activate_after_creation:boolean
  provision_vault:boolean
  ssh_bindings:SshBinding[]
}
const steps = [
  ['Vorlage','Projektquelle auswählen',Layers3],['Tenant','Stammdaten festlegen',Settings2],
  ['Anwendung','Testdaten konfigurieren',Database],['Ressourcen','Tasks und Gruppen',PackageCheck],
  ['Presets','Variablen ergänzen',FileCheck2],['Berechtigungen','Benutzer zuweisen',Users],
  ['Validieren','Importvorschau prüfen',ShieldCheck],['Erstellen','Semaphore-Projekt anlegen',Rocket],
] as const
const optionFields = [['application_ids','application_id','Anwendungen'],['database_types','database_type','Datenbankprovider'],['dataset_ids','dataset_id','Testdatensätze']] as const
const initial:Draft = {
  project_name:'',tenant_slug:'',runtime_scope_id:'',display_name:'',description:'',
  application_id:'',database_type:'',dataset_id:'',application_ids:[],database_types:[],dataset_ids:[],
  wizard_step:0,ttl_minutes:60,task_template_names:[],environment_names:[],preset_ids:[],access_assignments:[],
  create_default_policies:true,activate_after_creation:false,
  provision_vault:false,
  ssh_bindings:[],
}
const editable = (job:CreationJob|null) => !job || !job.vault_values_saved&&!job.credential_progress&&['draft','validated','failed'].includes(job.status)

export function TenantWizardPage() {
  const navigate=useNavigate(), [params]=useSearchParams()
  const [step,setStep]=useState(0), [furthestStep,setFurthestStep]=useState(0)
  const [draft,setDraftState]=useState<Draft>(initial), [job,setJob]=useState<CreationJob|null>(null)
  const [templateId,setTemplateId]=useState(''), [error,setError]=useState('')
  const [busy,setBusy]=useState(false), [retry,setRetry]=useState(false)
  const [vaultInputs,setVaultInputs]=useState<VaultInputs>({})
  const vault=useQuery({queryKey:['vault-config'],queryFn:()=>api<VaultConfig>('/admin/vault')})
  const catalog=useQuery({queryKey:['vault-catalog'],queryFn:()=>api<VaultCatalog>('/admin/vault/catalog'),enabled:draft.provision_vault})
  const jobs=useQuery({queryKey:['creation-jobs'],queryFn:()=>api<CreationJob[]>('/admin/creation-jobs')})
  const templates=useQuery({queryKey:['project-templates'],queryFn:()=>api<Template[]>('/admin/project-templates')})
  const presets=useQuery({queryKey:['presets'],queryFn:()=>api<Preset[]>('/admin/presets')})
  const users=useQuery({queryKey:['admin-users'],queryFn:()=>api<User[]>('/admin/users')})
  const groups=useQuery({queryKey:['admin-groups'],queryFn:()=>api<Group[]>('/admin/groups')})
  const selected=templates.data?.find(item=>item.id===templateId)
  const setDraft=(update:(value:Draft)=>Draft)=>{
    setDraftState(update)
    setJob(current=>current?{...current,validation_result:null}:null)
  }
  const moveTo=(target:number)=>{setStep(target);setFurthestStep(value=>Math.max(value,target))}
  const create=useMutation({mutationFn:()=>api<CreationJob>('/admin/creation-jobs',{
    method:'POST',body:JSON.stringify({idempotency_key:crypto.randomUUID(),project_template_id:templateId}),
  })})
  const persist=async(target=step)=>{
    let current=job
    if(!current){current=await create.mutateAsync();setJob(current)}
    const updated=await api<CreationJob>(`/admin/creation-jobs/${current.id}`,{
      method:'PUT',body:JSON.stringify({draft_data:{...draft,wizard_step:Math.max(furthestStep,target)}}),
    })
    setJob(updated)
    return updated
  }
  const validate=useMutation({
    mutationFn:async()=>{const current=await persist(6);return api<CreationJob>(`/admin/creation-jobs/${current.id}/validate`,{method:'POST'})},
    onSuccess:value=>{setJob(value);moveTo(6);setError('')},onError:(e:Error)=>setError(e.message),
  })
  const execute=useMutation({
    mutationFn:()=>api<CreationJob>(`/admin/creation-jobs/${job?.id}/execute`,{
      method:'POST',body:JSON.stringify({confirm_project_creation:true,allow_retry_after_verified_absence:retry,vault_inputs:draft.provision_vault&&!job?.vault_values_saved?vaultInputs:{}}),
    }),
    onSuccess:value=>{setJob(value);setVaultInputs({});moveTo(value.status==='completed'?7:6);setError('');void jobs.refetch()},
    onError:async(e:Error)=>{
      setError(e.message)
      if(job){try{const value=await api<CreationJob>(`/admin/creation-jobs/${job.id}`);setJob(value);if(value.vault_values_saved)setVaultInputs({})}catch{/* Keep the original action error. */}}
      void jobs.refetch()
    },
  })
  const forward=async(target:number)=>{
    setError('')
    if(!templateId){setError('Bitte zuerst eine Projektvorlage auswählen.');return}
    if(target>=2&&(!draft.project_name||!draft.tenant_slug||!draft.runtime_scope_id||!draft.display_name)){
      setError('Projektname, Tenant-ID, Runtime-Scope und Anzeigename sind erforderlich.');return
    }
    if(target>=3){
      for(const [plural,singular,label] of optionFields){
        if(selected?.survey_catalog[singular]?.length&&!draft[plural].length){setError(`Bitte mindestens einen Wert für ${label} auswählen.`);return}
      }
    }
    if(target>=4&&!draft.task_template_names.length){setError('Mindestens ein Task Template ist erforderlich.');return}
    setBusy(true)
    try{
      if(target===6){await validate.mutateAsync();return}
      await persist(target);moveTo(target)
    }catch(reason){setError(reason instanceof Error?reason.message:'Entwurf konnte nicht gespeichert werden.')}
    finally{setBusy(false)}
  }
  const chooseTemplate=(id:string)=>{
    if(id===templateId)return
    setTemplateId(id);setJob(null);setRetry(false);setFurthestStep(0)
    setVaultInputs({})
    const item=templates.data?.find(row=>row.id===id)
    if(item)setDraftState(value=>({...value,resource_overrides:undefined,wizard_step:0,
      task_template_names:item.task_templates,environment_names:item.environments,
      application_id:'',database_type:'',dataset_id:'',application_ids:[],database_types:[],dataset_ids:[],
      provision_vault:Boolean(vault.data?.enabled),
      ssh_bindings:[],
    }))
  }
  useEffect(()=>{const id=params.get('template');if(id&&templates.data&&!templateId)chooseTemplate(id)},[params,templates.data,templateId])
  const resume=(value:CreationJob)=>{
    const restored={...initial,...value.draft_data}
    for(const [plural,singular] of optionFields)restored[plural]=value.draft_data[plural]??(value.draft_data[singular]?[value.draft_data[singular]]:[])
    const target=value.status==='completed'?7:['validated','restoring','verification_required','semaphore_created'].includes(value.status)?6:Math.min(6,Math.max(1,restored.wizard_step))
    setJob(value);setTemplateId(value.project_template_id);setDraftState(restored)
    setVaultInputs({})
    setRetry(false);setError('');setStep(target);setFurthestStep(target)
  }
  if(templates.isLoading||presets.isLoading||users.isLoading||groups.isLoading||vault.isLoading)return <Loading/>
  const locked=busy||validate.isPending||execute.isPending
  const vaultReady=!job?.vault_plan||job.vault_values_saved||job.vault_plan.objects.every(obj=>obj.fields.every(field=>{
    const choice=vaultInputs[field.input_id]
    return field.source==='registry'||choice?.mode==='generate'||Boolean(choice?.value)
  }))
  return <>
    <PageHeader title="Tenant erstellen" description="Geführter, speicherbarer 8-Schritt-Prozess mit sicherer Importvorschau."/>
    {step===0&&Boolean(jobs.data?.length)&&<Card><h2>Gespeicherten Vorgang fortsetzen</h2><div className="compact-list">
      {jobs.data?.filter(value=>value.status!=='completed').map(value=><div key={value.id}><span>{value.draft_data.project_name||'Entwurf'} · {value.status}</span><Button variant="secondary" onClick={()=>resume(value)}>Fortsetzen</Button></div>)}
    </div></Card>}
    <div className="wizard"><aside className="wizard-steps" aria-label="Wizard-Schritte">
      {steps.map(([title,desc,Icon],index)=>{
        const done=index<furthestStep&&index!==step
        return <button key={title} aria-current={index===step?'step':undefined}
          className={`${index===step?'active ':''}${done?'done ':''}${index<=furthestStep?'visited ':''}`}
          onClick={()=>index<=step?setStep(index):void forward(index)}
          disabled={index>furthestStep||locked||!editable(job)}>
          <span className="step-circle">{done?<Check size={16}/>:<Icon size={16}/>}</span>
          <span><strong>{index+1}. {title}</strong><small>{desc}</small></span>
        </button>
      })}
    </aside><Card className="wizard-content">
      {error&&<Notice type="error">{error}</Notice>}{job?.last_error&&<Notice type="error">{job.last_error}</Notice>}
      {step===0&&<WizardTemplate templates={templates.data||[]} selected={templateId} onSelect={chooseTemplate}/>}
      {step===1&&<WizardTenant draft={draft} setDraft={setDraft}/>}
      {step===2&&<><WizardApplication draft={draft} setDraft={setDraft} template={selected}/>{draft.provision_vault&&<Notice type="info">Freigegebene Kombinationen im Vault-Katalog: {Object.entries(catalog.data?.applications||{}).map(([id,app])=>`${id}: ${Object.keys(app.database_types).join(', ')}`).join(' · ')||'Katalog wird geladen.'}</Notice>}</>}
      {step===3&&<><WizardResources draft={draft} setDraft={setDraft} template={draft.resource_overrides?{...selected!,task_templates:draft.resource_overrides.templates.map(x=>String(x.name)),environments:draft.resource_overrides.environments.map(x=>String(x.name))}:selected}/><SshProfilesWizard templateId={templateId} overrides={draft.resource_overrides} bindings={draft.ssh_bindings} onChange={ssh_bindings=>setDraft(value=>({...value,ssh_bindings}))}/><WizardResourceEditor key={templateId} templateId={templateId} draft={draft} setDraft={setDraft}/></>}
      {step===4&&<><WizardPresets draft={draft} setDraft={setDraft} presets={presets.data||[]}/><h3>Vault-Anlage</h3><label className="toggle-row"><input type="checkbox" disabled={!vault.data?.enabled&&!draft.provision_vault} checked={draft.provision_vault} onChange={e=>setDraft(v=>({...v,provision_vault:e.target.checked}))}/><span>Benötigte Vault-Objekte anlegen und den Semaphore-Lesezugang hinterlegen</span></label>{!vault.data?.enabled&&<Notice type="info">Vault ist noch nicht aktiviert. <Link to="/admin/vault">Vault konfigurieren</Link></Notice>}{vault.error&&<Notice type="error">{vault.error.message}</Notice>}</>}
      {step===5&&<WizardAccess draft={draft} setDraft={setDraft} users={users.data||[]} groups={groups.data||[]}/>}
      {step===6&&<><WizardValidation job={job} draft={draft}/>{job?.vault_plan&&<VaultWizard plan={job.vault_plan} inputs={vaultInputs} onChange={setVaultInputs} saved={Boolean(job.vault_values_saved)} progress={job.vault_progress} jobId={job.id} disabled={locked} onResolved={async()=>setJob(await api<CreationJob>(`/admin/creation-jobs/${job.id}`))}/>} {job&&['verification_required','restoring','semaphore_created'].includes(job.status)&&<Notice type="info">Der Vorgang wird anhand des Projektnamens geprüft und fortgesetzt.<label><input type="checkbox" checked={retry} onChange={e=>setRetry(e.target.checked)}/> Falls das Projekt nachweislich fehlt, erneuten Restore ausdrücklich erlauben.</label></Notice>}</>}
      {step===7&&<WizardResult job={job} onOpen={()=>job?.tenant_id&&navigate(`/admin/tenants/${job.tenant_id}`)}/>}
      <div className="wizard-footer">
        {step>0&&step<7&&editable(job)?<Button variant="secondary" disabled={locked} onClick={()=>setStep(value=>value-1)}><ChevronLeft size={16}/>Zurück</Button>:<span/>}
        {step<6&&<Button onClick={()=>void forward(step+1)} loading={busy}>Speichern & weiter<ChevronRight size={16}/></Button>}
        {step===6&&(!job?.validation_result||Boolean(job.validation_result.errors.length)
          ?<Button onClick={()=>void forward(6)} loading={busy||validate.isPending}>Konfiguration erneut validieren</Button>
          :<Button disabled={!vaultReady} onClick={()=>execute.mutate()} loading={execute.isPending}><Rocket size={16}/>{job.status==='validated'?'Projekt verbindlich erstellen':'Vorgang prüfen und fortsetzen'}</Button>)}
        {step===7&&<Button onClick={()=>job?.tenant_id&&navigate(`/admin/tenants/${job.tenant_id}`)}>Tenant öffnen</Button>}
      </div>
    </Card></div>
  </>
}

function WizardApplication({draft,setDraft,template}:{draft:Draft;setDraft:(fn:(value:Draft)=>Draft)=>void;template?:Template}){
  return <><WizardTitle number={3} title="Anwendungen, Datenbanken und Testdaten" text="Alle Werte auswählen, die dieser Tenant später verwenden darf."/>
    <Notice type="info">Die Auswahl begrenzt die Task-Auswahllisten im neuen Semaphore-Projekt und die Portal-Policies. Sie installiert noch keine Anwendung und importiert keine Testdaten. Beim Task-Start wird jeweils eine Anwendung, ein Provider und ein Datensatz gewählt. Ob diese Kombination zusammenpasst, prüft der Stack vor Änderungen am Zielhost.</Notice>
    {optionFields.map(([plural,singular,label])=><WizardOptions key={plural} label={label} variable={singular} options={template?.survey_catalog[singular]||[]} selected={draft[plural]} onChange={values=>setDraft(value=>({...value,[plural]:values}))}/>)}
    <Field label="Standardlaufzeit (Minuten)"><input type="number" min={5} max={1440} value={draft.ttl_minutes} onChange={e=>setDraft(value=>({...value,ttl_minutes:Number(e.target.value)}))}/></Field>
  </>
}
function WizardOptions({label,variable,options,selected,onChange}:{label:string;variable:string;options:unknown[];selected:string[];onChange:(values:string[])=>void}){
  const values=options.filter((value):value is string=>typeof value==='string')
  const unavailable=selected.filter(value=>!values.includes(value))
  return <section className="wizard-options" aria-label={label}>
    <div className="section-heading"><h3>{label}</h3><span>{selected.length} ausgewählt</span></div>
    {values.length?<>
      <div className="button-row"><Button variant="secondary" onClick={()=>onChange(values)}>Alle {label} auswählen</Button><Button variant="ghost" onClick={()=>onChange([])}>Auswahl für {label} leeren</Button></div>
      <div className="check-grid">{values.map(value=><label key={value}><input type="checkbox" checked={selected.includes(value)} onChange={e=>onChange(e.target.checked?[...selected,value]:selected.filter(item=>item!==value))}/><span>{value}</span></label>)}</div>
      {selected.length>0&&<Field label={`Vorgabe für ${label}`} help="Wird in Semaphore-Defaults gespeichert; beim Task-Start sind auch die übrigen freigegebenen Werte wählbar."><select value={selected[0]} onChange={e=>onChange([e.target.value,...selected.filter(value=>value!==e.target.value)])}>{selected.map(value=><option key={value} value={value}>{value}</option>)}</select></Field>}
    </>:<Notice type="info">Die Vorlage enthält keine {variable}-Auswahlliste. Werte zuerst im Quellprojekt ergänzen und die Vorlage erneut importieren.</Notice>}
    {unavailable.length>0&&<Notice type="error">Nicht mehr in der Vorlage vorhanden: {unavailable.join(', ')}. <Button variant="secondary" onClick={()=>onChange(selected.filter(value=>values.includes(value)))}>Fehlende Werte entfernen</Button></Notice>}
  </section>
}

function WizardResourceEditor({templateId,draft,setDraft}:{templateId:string;draft:Draft;setDraft:(fn:(v:Draft)=>Draft)=>void}){
  const query=useQuery({queryKey:['template-resources',templateId],queryFn:()=>api<Resources>(`/admin/project-templates/${templateId}/resources`)})
  const [text,setText]=useState(''),[error,setError]=useState(''),[applied,setApplied]=useState(false)
  useEffect(()=>{if(query.data)setText(JSON.stringify(draft.resource_overrides||query.data,null,2))},[query.data])
  const apply=()=>{try{const value=JSON.parse(text) as Resources;for(const key of ['templates','environments','repositories','inventories'] as const){if(!Array.isArray(value[key])||value[key].some(x=>!x||typeof x!=='object'||!x.name))throw new Error(`${key}: Liste benannter Objekte erforderlich.`)}setDraft(v=>({...v,resource_overrides:value,task_template_names:value.templates.map(x=>String(x.name)),environment_names:value.environments.map(x=>String(x.name))}));setError('');setApplied(true)}catch(e){setError(e instanceof Error?e.message:'Ungültige Ressourcen.')}}
  return <div><h3>Kopie vor dem Restore bearbeiten</h3><p>Variablengruppen, Repository/Branch, Inventories und Task-Zuordnungen können hier angepasst werden. Änderungen zuerst übernehmen und danach die Auswahl oben prüfen. Tenant und Scope werden aus Schritt 2 in Semaphore-Defaults geschrieben. Zugangsdaten im erstellten Projekt neu setzen.</p>{query.isLoading?<Loading/>:query.error?<Notice type="error">{query.error.message}</Notice>:<><Field label="Ressourcen der Projektkopie (JSON)"><textarea className="code-editor" rows={22} value={text} onChange={e=>{setText(e.target.value);setApplied(false)}}/></Field><Button variant="secondary" onClick={apply}>Ressourcen übernehmen</Button>{applied&&<Notice type="success">Ressourcen übernommen.</Notice>}</>}{error&&<Notice type="error">{error}</Notice>}</div>
}

function WizardTitle({number,title,text}:{number:number;title:string;text:string}){return <div className="wizard-title"><span>Schritt {number} von 8</span><h2>{title}</h2><p>{text}</p></div>}
function WizardTemplate({templates,selected,onSelect}:{templates:Template[];selected:string;onSelect:(id:string)=>void}){return <><WizardTitle number={1} title="Projektvorlage auswählen" text="Das Originalprojekt bleibt unverändert; gearbeitet wird auf einer Kopie des Backups."/><div className="choice-grid">{templates.map(item=><button key={item.id} className={`choice-card ${selected===item.id?'selected':''}`} onClick={()=>onSelect(item.id)}><Layers3/><div><strong>{item.name}</strong><span>{item.description||`${item.task_templates.length} Task Templates`}</span></div>{selected===item.id&&<CircleCheck/>}</button>)}</div>{!templates.length&&<Notice type="info">Legen Sie zuerst unter „Projektvorlagen“ eine Vorlage an.</Notice>}</>}
function WizardTenant({draft,setDraft}:{draft:Draft;setDraft:(fn:(v:Draft)=>Draft)=>void}){const set=(key:keyof Draft,value:unknown)=>setDraft(v=>({...v,[key]:value}));return <><WizardTitle number={2} title="Tenant konfigurieren" text="Technische Kennung und Anzeigename werden getrennt geführt."/><div className="form-grid columns-2"><Field label="Semaphore-Projektname"><input value={draft.project_name} onChange={e=>set('project_name',e.target.value)}/></Field><Field label="Technische Tenant-ID" help="2–31 Zeichen: a-z, 0-9 und Bindestrich"><input value={draft.tenant_slug} onChange={e=>set('tenant_slug',e.target.value.toLowerCase().replace(/[^a-z0-9-]/g,''))}/></Field><Field label="Runtime-Scope (runtime_scope_id)" help="Gemeinsam mit tenant_slug fest in Semaphore-Defaults gespeichert."><input value={draft.runtime_scope_id} onChange={e=>set('runtime_scope_id',e.target.value)}/></Field><Field label="Anzeigename"><input value={draft.display_name} onChange={e=>set('display_name',e.target.value)}/></Field><Field label="Beschreibung"><input value={draft.description} onChange={e=>set('description',e.target.value)}/></Field></div></>}
function WizardResources({draft,setDraft,template}:{draft:Draft;setDraft:(fn:(v:Draft)=>Draft)=>void;template?:Template}){const toggle=(key:'task_template_names'|'environment_names',name:string)=>setDraft(v=>({...v,[key]:v[key].includes(name)?v[key].filter(x=>x!==name):[...v[key],name]}));return <><WizardTitle number={4} title="Task Templates und Ressourcen" text="Nicht ausgewählte Inhalte werden nur aus der neuen Kopie entfernt."/><h3>Task Templates</h3><div className="check-grid">{template?.task_templates.map(name=><label key={name}><input type="checkbox" checked={draft.task_template_names.includes(name)} onChange={()=>toggle('task_template_names',name)}/><span>{name}</span></label>)}</div><h3>Variablengruppen</h3><div className="check-grid">{template?.environments.map(name=><label key={name}><input type="checkbox" checked={draft.environment_names.includes(name)} onChange={()=>toggle('environment_names',name)}/><span>{name}</span></label>)}</div><Notice type="info">Zeitpläne und Webhooks werden im Zielprojekt grundsätzlich nicht übernommen.</Notice></>}
function WizardPresets({draft,setDraft,presets}:{draft:Draft;setDraft:(fn:(v:Draft)=>Draft)=>void;presets:Preset[]}){const toggle=(id:string)=>setDraft(v=>({...v,preset_ids:v.preset_ids.includes(id)?v.preset_ids.filter(x=>x!==id):[...v.preset_ids,id]}));return <><WizardTitle number={5} title="Variablengruppen und Presets" text="Preset-Werte werden in die neue Tenant-Gruppe gemischt; tenant-spezifische Werte haben Vorrang."/><div className="choice-grid">{presets.map(item=><button key={item.id} className={`choice-card ${draft.preset_ids.includes(item.id)?'selected':''}`} onClick={()=>toggle(item.id)}><FileCheck2/><div><strong>{item.name}</strong><span>{item.category} · {item.description}</span></div>{draft.preset_ids.includes(item.id)&&<Check/>}</button>)}</div></>}
function WizardAccess({draft,setDraft,users,groups}:{draft:Draft;setDraft:(fn:(v:Draft)=>Draft)=>void;users:User[];groups:Group[]}){const toggle=(kind:'user_id'|'group_id',id:string)=>setDraft(v=>{const has=v.access_assignments.some(x=>x[kind]===id);return{...v,access_assignments:has?v.access_assignments.filter(x=>x[kind]!==id):[...v.access_assignments,{[kind]:id,role_code:'operator'}]}});return <><WizardTitle number={6} title="Benutzer und Berechtigungen" text="Operatoren dürfen die initial freigegebenen Tasks sehen, starten und abbrechen."/><div className="access-columns"><div><h3>Benutzer</h3><div className="check-grid">{users.filter(u=>u.is_active).map(user=><label key={user.id}><input type="checkbox" checked={draft.access_assignments.some(x=>x.user_id===user.id)} onChange={()=>toggle('user_id',user.id)}/><span>{user.display_name}<small>{user.email}</small></span></label>)}</div></div><div><h3>Gruppen</h3><div className="check-grid">{groups.map(group=><label key={group.id}><input type="checkbox" checked={draft.access_assignments.some(x=>x.group_id===group.id)} onChange={()=>toggle('group_id',group.id)}/><span>{group.name}</span></label>)}</div></div></div><label className="toggle-row"><input type="checkbox" checked={draft.create_default_policies} onChange={e=>setDraft(v=>({...v,create_default_policies:e.target.checked}))}/><span><strong>Sichere Initial-Policies erzeugen</strong><small>Tenant/Scope in Semaphore-Defaults, Anwendung/DB aus Survey, TTL 5–1440</small></span></label><label className="toggle-row"><input type="checkbox" checked={draft.activate_after_creation} onChange={e=>setDraft(v=>({...v,activate_after_creation:e.target.checked}))}/><span><strong>Nach erfolgreicher Konfiguration aktivieren</strong><small>Nur wenn Projekt und mindestens eine Policy vollständig sind</small></span></label></>}
function WizardValidation({job,draft}:{job:CreationJob|null;draft:Draft}){
  const result=job?.validation_result
  return <><WizardTitle number={7} title="Konfiguration validieren" text="Die Vorschau wird mit der aktuellen Semaphore-Projektliste abgeglichen."/>
    <div className="review-grid"><div><span>Projektname</span><strong>{draft.project_name}</strong></div><div><span>Tenant</span><strong>{draft.tenant_slug}</strong></div><div><span>Tasks</span><strong>{draft.task_template_names.length}</strong></div><div><span>Zugriffe</span><strong>{draft.access_assignments.length}</strong></div>
      {optionFields.map(([plural,,label])=><div key={plural}><span>{label}</span><strong>{draft[plural].join(', ')||'Keine Survey-Auswahl'}</strong></div>)}
    </div>
    {Boolean(job?.credential_plan?.length)&&<section aria-label="Geprüfte SSH-Zuordnungen"><h3>SSH-Zugangsprofile</h3>{job?.credential_plan?.map(item=><p key={item.profile.id}><strong>{item.name}</strong> · Version {item.profile.vault_version} · {item.fingerprint}<br/>{item.bindings.map(binding=>`${binding.name}: ${binding.targets.join(', ')}`).join(' · ')}{job.credential_progress?.installed?' · Übertragen':''}</p>)}</section>}
    {!result?<Notice type="info">Der Entwurf wurde geändert. Vor der Erstellung erneut validieren.</Notice>:result.errors.length?<Notice type="error"><strong>Validierung fehlgeschlagen</strong><ul>{result.errors.map(item=><li key={item}>{item}</li>)}</ul></Notice>:<Notice type="success">Struktur- und Verbindungsprüfung bestanden. Das Quellprojekt wird nicht verändert. Deployments und Datenimporte starten erst mit einem Task.</Notice>}
    {Boolean(result?.warnings.length)&&<Notice type="info"><ul>{result?.warnings.map(item=><li key={item}>{item}</li>)}</ul></Notice>}
  </>
}
function WizardResult({job,onOpen}:{job:CreationJob|null;onOpen:()=>void}){return <div className="success-screen"><div className="success-icon"><CircleCheck size={42}/></div><span>ERSTELLUNG ABGESCHLOSSEN</span><h2>Tenant-Projekt wurde registriert</h2><p>Semaphore-Projekt und Portalzuordnung wurden erfolgreich verknüpft. Prüfen Sie jetzt Key Store, Vault-Zugänge, Repository und Inventory im Semaphore-Projekteditor.</p><div className="review-grid"><div><span>Status</span><strong>{job?.status}</strong></div><div><span>Portal-Tenant</span><strong>{job?.tenant_id}</strong></div></div><Button onClick={onOpen}>Tenant öffnen</Button></div>}
