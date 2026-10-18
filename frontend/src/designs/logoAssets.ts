// Bundled image resources use the same logo controls as uploaded images.
export const LOGO_ASSETS = [
  {id:'sit-logo',name:'Südwestfalen-IT',src:'/branding/sit-logo.png',alt:'Südwestfalen-IT'},
] as const
export type LogoAssetId = typeof LOGO_ASSETS[number]['id']
