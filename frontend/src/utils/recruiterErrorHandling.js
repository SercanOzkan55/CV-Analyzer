/**
 * Enhanced error handling and validation improvements for Recruiter Dashboard
 * Addresses:
 * - Missing error logging and user feedback
 * - Incomplete error messages from API
 * - Missing input validation before API calls
 * - Inconsistent response format handling
 */

/**
 * Safely extract nested response data with fallbacks
 * Handles API inconsistencies where responses vary in structure
 * 
 * @param {*} data - API response data
 * @param {string} key - Primary key to look for (e.g., 'jobs', 'candidates')
 * @param {*} defaultVal - Default value if not found
 * @returns {*} Extracted data or default
 */
export function extractApiData(data, key, defaultVal = []) {
  if (!data) return defaultVal
  if (Array.isArray(data)) return data  // Direct array response
  if (data[key] !== undefined) return Array.isArray(data[key]) ? data[key] : defaultVal
  return defaultVal
}

/**
 * Format API error messages for user display
 * Extracts meaningful error details from various error formats
 * 
 * @param {Error|Response} error - Error object or fetch response
 * @param {string} defaultMsg - Fallback message
 * @returns {string} User-friendly error message
 */
export async function formatErrorMessage(error, defaultMsg = 'An error occurred') {
  // Handle Response objects (fetch API)
  if (error && typeof error.json === 'function') {
    try {
      const errorData = await error.json()
      return errorData?.detail || errorData?.message || defaultMsg
    } catch {
      return defaultMsg
    }
  }
  
  // Handle standard Error objects
  if (error instanceof Error) {
    return error.message || defaultMsg
  }
  
  // Handle string errors
  if (typeof error === 'string') {
    return error
  }
  
  return defaultMsg
}

/**
 * Safe API call wrapper with proper error handling and logging
 * 
 * @param {Function} apiFn - Async API function to call
 * @param {string} operationName - Name of operation for logging
 * @param {Object} options - Options object
 * @param {boolean} options.verbose - Log to console (for development)
 * @param {Function} options.onError - Optional error callback
 * @returns {Promise<{success: boolean, data: *, error: string|null}>}
 */
export async function safeApiCall(apiFn, operationName, { verbose = false, onError = null } = {}) {
  const startTime = performance.now()
  
  try {
    const result = await apiFn()
    const duration = performance.now() - startTime
    
    if (verbose) {
      console.log(`✓ ${operationName} succeeded in ${duration.toFixed(0)}ms`)
    }
    
    return { success: true, data: result, error: null }
  } catch (err) {
    const duration = performance.now() - startTime
    const errorMsg = err instanceof Error ? err.message : String(err)
    
    if (verbose) {
      console.error(`✗ ${operationName} failed after ${duration.toFixed(0)}ms:`, errorMsg)
    }
    
    if (onError) {
      onError(err)
    }
    
    return { success: false, data: null, error: errorMsg }
  }
}

/**
 * Validate email address format
 * 
 * @param {string} email - Email to validate
 * @returns {{valid: boolean, error: string|null}}
 */
export function validateEmail(email) {
  email = (email || '').trim()
  
  if (!email) {
    return { valid: false, error: 'Email is required' }
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email)) {
    return { valid: false, error: 'Invalid email format' }
  }
  
  if (email.length > 255) {
    return { valid: false, error: 'Email too long (max 255 characters)' }
  }
  
  return { valid: true, error: null }
}

/**
 * Validate CV text input
 * 
 * @param {string} cvText - CV text to validate
 * @param {number} minChars - Minimum characters required (default: 50)
 * @returns {{valid: boolean, error: string|null}}
 */
export function validateCVText(cvText, minChars = 50) {
  cvText = (cvText || '').trim()
  
  if (!cvText) {
    return { valid: false, error: 'CV text is required' }
  }
  
  if (cvText.length < minChars) {
    return { valid: false, error: `CV must have at least ${minChars} characters` }
  }
  
  if (cvText.length > 100_000) {
    return { valid: false, error: 'CV text too long (max 100,000 characters)' }
  }
  
  return { valid: true, error: null }
}

