import React, { lazy, Suspense } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"

import ErrorBoundary from "./components/ErrorBoundary"
import { ThemeProvider } from "./context/ThemeContext"
import { LanguageProvider } from "./i18n/LanguageContext"
import { AuthProvider, useAuth } from "./context/AuthContext"
import { ToastProvider } from "./components/Toast"

import CookieConsent from "./components/CookieConsent"
import BackToTop from "./components/BackToTop"
import FeedbackButton from "./components/FeedbackButton"


// ---------- LAZY PAGES ----------

const LandingPage = lazy(() => import("./pages/LandingPage"))
const LoginPage = lazy(() => import("./pages/LoginPage"))
const RegisterPage = lazy(() => import("./pages/RegisterPage"))
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"))
const DashboardPage = lazy(() => import("./pages/DashboardPage"))
const AnalyzePage = lazy(() => import("./pages/AnalyzePage"))
const FeedbackPage = lazy(() => import("./pages/FeedbackPage"))
const HistoryPage = lazy(() => import("./pages/HistoryPage"))
const SettingsPage = lazy(() => import("./pages/SettingsPage"))
const RecruiterPage = lazy(() => import("./pages/RecruiterPage"))
const PricingPage = lazy(() => import("./pages/PricingPage"))
const PremiumPage = lazy(() => import("./pages/PremiumPage"))
const CVBuilderPage = lazy(() => import("./pages/CVBuilderPage"))
const AdminBillingPage = lazy(() => import("./pages/AdminBillingPage"))
const PrivacyPage = lazy(() => import("./pages/PrivacyPage"))
const TermsPage = lazy(() => import("./pages/TermsPage"))
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"))
const BlogPage = lazy(() => import("./pages/BlogPage"))
const BlogDetailPage = lazy(() => import("./pages/BlogDetailPage"))


// ---------- ROUTE GUARDS ----------

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="loading">
        <span className="loading-text">CV Analyzer</span>
      </div>
    )
  }

  return user ? children : <Navigate to="/login" />
}


function PublicRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="loading">
        <span className="loading-text">CV Analyzer</span>
      </div>
    )
  }

  return user ? <Navigate to="/dashboard" /> : children
}


function RecruiterRoute({ children }) {
  const { user, loading, planLoading, role, isBillingAdmin } = useAuth()

  if (loading || planLoading) {
    return (
      <div className="loading">
        <span className="loading-text">CV Analyzer</span>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" />

  if (role !== "recruiter" && !isBillingAdmin) {
    return <Navigate to="/pricing" state={{ reason: "recruiter_required" }} />
  }

  return children
}


function AdminBillingRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="loading">
        <span className="loading-text">CV Analyzer</span>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" />

  const configured = String(
    import.meta.env.VITE_BILLING_ADMIN_EMAILS || ""
  )
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)

  const email = String(user?.email || "").trim().toLowerCase()

  if (!email || !configured.includes(email)) {
    return <Navigate to="/dashboard" />
  }

  return children
}


// ---------- APP ----------


export default function App() {
  return (
    <ErrorBoundary fallback={<div className="error-fallback">Bir hata oluştu. Lütfen sayfayı yenileyin veya destek ekibiyle iletişime geçin.</div>}>
      <LanguageProvider>
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <BrowserRouter>
                <Suspense
                  fallback={
                    <div className="loading">
                      <span className="loading-text">CV Analyzer</span>
                    </div>
                  }
                >
                  <a href="#main-content" className="skip-link">
                    Skip to main content
                  </a>
                  <Routes>
                    <Route path="/" element={<LandingPage />} />
                    <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
                    <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
                    <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
                    <Route path="/dashboard" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
                    <Route path="/analyze" element={<PrivateRoute><AnalyzePage /></PrivateRoute>} />
                    <Route path="/feedback" element={<PrivateRoute><FeedbackPage /></PrivateRoute>} />
                    <Route path="/history" element={<PrivateRoute><HistoryPage /></PrivateRoute>} />
                    <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
                    <Route path="/recruiter" element={<RecruiterRoute><RecruiterPage /></RecruiterRoute>} />
                    <Route path="/premium" element={<PrivateRoute><PremiumPage /></PrivateRoute>} />
                    <Route path="/cv-builder" element={<PrivateRoute><CVBuilderPage /></PrivateRoute>} />
                    <Route path="/admin/billing" element={<AdminBillingRoute><AdminBillingPage /></AdminBillingRoute>} />
                    <Route path="/pricing" element={<PricingPage />} />
                    <Route path="/privacy" element={<PrivacyPage />} />
                    <Route path="/terms" element={<TermsPage />} />
                    <Route path="/blog" element={<PrivateRoute><BlogPage /></PrivateRoute>} />
                    <Route path="/blog/:slug" element={<PrivateRoute><BlogDetailPage /></PrivateRoute>} />
                    <Route path="*" element={<NotFoundPage />} />
                  </Routes>
                </Suspense>
                <CookieConsent />
                <BackToTop />
                <FeedbackButton />
              </BrowserRouter>
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </LanguageProvider>
    </ErrorBoundary>
  )
}