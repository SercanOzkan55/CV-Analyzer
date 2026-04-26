import React, { lazy, Suspense } from "react"
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom"
import { AnimatePresence } from "framer-motion"

import ErrorBoundary from "./components/ErrorBoundary"
import DevContextGuard from "./components/DevContextGuard"
import { ThemeProvider } from "./context/ThemeContext"
import { LanguageProvider } from "./i18n/LanguageContext"
import { AuthProvider, useAuth } from "./context/AuthContext"
import { RecruiterSessionProvider } from "./context/RecruiterSessionContext"
import { ToastProvider } from "./components/Toast"
import LoadingScreen from "./components/LoadingScreen"
import PageTransition from "./components/PageTransition"

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
const CareerStudioPage = lazy(() => import("./pages/CareerStudioPage"))
const FeedbackPage = lazy(() => import("./pages/FeedbackPage"))
const HistoryPage = lazy(() => import("./pages/HistoryPage"))
const SettingsPage = lazy(() => import("./pages/SettingsPage"))
const RecruiterPage = lazy(() => import("./pages/RecruiterPage"))
const RecruiterHubPage = lazy(() => import("./pages/RecruiterHubPage"))
const PricingPage = lazy(() => import("./pages/PricingPage"))
const PremiumPage = lazy(() => import("./pages/PremiumPage"))
const CVBuilderPage = lazy(() => import("./pages/CVBuilderPage"))
const AdminBillingPage = lazy(() => import("./pages/AdminBillingPage"))
const PrivacyPage = lazy(() => import("./pages/PrivacyPage"))
const TermsPage = lazy(() => import("./pages/TermsPage"))
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"))
const BlogPage = lazy(() => import("./pages/BlogPage"))
const AboutPage = lazy(() => import("./pages/AboutPage"))
const BlogDetailPage = lazy(() => import("./pages/BlogDetailPage"))
const ProfilePage = lazy(() => import("./pages/ProfilePage"))
const ComparePage = lazy(() => import("./pages/ComparePage"))
const MyCVsPage = lazy(() => import("./pages/MyCVsPage"))
const SharedAnalysisPage = lazy(() => import("./pages/SharedAnalysisPage"))
const CoverLetterPage = lazy(() => import("./pages/CoverLetterPage"))
const InterviewSimulatorPage = lazy(() => import("./pages/InterviewSimulatorPage"))
const JobTrackerPage = lazy(() => import("./pages/JobTrackerPage"))


// ---------- CONFIG ----------

const PRIVATE_MODE = import.meta.env.VITE_PRIVATE_MODE === 'true'
const REGISTRATION_DISABLED = PRIVATE_MODE || import.meta.env.VITE_REGISTRATION_DISABLED === 'true'

// ---------- ROUTE GUARDS ----------

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen />
  return user ? children : <Navigate to="/login" />
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen />
  return user ? <Navigate to="/dashboard" /> : children
}

function RecruiterRoute({ children }) {
  const { user, loading, planLoading, role, isBillingAdmin } = useAuth()
  if (loading || planLoading) return <LoadingScreen />
  if (!user) return <Navigate to="/login" />
  
  // Lokal/Private moddaysa yetki kontrolünü esnet (Demo kolaylığı için)
  if (PRIVATE_MODE) return children;

  if (role !== "recruiter" && !isBillingAdmin) {
    return <Navigate to="/pricing" state={{ reason: "recruiter_required" }} />
  }
  return children
}

function AdminBillingRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen />
  if (!user) return <Navigate to="/login" />

  const configured = String(import.meta.env.VITE_BILLING_ADMIN_EMAILS || "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)

  const email = String(user?.email || "").trim().toLowerCase()
  if (!email || !configured.includes(email)) return <Navigate to="/dashboard" />

  return children
}

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={PRIVATE_MODE ? <PrivateRoute><Navigate to="/dashboard" /></PrivateRoute> : <PageTransition><LandingPage /></PageTransition>} />
        <Route path="/login" element={<PublicRoute><PageTransition><LoginPage /></PageTransition></PublicRoute>} />
        {!REGISTRATION_DISABLED && <Route path="/register" element={<PublicRoute><PageTransition><RegisterPage /></PageTransition></PublicRoute>} />}
        <Route path="/forgot-password" element={<PublicRoute><PageTransition><ForgotPasswordPage /></PageTransition></PublicRoute>} />
        <Route path="/dashboard" element={<PrivateRoute><PageTransition><DashboardPage /></PageTransition></PrivateRoute>} />
        <Route path="/analyze" element={<PrivateRoute><PageTransition><AnalyzePage /></PageTransition></PrivateRoute>} />
        <Route path="/career-studio" element={<PrivateRoute><PageTransition><CareerStudioPage /></PageTransition></PrivateRoute>} />
        <Route path="/feedback" element={<PrivateRoute><PageTransition><FeedbackPage /></PageTransition></PrivateRoute>} />
        <Route path="/history" element={<PrivateRoute><PageTransition><HistoryPage /></PageTransition></PrivateRoute>} />
        <Route path="/settings" element={<PrivateRoute><PageTransition><SettingsPage /></PageTransition></PrivateRoute>} />
        <Route path="/profile" element={<PrivateRoute><PageTransition><ProfilePage /></PageTransition></PrivateRoute>} />
        <Route path="/compare" element={<PrivateRoute><PageTransition><ComparePage /></PageTransition></PrivateRoute>} />
        <Route path="/my-cvs" element={<PrivateRoute><PageTransition><MyCVsPage /></PageTransition></PrivateRoute>} />
        <Route path="/recruiter" element={<RecruiterRoute><PageTransition><RecruiterPage /></PageTransition></RecruiterRoute>} />
        <Route path="/recruiter-hub" element={<Navigate to="/recruiter" replace />} />
        <Route path="/premium" element={<PrivateRoute><PageTransition><PremiumPage /></PageTransition></PrivateRoute>} />
        <Route path="/cv-builder" element={<PrivateRoute><PageTransition><CVBuilderPage /></PageTransition></PrivateRoute>} />
        <Route path="/cover-letter" element={<PrivateRoute><PageTransition><CoverLetterPage /></PageTransition></PrivateRoute>} />
        <Route path="/interview-simulator" element={<PrivateRoute><PageTransition><InterviewSimulatorPage /></PageTransition></PrivateRoute>} />
        <Route path="/job-tracker" element={<PrivateRoute><PageTransition><JobTrackerPage /></PageTransition></PrivateRoute>} />
        <Route path="/admin/billing" element={<AdminBillingRoute><PageTransition><AdminBillingPage /></PageTransition></AdminBillingRoute>} />
        <Route path="/pricing" element={PRIVATE_MODE ? <PrivateRoute><PageTransition><PricingPage /></PageTransition></PrivateRoute> : <PageTransition><PricingPage /></PageTransition>} />
        <Route path="/privacy" element={<PageTransition><PrivacyPage /></PageTransition>} />
        <Route path="/terms" element={<PageTransition><TermsPage /></PageTransition>} />
        <Route path="/about" element={<PageTransition><AboutPage /></PageTransition>} />
        <Route path="/shared/:shareToken" element={<PageTransition><SharedAnalysisPage /></PageTransition>} />
        <Route path="/blog" element={PRIVATE_MODE ? <PrivateRoute><PageTransition><BlogPage /></PageTransition></PrivateRoute> : <PageTransition><BlogPage /></PageTransition>} />
        <Route path="/blog/:slug" element={PRIVATE_MODE ? <PrivateRoute><PageTransition><BlogDetailPage /></PageTransition></PrivateRoute> : <PageTransition><BlogDetailPage /></PageTransition>} />
        <Route path="*" element={<PageTransition><NotFoundPage /></PageTransition>} />
      </Routes>
    </AnimatePresence>
  )
}


// ---------- APP ----------


export default function App() {
  return (
    <ErrorBoundary fallback={<div className="error-fallback">Bir hata oluştu. Lütfen sayfayı yenileyin veya destek ekibiyle iletişime geçin.</div>}>
      <LanguageProvider>
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <RecruiterSessionProvider>
                <BrowserRouter>
                  <DevContextGuard />
                  <a href="#main-content" className="skip-link">Skip to main content</a>
                  <Suspense fallback={<LoadingScreen />}>
                    <AnimatedRoutes />
                  </Suspense>
                  <CookieConsent />
                  <BackToTop />
                  <FeedbackButton />
                </BrowserRouter>
              </RecruiterSessionProvider>
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </LanguageProvider>
    </ErrorBoundary>
  )
}