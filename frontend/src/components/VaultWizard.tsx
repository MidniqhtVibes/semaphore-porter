import { useState } from 'react'
import { api } from '../api'
import { Button, Field, Notice } from './ui'
import type { VaultInputs, VaultPlan, VaultProgress } from '../vault'

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
  return <section aria-label="Vault-Objekte"><h3>Vault-Objekte und Secret-Werte</h3>
    <Notice type="info">Vor der Anlage werden alle folgenden Objekte auf Existenz geprüft. Vorhandene Objekte werden nicht überschrieben. Generierte Werte werden erst bei der Ausführung erzeugt.</Notice>
    {saved&&<Notice type="info">Werte sind für diesen Vorgang bereits geschützt gespeichert. Die Wiederaufnahme verwendet dieselben Werte.</Notice>}
    {error&&<Notice type="error">{error}</Notice>}
    {plan.objects.map(obj=>{
      const state=progress?.objects[obj.path]?.state
      return <div className="vault-object" key={obj.path}><h4>{obj.id}</h4><p><code>{plan.kv_mount}/{obj.path}</code>{state&&<span> · {state==='created'?'Angelegt':state==='pending'?'Ausstehend':'Schreibergebnis prüfen'}</span>}</p>
        <div className="form-grid columns-2">{obj.fields.map(field=>{
          if(field.source==='registry')return <p key={field.input_id}>{field.key}: zentraler Registry-Zugang</p>
          const choice=inputs[field.input_id]||{mode:'manual' as const,value:''}
          return <div key={field.input_id}><Field label={`${obj.id}: ${field.key} – Quelle`}><select disabled={saved||disabled} value={choice.mode} onChange={e=>onChange({...inputs,[field.input_id]:{mode:e.target.value as 'manual'|'generate',value:''}})}><option value="manual">Vorhandenen Wert eingeben</option>{field.generate&&<option value="generate">Neuen Wert generieren lassen</option>}</select></Field>
            {choice.mode==='manual'&&!saved&&<Field label={`${obj.id}: ${field.key}`} help={field.hex?'Hex-Zeichenfolge, gerade Länge, mindestens 16 Zeichen.':`${field.min_length}–${field.max_length} Zeichen.`}><input disabled={disabled} type="password" autoComplete="new-password" value={choice.value||''} onChange={e=>onChange({...inputs,[field.input_id]:{mode:'manual',value:e.target.value}})}/></Field>}
            {choice.mode==='generate'&&obj.id==='azubiorga'&&<Notice type="info">Nur verwenden, wenn dein Image neue Crypto-Werte erlaubt. Vorgegebene Image-Werte bitte eingeben.</Notice>}
          </div>
        })}</div>
        {['writing','uncertain'].includes(state||'')&&<div><label><input type="checkbox" checked={confirmations[obj.path]||false} onChange={e=>setConfirmations(v=>({...v,[obj.path]:e.target.checked}))}/> Ich habe in Vault geprüft, ob dieses Objekt durch genau diesen Vorgang angelegt wurde oder vollständig fehlt.</label><div className="button-row"><Button variant="secondary" disabled={disabled||busy||!confirmations[obj.path]} onClick={()=>void resolve(obj.path,'created_by_this_job')}>Eigene Anlage bestätigen</Button><Button variant="secondary" disabled={disabled||busy||!confirmations[obj.path]} onClick={()=>void resolve(obj.path,'absent')}>Abwesenheit bestätigen</Button></div></div>}
      </div>
    })}
  </section>
}
