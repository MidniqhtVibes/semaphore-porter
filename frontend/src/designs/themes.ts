import { LOGO_ASSETS, type LogoAssetId } from './logoAssets'

export const COLOR_KEYS = [
  'bg', 'header', 'surface', 'surface-alt', 'surface-soft', 'hover', 'border', 'border-soft',
  'text', 'muted', 'accent', 'accent-hover', 'accent-soft', 'accent-border', 'nav-indicator',
  'primary', 'primary-hover', 'primary-border', 'on-primary', 'success', 'success-soft',
  'success-border', 'warning', 'warning-soft', 'warning-border', 'danger', 'danger-soft',
  'danger-border', 'danger-hover', 'on-danger', 'on-emphasis', 'overlay', 'selection', 'on-selection',
] as const
export type ColorKey = typeof COLOR_KEYS[number]
export type Colors = Record<ColorKey, string>
export type BuiltinId = 'neutral-dark' | 'neutral-light' | 'github-dark' | 'sit-light' | 'sit-dark'
export type FontId = 'system' | 'sora'
export type Branding = 'neutral' | 'sit'
export const DEFAULT_COPY = {
  title: 'Semaphore', subtitle: 'Tenant Portal',
  headline: 'Deployments starten.', emphasis: 'Sicher getrennt.',
  intro: 'Eine zentrale Oberfläche für Mandanten, Anwendungen und freigegebene Semaphore-Tasks.',
  welcome: 'Willkommen zurück', loginHint: 'Melden Sie sich mit Ihrem lokalen Portalkonto an.',
}
export type ThemeCopy = typeof DEFAULT_COPY
export const DEFAULT_LEGAL = {footer:'Tenant Portal', imprint:'', privacy:''}
export type ThemeLegal = typeof DEFAULT_LEGAL
export const MAX_THEME_BYTES = 1024 * 1024
export const LOGO_PATTERN = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$/
export type ThemeFile = {
  schema_version: 1
  id: string
  name: string
  description?: string
  base: BuiltinId
  colors?: Partial<Colors>
  font?: FontId
  radius?: number
  branding?: Branding
  logoAsset?: LogoAssetId
  logoTone?: 'original' | 'dark'
  copy?: Partial<ThemeCopy>
  logo?: string
  loginBackground?: string
  logoWidth?: number
  legal?: Partial<ThemeLegal>
}
export type Theme = {
  id: string
  name: string
  description: string
  mode: 'light' | 'dark'
  font: FontId
  radius: number
  colors: Colors
  logoAsset?: LogoAssetId
  logoTone?: 'original' | 'dark'
  definition?: ThemeFile
  copy?: Partial<ThemeCopy>
  logo?: string
  loginBackground?: string
  logoWidth?: number
  legal?: Partial<ThemeLegal>
}
export const FONT_STACKS: Record<FontId,string> = {
  system: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif',
  sora: 'Sora, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
}
const github: Colors = {
  bg:'#0d1117', header:'#010409', surface:'#0d1117', 'surface-alt':'#161b22', 'surface-soft':'#010409',
  hover:'#212830', border:'#3d444d', 'border-soft':'#262c36', text:'#f0f6fc', muted:'#9198a1',
  accent:'#4493f8', 'accent-hover':'#79c0ff', 'accent-soft':'#388bfd1a', 'accent-border':'#388bfd66',
  'nav-indicator':'#f78166', primary:'#238636', 'primary-hover':'#29903b', 'primary-border':'#ffffff1a',
  'on-primary':'#ffffff', success:'#3fb950', 'success-soft':'#2386361a', 'success-border':'#23863666',
  warning:'#d29922', 'warning-soft':'#9e6a031a', 'warning-border':'#9e6a0366',
  danger:'#f85149', 'danger-soft':'#da36331a', 'danger-border':'#da363366', 'danger-hover':'#da3633',
  'on-danger':'#ffffff', 'on-emphasis':'#ffffff', overlay:'#010409b3', selection:'#1f6feb', 'on-selection':'#ffffff',
}
export const BUILTIN_THEMES: Theme[] = [
  {id:'neutral-dark', name:'Neutral Dunkel', description:'Neutrale dunkle Flächen, klare Typografie und dezente blaue Akzente.', mode:'dark', font:'system', radius:6, colors:{
    ...github,bg:'#111418',header:'#171b21',surface:'#1b2028','surface-alt':'#222934','surface-soft':'#14191f',
    hover:'#2a3442',border:'#455164','border-soft':'#303a48',text:'#edf1f5',muted:'#a2acba',
    accent:'#8bb9ff','accent-hover':'#b5d2ff','accent-soft':'#8bb9ff14','accent-border':'#8bb9ff66','nav-indicator':'#8bb9ff',
    primary:'#315da8','primary-hover':'#3c70c4','primary-border':'#4774bd','on-primary':'#ffffff',
  }},
  {id:'neutral-light', name:'Neutral Hell', description:'Neutrale helle Flächen, klare Typografie und dezente blaue Akzente.', mode:'light', font:'system', radius:6, colors:{
    ...github,bg:'#f5f7fa',header:'#ffffff',surface:'#ffffff','surface-alt':'#f0f3f7','surface-soft':'#edf1f6',
    hover:'#e5ebf3',border:'#bbc5d2','border-soft':'#dce2eb',text:'#242b36',muted:'#5b6574',
    accent:'#245db2','accent-hover':'#194889','accent-soft':'#245db214','accent-border':'#245db266','nav-indicator':'#245db2',
    primary:'#315da8','primary-hover':'#254a89','primary-border':'#315da8','on-primary':'#ffffff',
    success:'#1b6b3a','success-soft':'#1b6b3a14','success-border':'#1b6b3a66',
    warning:'#865400','warning-soft':'#86540014','warning-border':'#86540066',
    danger:'#b02a37','danger-soft':'#b02a3714','danger-border':'#b02a3766','danger-hover':'#91202b',
    overlay:'#18233280',selection:'#245db2','on-selection':'#ffffff',
  }},
  {id:'github-dark', name:'GitHub Black', description:'Das bisherige Design mit dunklen Flächen, blauen Links und grünen Aktionen.', mode:'dark', font:'system', radius:6, colors:github},
  {id:'sit-light', name:'SIT Hell', description:'Helle Flächen, Anthrazit und kräftiges Grün nach dem SIT Look & Feel.', mode:'light', font:'sora', logoAsset:'sit-logo', logoTone:'dark', radius:6, colors:{
    ...github, bg:'#ececec', header:'#ffffff', surface:'#ffffff', 'surface-alt':'#f5f6f3', 'surface-soft':'#ececec',
    hover:'#e2e8de', border:'#b7bbb5', 'border-soft':'#d6dad3', text:'#414146', muted:'#64646b',
    accent:'#414146', 'accent-hover':'#25252b', 'accent-soft':'#50be4614', 'accent-border':'#50be4680',
    'nav-indicator':'#50be46', primary:'#414146', 'primary-hover':'#303035', 'primary-border':'#414146',
    'on-primary':'#ececec', success:'#286924', 'success-soft':'#50be461a', 'success-border':'#50be4680',
    warning:'#88501d', 'warning-soft':'#ffa56929', 'warning-border':'#ff823780',
    danger:'#973367', 'danger-soft':'#f08cdc26', 'danger-border':'#f08cdc99', 'danger-hover':'#973367',
    'on-danger':'#ffffff', overlay:'#41414680', selection:'#9bd78c', 'on-selection':'#414146',
  }},
  {id:'sit-dark', name:'SIT Dunkel', description:'Anthrazit, Hellgrün und die Schrift Sora für eine ruhige dunkle Arbeitsfläche.', mode:'dark', font:'sora', logoAsset:'sit-logo', logoTone:'original', radius:6, colors:{
    ...github, bg:'#414146', header:'#36363b', surface:'#48484e', 'surface-alt':'#505057', 'surface-soft':'#36363b',
    hover:'#5a5a61', border:'#77777e', 'border-soft':'#606067', text:'#ececec', muted:'#c3c3c9',
    accent:'#9bd78c', 'accent-hover':'#b7e2ad', 'accent-soft':'#9bd78c14', 'accent-border':'#9bd78c66',
    'nav-indicator':'#9bd78c', primary:'#9bd78c', 'primary-hover':'#b7e2ad', 'primary-border':'#9bd78c',
    'on-primary':'#414146', success:'#9bd78c', 'success-soft':'#9bd78c14', 'success-border':'#9bd78c66',
    warning:'#ffa569', 'warning-soft':'#ff82371a', 'warning-border':'#ffa56966',
    danger:'#f08cdc', 'danger-soft':'#f08cdc1a', 'danger-border':'#f08cdc66', 'danger-hover':'#f08cdc',
    'on-danger':'#414146', overlay:'#242429b3', selection:'#9bd78c', 'on-selection':'#414146',
  }},
]
export const DEFAULT_THEME_ID = 'neutral-dark'
export const DEFAULT_THEME = BUILTIN_THEMES.find(theme=>theme.id===DEFAULT_THEME_ID)!

