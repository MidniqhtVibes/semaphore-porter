export type RegistryProfile = {
  id:string;name:string;application_id:string;host:string;username:string;host_variable:string;username_variable:string
  source:'stored'|'vault';vault_path:string|null;vault_version:number|null;vault_field:string|null
  password_present:boolean;is_active:boolean;revision:string
}
export type RegistryReader = {configured:boolean;base_url:string;namespace:string;kv_mount:string;auth_mount:string;role_id_present:boolean;secret_id_present:boolean}
export type RegistryBinding = Record<string,string>
