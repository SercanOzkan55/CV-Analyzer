import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://oanidolrgdukiqxvvbzd.supabase.co'
const supabaseKey = import.meta.env.VITE_SUPABASE_KEY || 'sb_publishable_jtUrR1fRO7YbWwecyeGcVQ_00jbDGfo'

export const supabase = createClient(supabaseUrl, supabaseKey)
