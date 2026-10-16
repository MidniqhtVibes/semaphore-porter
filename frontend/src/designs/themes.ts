export const COLOR_KEYS = [
  'bg', 'header', 'surface', 'surface-alt', 'surface-soft', 'hover', 'border', 'border-soft',
  'text', 'muted', 'accent', 'accent-hover', 'accent-soft', 'accent-border', 'nav-indicator',
  'primary', 'primary-hover', 'primary-border', 'on-primary', 'success', 'success-soft',
  'success-border', 'warning', 'warning-soft', 'warning-border', 'danger', 'danger-soft',
  'danger-border', 'danger-hover', 'on-danger', 'on-emphasis', 'overlay', 'selection', 'on-selection',
] as const
export type ColorKey = typeof COLOR_KEYS[number]
export type Colors = Record<ColorKey, string>
export type BuiltinId = 'github-dark' | 'sit-light' | 'sit-dark'
export type FontId = 'system' | 'sora'
export type Branding = 'neutral' | 'sit'
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
}
export type Theme = {
  id: string
  name: string
  description: string
  mode: 'light' | 'dark'
  font: FontId
  radius: number
  colors: Colors
  branding: Branding
  definition?: ThemeFile
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
  {id:'github-dark', name:'GitHub Black', description:'Das bisherige Design mit dunklen Flächen, blauen Links und grünen Aktionen.', mode:'dark', font:'system', branding:'neutral', radius:6, colors:github},
  {id:'sit-light', name:'SIT Hell', description:'Helle Flächen, Anthrazit und kräftiges Grün nach dem SIT Look & Feel.', mode:'light', font:'sora', branding:'sit', radius:6, colors:{
    ...github, bg:'#ececec', header:'#ffffff', surface:'#ffffff', 'surface-alt':'#f5f6f3', 'surface-soft':'#ececec',
    hover:'#e2e8de', border:'#b7bbb5', 'border-soft':'#d6dad3', text:'#414146', muted:'#64646b',
    accent:'#414146', 'accent-hover':'#25252b', 'accent-soft':'#50be4614', 'accent-border':'#50be4680',
    'nav-indicator':'#50be46', primary:'#414146', 'primary-hover':'#303035', 'primary-border':'#414146',
    'on-primary':'#ececec', success:'#286924', 'success-soft':'#50be461a', 'success-border':'#50be4680',
    warning:'#88501d', 'warning-soft':'#ffa56929', 'warning-border':'#ff823780',
    danger:'#973367', 'danger-soft':'#f08cdc26', 'danger-border':'#f08cdc99', 'danger-hover':'#973367',
    'on-danger':'#ffffff', overlay:'#41414680', selection:'#9bd78c', 'on-selection':'#414146',
  }},
  {id:'sit-dark', name:'SIT Dunkel', description:'Anthrazit, Hellgrün und die Schrift Sora für eine ruhige dunkle Arbeitsfläche.', mode:'dark', font:'sora', branding:'sit', radius:6, colors:{
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
const ALPHA_COLORS = new Set(['accent-soft','accent-border','primary-border','success-soft','success-border','warning-soft','warning-border','danger-soft','danger-border','overlay'])

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
    colors:{...base.colors,...definition.colors}, font:definition.font||base.font, radius:definition.radius??base.radius, branding:definition.branding??'neutral', definition}
}
export function parseThemeFile(value: unknown): ThemeFile {
  const keys=['schema_version','id','name','description','base','colors','font','radius','branding']
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
  const definition=JSON.parse(JSON.stringify(value)) as ThemeFile
  definition.name=definition.name.trim()
  const colors=resolveCustomTheme(definition).colors
  for(const [foreground,background] of [['text','bg'],['text','surface'],['muted','surface'],['on-primary','primary']] as const){
    if(contrast(colors[foreground],colors[background])<4.5)throw new Error(`Zu wenig Kontrast zwischen ${foreground} und ${background}. Bitte die Farben für gut lesbaren Text anpassen.`)
  }
  return definition
}
export function exportThemeFile(theme: Theme): ThemeFile {
  return theme.definition||{schema_version:1,id:theme.id,name:theme.name,description:theme.description,base:theme.id as BuiltinId,font:theme.font,radius:theme.radius,branding:theme.branding,colors:{...theme.colors}}
}
