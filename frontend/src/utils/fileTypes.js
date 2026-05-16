export const CV_UPLOAD_ACCEPT =
  'application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx,text/plain,.txt'

export function isPdfUpload(file) {
  if (!file) return false
  const name = (file.name || '').toLowerCase()
  return file.type === 'application/pdf' || name.endsWith('.pdf')
}

export function isDocxUpload(file) {
  if (!file) return false
  const name = (file.name || '').toLowerCase()
  return (
    file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    name.endsWith('.docx')
  )
}

export function isTextUpload(file) {
  if (!file) return false
  const name = (file.name || '').toLowerCase()
  return file.type === 'text/plain' || name.endsWith('.txt')
}

export function isSupportedCvUpload(file) {
  return isPdfUpload(file) || isDocxUpload(file) || isTextUpload(file)
}
