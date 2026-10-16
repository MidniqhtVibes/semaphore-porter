export const WEBSITE_SYMBOLS=[
  {id:'portal',name:'Portal-Tor',description:'Ein Eingang mit Pfeil für den zentralen Zugang zu Projekten und Tasks.',recommended:true},
  {id:'tenants',name:'Mandanten-Verbund',description:'Verbundene Bausteine für mehrere Mandanten unter einer Oberfläche.',recommended:false},
  {id:'monogram',name:'SP-Monogramm',description:'Die Initialen von Semaphore Porter als kompaktes Produktsymbol.',recommended:false},
] as const
export type WebsiteSymbolId=typeof WEBSITE_SYMBOLS[number]['id']
export function isWebsiteSymbolId(value:unknown):value is WebsiteSymbolId {
  return WEBSITE_SYMBOLS.some(symbol=>symbol.id===value)
}
export function applyWebsiteSymbol(id:WebsiteSymbolId){
  const links=[
    {id:'portal-favicon-fallback',rel:'icon',type:'image/x-icon',sizes:'any',href:`/icons/${id}.ico`},
    {id:'portal-favicon',rel:'icon',type:'image/svg+xml',sizes:'any',href:`/icons/${id}.svg`},
    {id:'portal-touch-icon',rel:'apple-touch-icon',sizes:'180x180',href:`/icons/${id}-180.png`},
    {id:'portal-manifest',rel:'manifest',href:`/manifests/${id}.webmanifest`},
  ]
  for(const attributes of links){
    let link=document.getElementById(attributes.id) as HTMLLinkElement|null
    if(!link){link=document.createElement('link');link.id=attributes.id;document.head.append(link)}
    for(const [key,value] of Object.entries(attributes))link.setAttribute(key,value)
  }
}