/**
 * Validate file uploads
 * 
 * @param {FileList|File[]} files - Files to validate
 * @param {Object} options - Validation options
 * @param {number} options.maxFiles - Maximum number of files (default: 50)
 * @param {number} options.maxSizeMB - Max file size in MB (default: 5)
 * @param {string[]} options.allowedTypes - Allowed MIME types
 * @returns {{valid: boolean, error: string|null, validFiles: File[]}}
 */
export function validateFileUploads(files, {
  maxFiles = 50,
  maxSizeMB = 5,
  allowedTypes = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
} = {}) {
  if (!files || files.length === 0) {
    return { valid: false, error: 'No files selected', validFiles: [] }
  }
  
  if (files.length > maxFiles) {
    return { valid: false, error: `Maximum ${maxFiles} files allowed (you selected ${files.length})`, validFiles: [] }
  }
  
  const validFiles = []
  const maxSizeBytes = maxSizeMB * 1_000_000
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    
    // Check file size
    if (file.size > maxSizeBytes) {
      return {
        valid: false,
        error: `File "${file.name}" is too large (${(file.size / 1_000_000).toFixed(1)}MB, max ${maxSizeMB}MB)`,
        validFiles: [],
      }
    }
    
    // Check file type
    const mimeToExtensions = {
      'application/pdf': ['pdf'],
      'text/plain': ['txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
      'application/msword': ['doc', 'docx'],
    }
    const derivedAllowedExtensions = []
    allowedTypes.forEach(t => {
      const extensions = mimeToExtensions[t] || []
      extensions.forEach(ext => {
        if (!derivedAllowedExtensions.includes(ext)) {
          derivedAllowedExtensions.push(ext)
        }
      })
    })

    const fileExtension = file.name.split('.').pop().toLowerCase()
    const isMimeAllowed = allowedTypes.includes(file.type)
    const isExtensionAllowed = derivedAllowedExtensions.includes(fileExtension)

    if (!isMimeAllowed && !isExtensionAllowed) {
      const displayExts = derivedAllowedExtensions.length > 0
        ? derivedAllowedExtensions.map(e => e.toUpperCase()).join(', ')
        : 'PDF, TXT, DOCX'
      return {
        valid: false,
        error: `File "${file.name}" has unsupported format. Allowed: ${displayExts}`,
        validFiles: [],
      }
    }
    
    validFiles.push(file)
  }
  
  return { valid: true, error: null, validFiles }
}

/**
 * Parse and extract detail message from API error response
 * 
 * @param {Error|Object} error - Error object or API response
 * @returns {string} Extracted detail message
 */
export function extractDetailFromError(error) {
  if (!error) return 'Unknown error'
  
  // Handle Response-like objects
  if (error.detail) return error.detail
  if (error.message) return error.message
  
  // Handle nested error structures
  if (error.error?.detail) return error.error.detail
  if (error.error?.message) return error.error.message
  
  if (typeof error === 'string') return error
  
  return 'An unexpected error occurred'
}

/**
 * Rate limit error detector
 * 
 * @param {Error|Object} error - Error to check
 * @returns {boolean} True if rate limit error
 */
export function isRateLimitError(error) {
  const msg = extractDetailFromError(error).toLowerCase()
  return msg.includes('rate') || msg.includes('limit') || msg.includes('too many')
}

/**
 * Validation error detector
 * 
 * @param {Error|Object} error - Error to check
 * @returns {boolean} True if validation error
 */
export function isValidationError(error) {
  const msg = extractDetailFromError(error).toLowerCase()
  return msg.includes('invalid') || msg.includes('required') || msg.includes('must')
}

/**
 * Permission error detector
 * 
 * @param {Error|Object} error - Error to check
 * @returns {boolean} True if permission error
 */
export function isPermissionError(error) {
  const msg = extractDetailFromError(error).toLowerCase()
  return msg.includes('permission') || msg.includes('unauthorized') || msg.includes('forbidden')
}
