export type GitLabConfig = {
  configured:boolean;token_present:boolean;base_url?:string;project_id?:number;base_branch?:string
  write_enabled?:boolean;connection_id?:string;project_name?:string;web_url?:string;protected?:boolean;last_tested_at?:string
}
export type Repository = {sha:string;branch:string;project_name:string;web_url?:string;providers:Record<string,unknown>;programs:Array<{
  id:string;name:string;database_types:string[];release:string;profile:string
}>}
export type Pipeline = {id:number;pipeline_id?:number;sha:string;ref?:string;status:string;web_url?:string}
export type Validation = {valid:boolean;version?:number;compiler:string;source_hash:string;note:string;pipeline?:Pipeline;
  checks:Array<{application_id:string;database_type:string;policy:string;dataset_id:string;compatibility_id:string}>}
export type Manifest = {
  schema_version:number;id:string;display_name:string;profile_version:number
  release:{default:string;primary_image:string;images:Record<string,{repository_key:string;tag_input:string;repository_environment:string;tag_environment:string}>}
  database:{default_type:string;types:Record<string,{provider_id:string;allowed_policies:string[];compose:Record<string,string>;configuration_files:unknown[];connection_mapping:Record<string,string>}>}
  datasets:{catalog:string;optional:boolean};readiness:unknown[];secrets:{vault_profile:string;required:Record<string,unknown>}
}
export type Dataset = {description:string;format:string;database_type:string;provider_ids:string[];file:string;sha256:string;
  contains_schema:boolean;engine_major:number;compatible_image_tags:string[]}
export type DatasetCatalog = {schema_version:number;datasets:Record<string,Dataset>}
export type PackageDraft = {
  id:string;package_id:string;name:string;base_sha:string;base_branch:string;version:number;status:string;branch?:string
  commit_sha?:string;merge_request_iid?:number;connection_id:string;last_error?:string;execution_started_at?:string
  files:Record<string,string>;manifest:Manifest;dataset_catalog:DatasetCatalog
  diff:Array<{path:string;action:string;diff:string|null;sha256:string|null}>;validation?:Validation
  remote_status?:{state:string;web_url?:string;sha?:string;merge_status?:string;pipelines?:Pipeline[]}
  updated_at:string;created_at:string
}
export type Snapshot = {
  id:string;source_sha:string;source_hash:string;connection_id:string;active:boolean;created_at:string;project_name:string
  catalog:{applications:Record<string,{display_name:string;profile:string;database_types:Record<string,string>;datasets:Record<string,unknown>}>;source_revision:string}
  validation:Validation;diff:{added:string[];removed:string[];changed:string[]}
}
export type Snapshots = {active_id:string|null;current_catalog:Snapshot['catalog'];snapshots:Snapshot[]}

export function decodeText(value:string):string|null {
  try{const bytes=Uint8Array.from(atob(value),char=>char.charCodeAt(0));const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);return text.includes('\0')?null:text}catch{return null}
}
export function encodeBytes(bytes:Uint8Array):string {
  let binary='';for(let start=0;start<bytes.length;start+=8192)binary+=String.fromCharCode(...bytes.subarray(start,start+8192))
  return btoa(binary)
}
export function encodeText(value:string){return encodeBytes(new TextEncoder().encode(value))}
export function downloadPackage(draft:PackageDraft){
  const url=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,package_id:draft.package_id,base_sha:draft.base_sha,files:draft.files},null,2)],{type:'application/json'}))
  const anchor=document.createElement('a');anchor.href=url;anchor.download=`${draft.package_id}-${draft.id}.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),0)
}
