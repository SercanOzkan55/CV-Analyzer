// Launch feature flags. Every flag defaults to OFF and is enabled per
// environment via Vite env vars so unfinished features stay hidden in
// production builds.

// Blog currently runs on localStorage with seeded demo content — keep it
// hidden until it is backed by a real backend.
export const BLOG_ENABLED = import.meta.env.VITE_ENABLE_BLOG === 'true'

// Checkout and billing portal stay unavailable until Stripe production
// products, redirects, and webhooks are configured and verified.
export const BILLING_ENABLED = import.meta.env.VITE_ENABLE_BILLING === 'true'
