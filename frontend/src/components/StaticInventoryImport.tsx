import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api'
import { Button, Field, Notice } from './ui'

type Inventory = Record<string, unknown>
type Preview = {targets: string[]; login: string}

export function StaticInventoryImport({inventory, profileId, onApply}: {
  inventory: Inventory; profileId?: string; onApply: (value: Inventory) => void
}) {
  const name = String(inventory.name)
  const [content, setContent] = useState('')
  const [format, setFormat] = useState(/\.ya?ml$/i.test(String(inventory.inventory)) ? 'static-yaml' : 'static')
  const [fileError, setFileError] = useState('')
  const [reading, setReading] = useState(false)
  const generation = useRef(0)
  const preview = useMutation({
    mutationFn: (values: {profile_id: string; inventory_type: string; content: string}) =>
      api<Preview>('/admin/credentials/inventory-preview', {method: 'POST', body: JSON.stringify(values)}),
  })
  const resetPreview = preview.reset
  useEffect(() => {resetPreview()}, [profileId, resetPreview])
  const normalize = (value: string) => value.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n')
  const checked = preview.isSuccess && preview.variables.profile_id === profileId
    && preview.variables.content === content && preview.variables.inventory_type === format
  const apply = () => {
    if (!checked || reading) return
    const value: Inventory = {...inventory, type: format, inventory: content}
    delete value.repository
    delete value.repository_id
    onApply(value)
  }
  return <section className="card" aria-label={`Datei-Inventory ${name}`}>
    <h4>{name}: statische Hostliste übernehmen</h4>
    <p>Quelle: <code>{String(inventory.inventory)}</code>. Lade die INI-/YAML-Datei aus dem Repository herunter oder füge ihren Inhalt ein.
      Die Kopie wird im neuen Semaphore-Projekt gespeichert. Spätere Änderungen im Repository werden nicht automatisch übernommen.</p>
    {!profileId && <Notice type="info">Wähle oben zuerst ein Host-SSH-Profil für dieses Inventory. Damit werden Benutzer und freigegebene Zielhosts geprüft.</Notice>}
    <div className="form-grid columns-2">
      <Field label={`Datei für ${name}`} help="INI oder YAML, maximal 500 KB. Keine Schlüssel oder Passwörter hochladen.">
        <input type="file" accept=".ini,.yaml,.yml,.txt" onChange={async event => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (!file) return
          const current = ++generation.current
          setFileError(''); preview.reset(); setReading(true)
          try {
            if (file.size > 500_000) throw new Error('Die Inventory-Datei darf maximal 500 KB groß sein.')
            const value = normalize(await file.text())
            if (current !== generation.current) return
            if (value.includes('\0')) throw new Error('Bitte eine INI-/YAML-Textdatei auswählen.')
            setContent(value)
            setFormat(/\.ya?ml$/i.test(file.name) ? 'static-yaml' : 'static')
          } catch (error) {
            if (current === generation.current) setFileError(error instanceof Error ? error.message : 'Datei konnte nicht gelesen werden.')
          } finally {
            if (current === generation.current) setReading(false)
          }
        }}/>
      </Field>
      <Field label={`Format für ${name}`}><select value={format} onChange={event => {setFormat(event.target.value); preview.reset()}}>
        <option value="static">INI</option><option value="static-yaml">YAML</option>
      </select></Field>
    </div>
    <Field label={`Inventory-Inhalt für ${name}`}><textarea className="code-editor" rows={8} value={content} onChange={event => {
      generation.current++; setReading(false); setContent(normalize(event.target.value)); setFileError(''); preview.reset()
    }}/></Field>
    {fileError && <Notice type="error">{fileError}</Notice>}
    {preview.error && <Notice type="error">{preview.error.message}</Notice>}
    {checked && <Notice type="success">Geprüft: {preview.data.targets.join(', ')} · SSH-Benutzer {preview.data.login}.
      Die Prüfung bestätigt die Profilfreigabe; eine SSH-Verbindung wird dabei nicht aufgebaut.</Notice>}
    <div className="button-row">
      <Button type="button" variant="secondary" disabled={!profileId || !content.trim() || reading || Boolean(fileError)} loading={preview.isPending}
        onClick={() => {if (profileId) preview.mutate({profile_id: profileId, inventory_type: format, content})}}>Hostliste prüfen</Button>
      <Button type="button" disabled={!checked || reading || Boolean(fileError)} onClick={apply}>Als statisches Inventory übernehmen</Button>
    </div>
  </section>
}
