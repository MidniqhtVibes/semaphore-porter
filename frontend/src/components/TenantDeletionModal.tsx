import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Badge, Button, Field, Loading, Modal, Notice } from './ui'

type Preview = {
  revision: string; running: boolean; last_error: string | null
  progress: {started?: boolean; project?: string; vault?: Record<string, string>}
  deployment_blockers?: string[]
  plan: {tenant_slug: string; blockers: string[]; preserved: string[]
    semaphore: {id: number; name: string; owned: boolean} | null
    vault: Array<{path: string; versions: number; identity: {kv_mount: string}}>
    portal: {tasks: number; runs: number; memberships: number}}
}

export function TenantDeletionModal({tenantId, onClose, onDeleted}: {tenantId: string; onClose: () => void; onDeleted: () => void}) {
  const [confirmation, setConfirmation] = useState(''), [deployments, setDeployments] = useState(false)
  const preview = useQuery({queryKey: ['tenant-deletion', tenantId], queryFn: () => api<Preview>(`/admin/tenants/${tenantId}/deletion/preview`, {method: 'POST'}), retry: false, refetchOnWindowFocus: false})
  const remove = useMutation({mutationFn: () => api(`/admin/tenants/${tenantId}/deletion/execute`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({revision: preview.data?.revision, confirm_slug: confirmation, deployments_confirmed: deployments})
  }), onSuccess: onDeleted, onError: () => {void preview.refetch()}})
  const cancel = useMutation({mutationFn: () => api(`/admin/tenants/${tenantId}/deletion`, {method: 'DELETE'}), onSuccess: onClose})
  const state = preview.data, busy = remove.isPending || cancel.isPending || Boolean(state?.running)
  const blockers = [...(state?.plan.blockers || []), ...(state?.deployment_blockers || [])]
  return <Modal title="Tenant vollständig entfernen" onClose={() => {if (!busy) onClose()}}>
    <p>Eigene Ressourcen in Semaporter, Semaphore und Vault sowie der tenantbezogene Verlauf werden dauerhaft entfernt. Es werden keine Deployments gestoppt.</p>
    {preview.isLoading && <Loading/>}
    {preview.error && <Notice type="error">{preview.error.message}</Notice>}
    {cancel.error && <Notice type="error">{cancel.error.message}</Notice>}
    {(remove.error || state?.last_error) && <Notice type="error">{remove.error?.message || state?.last_error} Die Bereinigung bleibt gespeichert und kann fortgesetzt werden.</Notice>}
    {state && <>
      {state.progress.started && <Notice>Die Bereinigung wurde begonnen. Der Tenant ist deaktiviert, damit keine neuen Tasks starten.</Notice>}
      {!!blockers.length && <Notice type="error"><ul>{blockers.map((item, index) => <li key={index}>{item}</li>)}</ul></Notice>}
      <h3>Diese Ressourcen werden entfernt</h3>
      <ul className="tenant-cleanup-resources"><li>{state.plan.portal.tasks} Task-Freigaben, {state.plan.portal.runs} Ausführungen und {state.plan.portal.memberships} Zugriffszuordnungen einschließlich Tenant-Verlauf</li>
        {state.plan.semaphore?.owned && <li>Semaphore-Projekt „{state.plan.semaphore.name}“ (#{state.plan.semaphore.id}) einschließlich seiner Schlüssel, Variablengruppen und Task-Historie</li>}
        {state.plan.vault.map(item => <li key={`${item.identity.kv_mount}/${item.path}`}><code>{item.identity.kv_mount}/{item.path}</code> · alle Secret-Versionen ({item.versions}) und Metadaten</li>)}</ul>
      {!state.plan.vault.length && <p className="muted">Keine von Semaporter belegten Vault-Anlagen vorhanden. Andere Vault-Pfade werden nicht gelöscht.</p>}
      <h3>Bleibt erhalten</h3><div className="badge-row">{state.plan.preserved.map(item => <Badge key={item}>{item}</Badge>)}</div>
      <Field label="Deployments geprüft"><label className="toggle-row"><input type="checkbox" checked={deployments} onChange={e => setDeployments(e.target.checked)} disabled={busy}/><span>Ich habe alle Zielserver geprüft: Temporäre Deployments sind regulär ausgelaufen; dauerhafte Deployments wurden bewusst beendet. Auch nicht überwachte Deployments sind geprüft.</span></label></Field>
      <p className="muted">Die Anwendung prüft bekannte Hostmeldungen und laufende Semaphore-Tasks zusätzlich. Ohne Hostüberwachung ist deine Prüfung der Zielserver erforderlich.</p>
      <Field label={`Zur Bestätigung „${state.plan.tenant_slug}“ eingeben`}><input value={confirmation} onChange={e => setConfirmation(e.target.value)} disabled={busy}/></Field>
    </>}
    <div className="modal-actions"><Button variant="secondary" disabled={busy} onClick={onClose}>Schließen</Button>{state?.progress.started && !state.progress.project && !Object.keys(state.progress.vault || {}).length && <Button variant="secondary" disabled={busy || preview.isFetching} onClick={() => cancel.mutate()}>Bereinigung verwerfen</Button>}<Button variant="secondary" disabled={busy} loading={preview.isFetching} onClick={() => {void preview.refetch()}}>Vorschau aktualisieren</Button><Button variant="danger" loading={remove.isPending} disabled={!state || busy || preview.isFetching || Boolean(preview.error) || !!blockers.length || confirmation !== state.plan.tenant_slug || !deployments} onClick={() => remove.mutate()}>{state?.progress.started ? 'Bereinigung fortsetzen' : 'Tenant endgültig entfernen'}</Button></div>
  </Modal>
}