export const ALPHA_COLORS = new Set(['accent-soft','accent-border','primary-border','success-soft','success-border','warning-soft','warning-border','danger-soft','danger-border','overlay'])

function object(value: unknown): value is Record<string,unknown> { return typeof value==='object' && value!==null && !Array.isArray(value) }
function luminance(color: string) {
  const [r,g,b]=[1,3,5].map(index=>parseInt(color.slice(index,index+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
  return r*.2126+g*.7152+b*.0722
}
export function contrast(a: string,b: string) {
  const x=luminance(a), y=luminance(b)
  return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)
}
export function resolveCustomTheme(definition: ThemeFile): Theme {
  const base=BUILTIN_THEMES.find(theme=>theme.id===definition.base)!
  return {...base, id:`custom:${definition.id}`, name:definition.name, description:definition.description||'Eigenes Design',
    colors:{...base.colors,...definition.colors}, font:definition.font||base.font, radius:definition.radius??base.radius, logoAsset:definition.logoAsset, logoTone:definition.logoTone, copy:definition.copy, logo:definition.logo,
    loginBackground:definition.loginBackground, logoWidth:definition.logoWidth, legal:definition.legal, definition}
}
export function parseThemeFile(value: unknown): ThemeFile {
  const keys=['schema_version','id','name','description','base','colors','font','radius','branding','logoAsset','logoTone','copy','logo','loginBackground','logoWidth','legal']
  if(!object(value)||Object.keys(value).some(key=>!keys.includes(key)))throw new Error('Ungültiges Design-Format. Bitte die JSON-Vorlage verwenden.')
  if(value.schema_version!==1)throw new Error('Diese Design-Version wird nicht unterstützt. Erwartet wird schema_version: 1.')
  if(typeof value.id!=='string'||!/^[a-z0-9][a-z0-9-]{1,47}$/.test(value.id))throw new Error('Design-ID: 2–48 Kleinbuchstaben, Ziffern oder Bindestriche erforderlich.')
  if(typeof value.name!=='string'||!value.name.trim()||value.name.length>80)throw new Error('Ein Design-Name mit maximal 80 Zeichen ist erforderlich.')
  if(value.description!==undefined&&(typeof value.description!=='string'||value.description.length>240))throw new Error('Die Beschreibung darf maximal 240 Zeichen enthalten.')
  if(!BUILTIN_THEMES.some(theme=>theme.id===value.base))throw new Error('Unbekanntes Basisdesign.')
  if(value.font!==undefined&&(typeof value.font!=='string'||!['system','sora'].includes(value.font)))throw new Error('Als Schrift sind system und sora erlaubt.')
  if(value.branding!==undefined&&(typeof value.branding!=='string'||!['neutral','sit'].includes(value.branding)))throw new Error('Als Bildmarke sind neutral und sit erlaubt.')
  if(value.radius!==undefined&&(typeof value.radius!=='number'||!Number.isInteger(value.radius)||value.radius<0||value.radius>16))throw new Error('Der Eckenradius muss zwischen 0 und 16 liegen.')
  if(value.colors!==undefined){
    if(!object(value.colors))throw new Error('colors muss ein Objekt mit Farbwerten sein.')
    for(const [key,color] of Object.entries(value.colors)){
      if(!COLOR_KEYS.includes(key as ColorKey))throw new Error(`Unbekannter Farbschlüssel: ${key}`)
      if(typeof color!=='string'||!/^#[0-9a-f]{6}([0-9a-f]{2})?$/i.test(color)||(!ALPHA_COLORS.has(key)&&color.length!==7))throw new Error(`${key}: Ein Hex-Farbwert ist erforderlich; Transparenz ist nur für Rahmen und Hinweisflächen erlaubt.`)
    }
  }
  if(value.copy!==undefined){
    if(!object(value.copy))throw new Error('Texte müssen als Objekt angegeben werden.')
    for(const [key,text] of Object.entries(value.copy)){
      if(!Object.prototype.hasOwnProperty.call(DEFAULT_COPY,key)||typeof text!=='string'||!text.trim()||text.length>(key==='intro'?400:100))throw new Error('Ungültiger Design-Text oder Text zu lang.')
    }
  }
  for(const key of ['logo','loginBackground'] as const){
    const image=value[key]
    if(image!==undefined){
      const invalid=typeof image!=='string'||!LOGO_PATTERN.test(image)
      const data=typeof image==='string'?image.slice(image.indexOf(',')+1):''
      const bytes=data.length*3/4-(data.endsWith('==')?2:data.endsWith('=')?1:0)
      if(invalid||data.length%4!==0||bytes>250*1024)throw new Error(`${key==='logo'?'Das Logo':'Das Hintergrundbild'} muss ein eingebettetes PNG-, JPEG- oder WebP-Bild bis 250 KB sein.`)
    }
  }
  if(value.logoWidth!==undefined&&(typeof value.logoWidth!=='number'||!Number.isInteger(value.logoWidth)||value.logoWidth<32||value.logoWidth>120))throw new Error('Die Logobreite muss zwischen 32 und 120 Pixeln liegen.')
  if(value.legal!==undefined){
    if(!object(value.legal))throw new Error('Footer und rechtliche Texte müssen als Objekt angegeben werden.')
    for(const [key,text] of Object.entries(value.legal)){
      if(!Object.prototype.hasOwnProperty.call(DEFAULT_LEGAL,key)||typeof text!=='string'||text.length>(key==='footer'?160:12000))throw new Error('Ungültiger Footer- oder Rechtstext oder Text zu lang.')
    }
  }
  if(value.logoAsset!==undefined&&!LOGO_ASSETS.some(asset=>asset.id===value.logoAsset))throw new Error('Unbekannte Logo-Vorlage.')
  if(value.logoTone!==undefined&&(typeof value.logoTone!=='string'||!['original','dark'].includes(value.logoTone)))throw new Error('Unbekannte Logo-Darstellung.')
  const definition=JSON.parse(JSON.stringify(value)) as ThemeFile
  // Migrate older design files once; renderers use only generic logo metadata.
  if(definition.branding==='sit'&&definition.logoAsset===undefined){
    definition.logoAsset='sit-logo'
    definition.logoTone??=BUILTIN_THEMES.find(theme=>theme.id===definition.base)?.mode==='light'?'dark':'original'
  }
  delete definition.branding
  definition.name=definition.name.trim()
  const colors=resolveCustomTheme(definition).colors
  for(const [foreground,background] of [['text','bg'],['text','surface'],['muted','surface'],['on-primary','primary']] as const){
    if(contrast(colors[foreground],colors[background])<4.5)throw new Error(`Zu wenig Kontrast zwischen ${foreground} und ${background}. Bitte die Farben für gut lesbaren Text anpassen.`)
  }
  return definition
}
export function exportThemeFile(theme: Theme): ThemeFile {
  return theme.definition||{schema_version:1,id:theme.id,name:theme.name,description:theme.description,base:theme.id as BuiltinId,font:theme.font,radius:theme.radius,logoAsset:theme.logoAsset,logoTone:theme.logoTone,colors:{...theme.colors}}
}

export function createDraft(theme: Theme): ThemeFile {
  return {schema_version:1,id:`design-${crypto.randomUUID().slice(0,8)}`,name:`${theme.name} – Kopie`.slice(0,80),description:theme.description,base:theme.definition?.base??theme.id as ThemeFile['base'],colors:{...theme.colors},font:theme.font,radius:theme.radius,logoAsset:theme.logoAsset,logoTone:theme.logoTone,copy:{...theme.copy},legal:{...theme.legal},logo:theme.logo,loginBackground:theme.loginBackground,logoWidth:theme.logoWidth}
}
