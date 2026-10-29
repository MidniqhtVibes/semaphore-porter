export type SshBinding = {profile_id:string;resource_kind:'inventories'|'repositories';resource_name:string}
export type SshProfile = {
  id:string;name:string;purpose:'host'|'git';login:string;vault_path:string;vault_version:number
  allowed_targets:string[];is_active:boolean;fingerprint?:string|null;public_key?:string|null
  last_tested_at?:string|null;revision:string
}
export type SshPlan = {profile:Pick<SshProfile,'id'|'purpose'|'login'|'vault_path'|'vault_version'|'allowed_targets'>
  name:string;fingerprint:string;public_key:string;bindings:Array<{kind:string;name:string;targets:string[]}>}
export type SshUse = {id:string;profile_id:string;creation_job_id:string;semaphore_project_id:number;semaphore_key_id:number
  vault_version:number;fingerprint:string;status:string;last_error?:string|null;bindings:Array<{kind:string;name:string;targets:string[]}>}
export type SshStore = {configured:boolean;base_url?:string;namespace?:string;kv_mount?:string;auth_mount?:string;role_id_present?:boolean;secret_id_present?:boolean}
