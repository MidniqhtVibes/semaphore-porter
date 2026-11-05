import { useState } from 'react'
import { AppWindow, Database, KeyRound } from 'lucide-react'
import { api } from '../api'
import { Badge, Button, Field, Notice } from './ui'
import type { VaultInputs, VaultPlan, VaultProgress, VaultSecretField } from '../vault'

const objectNames:Record<string,string> = {azubiorga:'AzubiOrga',wordpress:'WordPress',postgresql:'PostgreSQL',mysql:'MySQL',mariadb:'MariaDB'}
const fieldNames:Record<string,string> = {crypto_secret:'Anwendungsschlüssel',crypto_salt:'Crypto-Salt',registry_password:'Registry-Zugang',postgres_password:'Datenbankpasswort',mysql_password:'Datenbankpasswort',mariadb_password:'Datenbankpasswort'}
function fieldHelp(field:VaultSecretField){
  if(field.hex)return `Hexadezimaler Wert mit gerader Zeichenanzahl (${field.min_length}–${field.max_length} Zeichen).`
  return `${field.min_length}–${field.max_length} Zeichen.${field.forbid_whitespace?' Keine Leerzeichen.':''}`
}

export function VaultWizard({plan,inputs,onChange,saved,progress,jobId,onResolved,disabled}:{
  plan:VaultPlan;inputs:VaultInputs;onChange:(value:VaultInputs)=>void;saved:boolean
  progress?:VaultProgress|null;jobId:string;onResolved:()=>Promise<void>;disabled:boolean
}){
  const [error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [confirmations,setConfirmations]=useState<Record<string,boolean>>({})
  const resolve=async(path:string,decision:string)=>{
    setBusy(true);setError('')
    try{await api(`/admin/creation-jobs/${jobId}/vault/resolve`,{method:'POST',body:JSON.stringify({path,decision,confirm_checked_in_vault:true})});await onResolved()}
    catch(e){setError(e instanceof Error?e.message:'Prüfergebnis konnte nicht gespeichert werden.')}
    finally{setBusy(false)}
  }
  return <section className="vault-wizard" aria-label="Vault-Objekte"><div className="vault-section-heading"><KeyRound size={21}/><div><h3>Zugangsdaten für Vault</h3><p>Lege die benötigten Werte für Anwendungen und Datenbanken fest.</p></div></div>
    <Notice type="info">Vor dem Speichern prüfen wir alle Zielpfade. Vorhandene Einträge werden nicht überschrieben. Neue Werte entstehen erst bei der Erstellung.</Notice>
    {saved&&<Notice type="info">Werte sind für diesen Vorgang bereits geschützt gespeichert. Die Wiederaufnahme verwendet dieselben Werte.</Notice>}
    {error&&<Notice type="error">{error}</Notice>}
    {plan.objects.map(obj=>{
      const state=progress?.objects[obj.path]?.state
      const label=objectNames[obj.id]||obj.id
      const Icon=obj.kind==='provider'?Database:AppWindow
      const registry=plan.registries?.find(item=>item.application_id===obj.id)
      const fields=obj.fields.filter(field=>field.source!=='registry')
      return <article className="vault-object" key={obj.path} aria-label={`Vault-Zugangsdaten für ${label}`}>
        <header className="vault-object-heading"><div className="vault-object-title"><span className="vault-object-icon"><Icon size={20}/></span><div><span className="vault-object-kind">{obj.kind==='provider'?'Datenbank':'Anwendung'}</span><h4>{label}</h4></div></div>
          {state&&<Badge tone={state==='created'?'success':['writing','uncertain'].includes(state)?'warning':'neutral'}>{state==='created'?'Angelegt':state==='pending'?'Ausstehend':'Ergebnis prüfen'}</Badge>}
        </header>
        <div className="vault-object-path"><span>Ablage in Vault</span><code>{plan.kv_mount}/{obj.path}</code></div>
        {obj.fields.filter(field=>field.source==='registry').map(field=><div className="vault-registry-source" key={field.input_id}>
          <div><strong>{fieldNames[field.key]||field.key}</strong><span>{registry?registry.name:'Vorhandener Registry-Zugang der Anwendung'}{registry&&` · ${registry.host}`}</span></div><Badge tone="info">Wird übernommen</Badge>
        </div>)}
        {fields.length>0&&<div className="vault-secret-grid">{fields.map(field=>{
          const choice=inputs[field.input_id]||{mode:'manual' as const,value:''}
          const fieldLabel=fieldNames[field.key]||field.key
          return <div className="vault-secret-field" key={field.input_id}>
            <div className="vault-secret-heading"><strong>{fieldLabel}</strong><code>{field.key}</code></div>
            {obj.id==='azubiorga'&&['crypto_secret','crypto_salt'].includes(field.key)&&<p className="vault-secret-description">Bei bestehenden Images den vorgegebenen Wert aus der Anwendungskonfiguration übernehmen.</p>}
            <Field label={`${label}: ${fieldLabel} – Bereitstellung`}><select disabled={saved||disabled} value={choice.mode} onChange={e=>onChange({...inputs,[field.input_id]:{mode:e.target.value as 'manual'|'generate',value:''}})}><option value="manual">Vorhandenen Wert verwenden</option>{field.generate&&<option value="generate">Neuen Wert erzeugen</option>}</select></Field>
            {choice.mode==='manual'&&!saved&&<Field label={`${label}: ${fieldLabel}`} help={fieldHelp(field)}><input disabled={disabled} type="password" autoComplete="new-password" maxLength={field.max_length} value={choice.value||''} onChange={e=>onChange({...inputs,[field.input_id]:{mode:'manual',value:e.target.value}})}/></Field>}
            {saved?<p className="vault-field-note">Für diesen Vorgang geschützt gespeichert.</p>:choice.mode==='generate'&&<p className="vault-field-note">Wird bei der Erstellung erzeugt und in Vault gespeichert.</p>}
          </div>
        })}</div>}
        {obj.id==='azubiorga'&&fields.some(field=>inputs[field.input_id]?.mode==='generate')&&<Notice type="info">Nur verwenden, wenn dein Image neue Crypto-Werte erlaubt. Vorgegebene Image-Werte bitte eingeben.</Notice>}
        {['writing','uncertain'].includes(state||'')&&<div className="vault-object-resolution"><label className="toggle-row"><input type="checkbox" disabled={disabled||busy} checked={confirmations[obj.path]||false} onChange={e=>setConfirmations(v=>({...v,[obj.path]:e.target.checked}))}/> Ich habe in Vault geprüft, ob dieses Objekt durch genau diesen Vorgang angelegt wurde oder vollständig fehlt.</label><div className="button-row"><Button variant="secondary" disabled={disabled||busy||!confirmations[obj.path]} onClick={()=>void resolve(obj.path,'created_by_this_job')}>Eigene Anlage bestätigen</Button><Button variant="secondary" disabled={disabled||busy||!confirmations[obj.path]} onClick={()=>void resolve(obj.path,'absent')}>Abwesenheit bestätigen</Button></div></div>}
      </article>
    })}
  </section>
}
