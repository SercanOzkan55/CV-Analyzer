// Launch feature flags. Every flag defaults to OFF and is enabled per
// environment via Vite env vars so unfinished features stay hidden in
// production builds.

// The community blog is backed by authenticated, moderated API endpoints.
// Enable it explicitly per environment after the database migration is applied.
export const BLOG_ENABLED = import.meta.env.VITE_ENABLE_BLOG === 'true'
