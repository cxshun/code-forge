import { ElMessageBox, ElMessage } from 'element-plus'

export async function confirmAction(
  message: string,
  title = '确认操作',
  type: 'warning' | 'info' | 'success' | 'error' = 'warning',
): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, title, {
      type,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    return true
  } catch {
    return false
  }
}

export async function confirmDelete(message = '确定删除？此操作不可撤销。'): Promise<boolean> {
  return confirmAction(message, '删除确认', 'error')
}

export function showSuccess(message: string) {
  ElMessage.success(message)
}

export function showError(message: string) {
  ElMessage.error(message)
}
