export function applyWebsiteSymbol(){
  const links=[
    {id:'portal-favicon-fallback',rel:'icon',type:'image/x-icon',sizes:'any',href:'/icons/portal.ico'},
    {id:'portal-favicon',rel:'icon',type:'image/svg+xml',sizes:'any',href:'/icons/portal.svg'},
    {id:'portal-touch-icon',rel:'apple-touch-icon',sizes:'180x180',href:'/icons/portal-180.png'},
    {id:'portal-manifest',rel:'manifest',href:'/manifests/portal.webmanifest'},
  ]
  for(const attributes of links){
    let link=document.getElementById(attributes.id) as HTMLLinkElement|null
    if(!link){link=document.createElement('link');link.id=attributes.id;document.head.append(link)}
    for(const [key,value] of Object.entries(attributes))link.setAttribute(key,value)
  }
}
