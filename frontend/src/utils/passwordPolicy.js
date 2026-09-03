export const MIN_PASSWORD_LENGTH = 12

export function meetsPasswordLength(password) {
  return typeof password === 'string' && password.length >= MIN_PASSWORD_LENGTH
}
