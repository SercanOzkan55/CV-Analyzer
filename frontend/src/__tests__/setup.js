import '@testing-library/jest-dom'
import { vi } from 'vitest'

vi.stubEnv('VITE_SUPABASE_URL', 'https://example.supabase.co')
vi.stubEnv('VITE_SUPABASE_KEY', 'test-anon-key')
