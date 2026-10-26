import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { ArrowLeft, CheckCircle2, ImagePlus, Palette, RotateCcw, Save, Type, X } from 'lucide-react'
import { Button, Field, Notice } from '../components/ui'
import { DesignLivePreview, type PreviewPage } from './DesignLivePreview'
import { LOGO_ASSETS } from './logoAssets'
import type { NavigationMode } from '../components/navigation'
import { ALPHA_COLORS, BUILTIN_THEMES, COLOR_KEYS, DEFAULT_COPY, DEFAULT_LEGAL, MAX_THEME_IMAGE_BYTES, MAX_LOGIN_BACKGROUND_BLUR, THEME_IMAGE_TYPES, contrast, parseThemeFile, resolveCustomTheme, type ColorKey, type ThemeCopy, type ThemeFile } from './themes'

const mainColors: ColorKey[]=['bg','header','surface','text','muted','accent','primary','on-primary','nav-indicator','border','success','warning','danger']
const colorLabels: Record<ColorKey,string> = {
  bg:'Seitenhintergrund',header:'Navigation',surface:'Karten','surface-alt':'Eingabeflächen','surface-soft':'Nebenflächen',hover:'Hover-Fläche',border:'Rahmen','border-soft':'Dezente Rahmen',text:'Haupttext',muted:'Begleittext',accent:'Links und Fokus','accent-hover':'Link bei Hover','accent-soft':'Akzentfläche','accent-border':'Akzentrahmen','nav-indicator':'Aktiver Menüpunkt',primary:'Primäre Aktion','primary-hover':'Aktion bei Hover','primary-border':'Aktionsrahmen','on-primary':'Text auf Aktion',success:'Erfolg','success-soft':'Erfolgsfläche','success-border':'Erfolgsrahmen',warning:'Warnung','warning-soft':'Warnfläche','warning-border':'Warnrahmen',danger:'Fehler','danger-soft':'Fehlerfläche','danger-border':'Fehlerrahmen','danger-hover':'Fehleraktion bei Hover','on-danger':'Text auf Fehleraktion','on-emphasis':'Hervorgehobener Text',overlay:'Dialoghintergrund',selection:'Textauswahl','on-selection':'Text in Auswahl',
}
const copyLabels: Record<keyof ThemeCopy,string> = {title:'Portalname',subtitle:'Untertitel',headline:'Überschrift der Anmeldung',emphasis:'Hervorgehobene Zeile',intro:'Beschreibung der Anmeldung',welcome:'Begrüßung',loginHint:'Hinweis zur Anmeldung'}
const palettes = [
  {name:'Ozean',primary:'#176e8c',light:'#176e8c',dark:'#7dd3ef'},
  {name:'Iris',primary:'#6941c6',light:'#6941c6',dark:'#c3a6ff'},
  {name:'Wald',primary:'#286b45',light:'#286b45',dark:'#9bd7ad'},
  {name:'Terrakotta',primary:'#a13c32',light:'#a13c32',dark:'#ffb4a6'},
]
export { createDraft } from './themes'

