export interface UserInfo {
  id: number
  username: string
  role: 'admin' | 'user'
  status: 'active' | 'disabled'
}

export interface UserOut {
  id: number
  username: string
  role: 'admin' | 'user'
  status: 'active' | 'disabled'
}

export interface UserCreateIn {
  username: string
  password: string
  role?: 'admin' | 'user'
}

export interface UserPatchIn {
  role?: 'admin' | 'user'
  status?: 'active' | 'disabled'
}

export interface ResetPasswordIn {
  new_password: string
}

export interface LoginResponse {
  user: UserInfo
}
