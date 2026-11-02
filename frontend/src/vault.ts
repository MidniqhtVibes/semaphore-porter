export type VaultSecretField = {
  key:string;source:'registry'|'input';generate:'password'|'hex'|null;input_id:string
  min_length:number;max_length:number;hex:boolean;even_length:boolean;forbid_whitespace:boolean
}
export type VaultPlan = {kv_mount:string;objects:Array<{id:string;kind:string;path:string;fields:VaultSecretField[]}>;registries?:Array<{id:string;name:string;application_id:string;host:string;username:string;source:string;vault_path?:string|null;vault_version?:number|null}>}
export type VaultInputs = Record<string,{mode:'manual'|'generate';value?:string}>
export type VaultProgress = {objects:Record<string,{state:string;version?:number}>;access_installed?:boolean}
export type VaultConfig = {
  configured:boolean;enabled:boolean;base_url?:string;namespace?:string;kv_mount?:string;tenant_root?:string
  writer_auth_mount?:string;reader_auth_mount?:string
  credentials_present?:Record<string,boolean>;registry_configured?:Record<string,boolean>
}
export type VaultCatalog = {
  source_revision:string
  applications:Record<string,{display_name:string;database_types:Record<string,string>;datasets:Record<string,{database_type:string}>;
    fields?:Array<{source:string;key:string}>;registry?:{login:boolean;host_variable:string|null;username_variable:string|null;password_secret:string|null}|null}>
}