export function DesignCreator({initial,onSave,onClose,initialMode='admin'}:{initial:ThemeFile;onSave:(value:ThemeFile)=>void;onClose:()=>void;initialMode?:NavigationMode}) {
  const [draft,setDraft]=useState<ThemeFile>(()=>structuredClone(initial))
  const [error,setError]=useState(''), [loading,setLoading]=useState<'logo'|'loginBackground'|null>(null)
  const [page,setPage]=useState<PreviewPage>('workspace')
  const [panel,setPanel]=useState<'colors'|'details'>('colors')
  const [fileNames,setFileNames]=useState<Partial<Record<'logo'|'loginBackground',string>>>({})
  const uploadVersion=useRef(0)
  const settingsScroll=useRef<HTMLDivElement>(null)
  useEffect(()=>{if(settingsScroll.current)settingsScroll.current.scrollTop=0},[panel])
  const original=useMemo(()=>resolveCustomTheme(initial),[initial])
  const preview=useMemo(()=>resolveCustomTheme(draft),[draft])
  const copy={...DEFAULT_COPY,...draft.copy}, legal={...DEFAULT_LEGAL,...draft.legal}
  const update=(value:Partial<ThemeFile>)=>setDraft(current=>({...current,...value}))
  let validation=''
  try{parseThemeFile(draft)}catch(reason){validation=(reason as Error).message}
  const upload=async(event:ChangeEvent<HTMLInputElement>,key:'logo'|'loginBackground')=>{
    const file=event.target.files?.[0];event.target.value='';if(!file)return
    const version=++uploadVersion.current
    setLoading(key);setError('')
    try{
      if(!THEME_IMAGE_TYPES.some(type=>type===file.type)||file.size>MAX_THEME_IMAGE_BYTES)throw new Error('Bitte ein PNG-, JPEG-, WebP- oder GIF-Bild bis 250 KB auswählen.')
      const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('Die Datei konnte nicht gelesen werden.'));reader.readAsDataURL(file)})
      await new Promise<void>((resolve,reject)=>{const image=new Image();image.onload=()=>resolve();image.onerror=()=>reject(new Error('Die Datei ist kein lesbares Bild.'));image.src=data})
      if(version!==uploadVersion.current)return
      setDraft(current=>({...current,[key]:data}));setFileNames(current=>({...current,[key]:file.name}));setPage('login')
    }catch(reason){if(version===uploadVersion.current)setError((reason as Error).message)}finally{if(version===uploadVersion.current)setLoading(null)}
  }
  const reset=()=>{uploadVersion.current++;setLoading(null);setDraft(structuredClone(initial));setFileNames({});setError('')}
  const colorField=(key:ColorKey)=>{
    const color=preview.colors[key]
    const opacity=color.length===9?Math.round(parseInt(color.slice(7),16)/255*100):100
    return <div className="studio-color" key={key}>
      <label className="studio-color-row"><span>{colorLabels[key]}</span><input aria-label={`${colorLabels[key]} wählen`} type="color" value={color.slice(0,7)} onChange={e=>update({colors:{...draft.colors,[key]:e.target.value+(color.length===9?color.slice(7):'')}})}/></label>
      {ALPHA_COLORS.has(key)&&<label className="studio-opacity"><span>Deckkraft {opacity}%</span><input aria-label={`${colorLabels[key]} Deckkraft`} type="range" min={0} max={100} value={opacity} onChange={e=>update({colors:{...draft.colors,[key]:color.slice(0,7)+Math.round(Number(e.target.value)*255/100).toString(16).padStart(2,'0')}})}/></label>}
    </div>
  }
  const assetField=(key:'logo'|'loginBackground',label:string)=><div className="creator-asset">
    <div className={`creator-asset-thumb ${key==='logo'?'creator-asset-logo':''}`}>{draft[key]?<img src={draft[key]} alt={`${label} Datei`}/>:<ImagePlus size={24}/>}</div>
    <div><Field label={label} help={fileNames[key]||'PNG, JPEG, WebP oder GIF · maximal 250 KB'}><input aria-label={label} type="file" accept={THEME_IMAGE_TYPES.join(',')} disabled={!!loading} onChange={e=>void upload(e,key)}/></Field>
      {draft[key]&&<Button variant="ghost" type="button" disabled={!!loading} onClick={()=>update({[key]:undefined})}><X size={13}/>{key==='logo'?'Eigenes Logo entfernen':'Hintergrundbild entfernen'}</Button>}
    </div>
  </div>
  return <main className="design-studio" aria-label="Designstudio">
    <header className="studio-header"><Button variant="ghost" onClick={onClose} aria-label="Zurück zu Designs"><ArrowLeft size={17}/><span>Designs</span></Button><span className="studio-header-divider"/>
      <Palette size={17}/><input className="studio-name" aria-label="Design-Name" required maxLength={80} value={draft.name} onChange={e=>update({name:e.target.value})}/>
      <span className="studio-draft-label">Entwurf</span><Button type="submit" aria-label="Speichern und aktivieren" form="design-studio-form" disabled={!!validation||!!loading}><Save size={15}/><span className="studio-save-label">Speichern und aktivieren</span><span className="studio-save-short" aria-hidden="true">Speichern</span></Button>
    </header>
    <div className="studio-workbench"><form id="design-studio-form" className="studio-settings" onSubmit={event=>{event.preventDefault();try{onSave(parseThemeFile(draft));setError('')}catch(reason){setError((reason as Error).message)}}}>
      <div className="studio-panel-tabs"><button type="button" aria-pressed={panel==='colors'} onClick={()=>setPanel('colors')}><Palette size={14}/>Farben</button><button type="button" aria-pressed={panel==='details'} onClick={()=>setPanel('details')}><Type size={14}/>Texte &amp; Bilder</button></div>
      <div className="studio-settings-scroll" ref={settingsScroll}>
        <div hidden={panel!=='colors'}>
          <Field label="Farbbasis"><select aria-label="Farbbasis" value={draft.base} onChange={e=>{const base=BUILTIN_THEMES.find(t=>t.id===e.target.value)!;update({base:base.id as ThemeFile['base'],colors:{...base.colors}})}}>{BUILTIN_THEMES.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
          <div className="creator-palettes">{palettes.map(palette=><button type="button" key={palette.name} onClick={()=>{
            const accent=preview.mode==='dark'?palette.dark:palette.light
            update({colors:{...draft.colors,accent,'accent-hover':accent,'accent-soft':accent+'14','accent-border':accent+'66','nav-indicator':accent,primary:palette.primary,'primary-hover':palette.primary,'primary-border':palette.primary,'on-primary':'#ffffff'}})
          }}><i style={{background:palette.primary}}/>{palette.name}</button>)}</div>
          <div className="studio-colors">{mainColors.map(colorField)}</div>
          <details><summary>Weitere Farben und Zustände</summary><div className="studio-colors">{COLOR_KEYS.filter(key=>!mainColors.includes(key)).map(colorField)}</div></details>
          <div className="creator-contrast"><CheckCircle2 size={15}/><span>Text <strong>{contrast(preview.colors.text,preview.colors.surface).toFixed(1)}:1</strong></span><span>Aktionen <strong>{contrast(preview.colors['on-primary'],preview.colors.primary).toFixed(1)}:1</strong></span></div>
        </div>
        <div hidden={panel!=='details'}>
          <fieldset><legend>Darstellung</legend><div className="creator-fields">
            <Field label="Beschreibung"><input maxLength={240} value={draft.description??''} onChange={e=>update({description:e.target.value})}/></Field>
            <Field label="Schrift"><select value={preview.font} onChange={e=>update({font:e.target.value as ThemeFile['font']})}><option value="system">Systemschrift</option><option value="sora">Sora</option></select></Field>
            <Field label={`Eckenradius · ${preview.radius} px`}><input type="range" min={0} max={16} value={preview.radius} onChange={e=>update({radius:Number(e.target.value)})}/></Field>
          </div></fieldset>
          <fieldset><legend>Logo und Bilder</legend>
            {assetField('logo','Eigenes Logo')}
            {!draft.logo&&<Field label="Logo-Vorlage"><select value={draft.logoAsset??''} onChange={e=>update({logoAsset:(e.target.value||undefined) as ThemeFile['logoAsset']})}><option value="">Neutrales Symbol</option>{LOGO_ASSETS.map(asset=><option key={asset.id} value={asset.id}>{asset.name}</option>)}</select></Field>}
            {(draft.logo||draft.logoAsset)&&<Field label={`Logobreite · ${draft.logoWidth??64} px`}><input type="range" min={32} max={120} value={draft.logoWidth??64} onChange={e=>update({logoWidth:Number(e.target.value)})}/></Field>}
            {(draft.logo||draft.logoAsset)&&<Field label="Logo-Darstellung"><select value={draft.logoTone??'original'} onChange={e=>update({logoTone:e.target.value as ThemeFile['logoTone']})}><option value="original">Originalfarben</option><option value="dark">Dunkel</option></select></Field>}
            {assetField('loginBackground','Hintergrundbild der Anmeldung')}
            {draft.loginBackground&&<Field label={`Hintergrund-Unschärfe · ${draft.loginBackgroundBlur??0} px`} help="Nur das Hintergrundbild wird unscharf. GIFs bleiben animiert."><input aria-label="Hintergrund-Unschärfe" type="range" min={0} max={MAX_LOGIN_BACKGROUND_BLUR} step={1} value={draft.loginBackgroundBlur??0} onChange={e=>{update({loginBackgroundBlur:Number(e.target.value)});setPage('login')}}/></Field>}
            {loading&&<span role="status" className="field-help">Bild wird geprüft …</span>}
          </fieldset>
          <fieldset><legend>Portal und Anmeldung</legend><div className="creator-fields">{Object.entries(copyLabels).map(([key,label])=><Field key={key} label={label}>{key==='intro'?<textarea rows={3} maxLength={400} value={copy.intro} onFocus={()=>setPage('login')} onChange={e=>update({copy:{...draft.copy,intro:e.target.value}})}/>:<input maxLength={100} value={copy[key as keyof ThemeCopy]} onFocus={()=>setPage('login')} onChange={e=>update({copy:{...draft.copy,[key]:e.target.value}})}/>}</Field>)}</div></fieldset>
          <fieldset><legend>Footer und Rechtliches</legend><div className="creator-fields">
            <Field label="Footertext"><input maxLength={160} value={legal.footer} onFocus={()=>setPage('login')} onChange={e=>update({legal:{...draft.legal,footer:e.target.value}})}/></Field>
            <Field label="Impressum" help={`${legal.imprint.length.toLocaleString('de-DE')} / 12.000 Zeichen`}><textarea aria-label="Impressum" rows={7} maxLength={12000} value={legal.imprint} onFocus={()=>setPage('imprint')} onChange={e=>{setPage('imprint');update({legal:{...draft.legal,imprint:e.target.value}})}}/></Field>
            <Field label="Datenschutz" help={`${legal.privacy.length.toLocaleString('de-DE')} / 12.000 Zeichen`}><textarea aria-label="Datenschutz" rows={7} maxLength={12000} value={legal.privacy} onFocus={()=>setPage('privacy')} onChange={e=>{setPage('privacy');update({legal:{...draft.legal,privacy:e.target.value}})}}/></Field>
          </div></fieldset>
        </div>
      </div>
      {validation&&<div className="creator-validation" role="status"><Notice type="info">{validation}</Notice></div>}
      {error&&<div className="creator-validation" role="alert"><Notice type="error">{error}</Notice></div>}
      <footer className="studio-settings-footer"><Button variant="ghost" type="button" onClick={reset}><RotateCcw size={14}/>Änderungen zurücksetzen</Button><span>In diesem Browser gespeichert</span></footer>
    </form><DesignLivePreview theme={preview} original={original} page={page} onPageChange={setPage} initialMode={initialMode} fullPage/></div>
  </main>
}
