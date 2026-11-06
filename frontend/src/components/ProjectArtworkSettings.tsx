import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import type { ProjectArtworkConfig, Tenant } from '../types'
import { ProjectArtwork, projectMarks } from './ProjectArtwork'
import { Button, Card, Field, Notice } from './ui'

export function ProjectArtworkSettings({tenant}: {tenant:Tenant}) {
  const qc=useQueryClient(),[value,setValue]=useState<ProjectArtworkConfig>(tenant.project_artwork||{mode:'auto',marks:[]})
  const [file,setFile]=useState<File|null>(null),[message,setMessage]=useState('')
  const saved=(config:ProjectArtworkConfig)=>{setValue(config);setMessage('Projektlogo gespeichert.');void qc.invalidateQueries({queryKey:['admin-tenant',tenant.id]});void qc.invalidateQueries({queryKey:['portal-tenants']})}
  const save=useMutation({mutationFn:()=>api<ProjectArtworkConfig>(`/admin/tenants/${tenant.id}/artwork`,{method:'PUT',body:JSON.stringify({mode:value.mode||'auto',marks:value.marks||[]})}),onSuccess:saved})
  const upload=useMutation({mutationFn:()=>{const body=new FormData();if(file)body.append('file',file);return api<ProjectArtworkConfig>(`/admin/tenants/${tenant.id}/logo`,{method:'PUT',body})},onSuccess:config=>{saved(config);setFile(null)}})
  const remove=useMutation({mutationFn:()=>api<ProjectArtworkConfig>(`/admin/tenants/${tenant.id}/logo`,{method:'DELETE'}),onSuccess:saved})
  const busy=save.isPending||upload.isPending||remove.isPending
  return <Card><h2>Projektlogo</h2><p className="muted">Logos erscheinen rechts auf der Projektkachel und blenden zur Mitte hin aus.</p>
    <div className="detail-grid"><div><Field label="Darstellung"><select value={value.mode||'auto'} onChange={event=>setValue({...value,mode:event.target.value as ProjectArtworkConfig['mode']})}>
      <option value="auto">Automatisch nach Anwendung und Datenbank</option><option value="selected">Mitgelieferte Logos auswählen</option><option value="custom">Eigenes Logo</option><option value="none">Kein Logo</option></select></Field>
      {value.mode==='selected'&&<div className="check-grid project-logo-options">{projectMarks.map(mark=><label key={mark.id}><input type="checkbox" checked={value.marks?.includes(mark.id)||false}
        onChange={event=>setValue({...value,marks:event.target.checked?[...value.marks||[],mark.id]:(value.marks||[]).filter(id=>id!==mark.id)})}/><span>{mark.name}</span></label>)}</div>}
      <Button variant="secondary" disabled={busy||(value.mode==='custom'&&!value.image_version)} loading={save.isPending} onClick={()=>save.mutate()}>Auswahl speichern</Button>
    </div><div className="project-card project-artwork-preview" aria-label="Vorschau der Projektkachel"><ProjectArtwork tenant={{...tenant,project_artwork:value}}/><h2>{tenant.display_name}</h2><p>Vorschau</p></div></div>
    <Field label="Eigenes Logo hochladen" help="PNG, JPEG, WebP oder GIF; maximal 5 MB und 1024 × 1024 Pixel. Transparente Hintergründe und Animationen bleiben erhalten.">
      <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" disabled={busy} onChange={event=>{setMessage('');setFile(event.target.files?.[0]||null)}}/></Field>
    {file&&file.size>5*1024*1024&&<Notice type="error">Das Logo darf maximal 5 MB groß sein.</Notice>}
    <div className="button-row"><Button disabled={busy||!file||file.size>5*1024*1024} loading={upload.isPending} onClick={()=>upload.mutate()}>Logo hochladen und verwenden</Button>
      {value.image_version&&<Button variant="danger" disabled={busy} onClick={()=>remove.mutate()}>Hochgeladenes Logo entfernen</Button>}</div>
    {[save.error,upload.error,remove.error].filter(Boolean).map((error,index)=><Notice type="error" key={index}>{error?.message}</Notice>)}{message&&<Notice type="success">{message}</Notice>}
  </Card>
}
