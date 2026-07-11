export interface ListResult<T> {
  items: T[]
  total: number
}

export interface ErrorResponse {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
