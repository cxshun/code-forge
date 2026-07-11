export interface SkillOut {
  id: number
  name: string
  description: string
  owner_id: number
  visibility: 'private' | 'public'
  dir_path: string
  mounted_count?: number
}

export interface SkillPatchIn {
  description?: string
  visibility?: 'private' | 'public'
}
