export interface FeishuAppOut {
  id: number
  app_id: string
  app_secret_masked: string
  name: string
  owner_id: number
  owner_name?: string
  connection_status: string
}

export interface FeishuAppCreateIn {
  app_id: string
  app_secret: string
  name: string
}

export interface FeishuAppPatchIn {
  name?: string
  app_secret?: string
}

export interface FeishuAppCreateResult extends FeishuAppOut {
  app_secret?: string
}
