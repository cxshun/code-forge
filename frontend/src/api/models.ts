import { http } from './client'

export interface ModelMeta {
  name: string
  context_window: number
  max_output_tokens: number
}

export const modelsApi = {
  list() {
    return http.get<unknown, ModelMeta[]>('/admin/models')
  },
}
