import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { useAuthStore } from '../store/authStore'

// Layouts (always loaded)
import MainLayout from '../components/layout/MainLayout'
import AdminLayout from '../components/layout/AdminLayout'
import PublicLayout from '../components/layout/PublicLayout'

// Eagerly loaded pages (critical path)
import Home from '../pages/Home'
import Login from '../pages/auth/Login'
import Register from '../pages/auth/Register'

// Lazy-loaded pages (code-split)
const ForgotPassword = lazy(() => import('../pages/auth/ForgotPassword'))
const ResetPassword = lazy(() => import('../pages/auth/ResetPassword'))
const Pricing = lazy(() => import('../pages/Pricing'))
const Dashboard = lazy(() => import('../pages/Dashboard'))
const Technologies = lazy(() => import('../pages/Technologies'))
const TechnologyDetail = lazy(() => import('../pages/TechnologyDetail'))
const Scenarios = lazy(() => import('../pages/Scenarios'))
const ScenarioDetail = lazy(() => import('../pages/ScenarioDetail'))
const LabRunner = lazy(() => import('../pages/LabRunner'))
const JiraTicketPage = lazy(() => import('../pages/JiraTicketPage'))
const Leaderboard = lazy(() => import('../pages/Leaderboard'))
const Profile = lazy(() => import('../pages/Profile'))
const Subscriptions = lazy(() => import('../pages/Subscriptions'))
const Bookmarks = lazy(() => import('../pages/Bookmarks'))
const About = lazy(() => import('../pages/About'))
const Blog = lazy(() => import('../pages/Blog'))
const BlogPost = lazy(() => import('../pages/BlogPost'))
const OAuthCallback = lazy(() => import('../pages/auth/OAuthCallback'))
const LabHistory = lazy(() => import('../pages/LabHistory'))
const Achievements = lazy(() => import('../pages/Achievements'))
const SessionReplay = lazy(() => import('../pages/SessionReplay'))
const Community = lazy(() => import('../pages/Community'))
const CertificateVerify = lazy(() => import('../pages/CertificateVerify'))
const PaymentPage = lazy(() => import('../pages/PaymentPage'))
const Privacy = lazy(() => import('../pages/Privacy'))
const Terms = lazy(() => import('../pages/Terms'))
const Contact = lazy(() => import('../pages/Contact'))
const FAQ = lazy(() => import('../pages/FAQ'))
const NotFound = lazy(() => import('../pages/NotFound'))
const AdminDashboard = lazy(() => import('../pages/admin/AdminDashboard'))
const AdminScenarios = lazy(() => import('../pages/admin/AdminScenarios'))
const AdminTechnologies = lazy(() => import('../pages/admin/AdminTechnologies'))
const AdminUsers = lazy(() => import('../pages/admin/AdminUsers'))
const AdminLabs = lazy(() => import('../pages/admin/AdminLabs'))
const AdminSubscriptions = lazy(() => import('../pages/admin/AdminSubscriptions'))
const AdminThreads = lazy(() => import('../pages/admin/AdminThreads'))
const AdminJira = lazy(() => import('../pages/admin/AdminJira'))
const AdminCoupons = lazy(() => import('../pages/admin/AdminCoupons'))
const AdminAnalytics = lazy(() => import('../pages/admin/AdminAnalytics'))
const AdminTeams = lazy(() => import('../pages/admin/AdminTeams'))
const AdminSecurity = lazy(() => import('../pages/admin/AdminSecurity'))
const AdminAuditLogs = lazy(() => import('../pages/admin/AdminAuditLogs'))
const AdminInvoices = lazy(() => import('../pages/admin/AdminInvoices'))
const AdminMonitoring = lazy(() => import('../pages/admin/AdminMonitoring'))
const Team = lazy(() => import('../pages/Team'))
const AdminSettings = lazy(() => import('../pages/admin/AdminSettings'))
const InterviewHub = lazy(() => import('../pages/interviews/InterviewHub'))
const InterviewSetup = lazy(() => import('../pages/interviews/InterviewSetup'))
const InterviewCampaign = lazy(() => import('../pages/interviews/InterviewCampaign'))
const InterviewRoom = lazy(() => import('../pages/interviews/InterviewRoom'))
const InterviewReport = lazy(() => import('../pages/interviews/InterviewReport'))
const AdminInterviews = lazy(() => import('../pages/admin/AdminInterviews'))
const AdminCertificates = lazy(() => import('../pages/admin/AdminCertificates'))
const InterviewLanding = lazy(() => import('../pages/interviews/InterviewLanding'))
const Unsubscribe = lazy(() => import('../pages/Unsubscribe'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
        <span className="text-sm text-surface-500">Loading...</span>
      </div>
    </div>
  )
}

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

function AdminRoute({ children }) {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!user?.is_staff) return <Navigate to="/dashboard" replace />
  return children
}

export default function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/about" element={<About />} />
        <Route path="/blog" element={<PublicLayout><Blog /></PublicLayout>} />
        <Route path="/blog/:slug" element={<PublicLayout><BlogPost /></PublicLayout>} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/unsubscribe" element={<Unsubscribe />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/support" element={<Navigate to="/contact" replace />} />
        <Route path="/faq" element={<FAQ />} />
        <Route path="/mock-interviews" element={<InterviewLanding />} />
        <Route path="/verify-certificate" element={<CertificateVerify />} />
        <Route path="/payment" element={<ProtectedRoute><PaymentPage /></ProtectedRoute>} />
        <Route path="/jira/:issueKey" element={<ProtectedRoute><JiraTicketPage /></ProtectedRoute>} />
        <Route path="/auth/callback/:provider" element={<OAuthCallback />} />

        {/* Protected routes */}
        <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/technologies" element={<Technologies />} />
          <Route path="/technologies/:slug" element={<TechnologyDetail />} />
          <Route path="/scenarios" element={<Scenarios />} />
          <Route path="/scenarios/:slug" element={<ScenarioDetail />} />
          <Route path="/lab/:sessionId" element={<LabRunner />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/bookmarks" element={<Bookmarks />} />
          <Route path="/lab-history" element={<LabHistory />} />
          <Route path="/achievements" element={<Achievements />} />
          <Route path="/session-replay/:sessionId" element={<SessionReplay />} />
          <Route path="/community" element={<Community />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route path="/team" element={<Team />} />
          <Route path="/interviews" element={<InterviewHub />} />
          <Route path="/interviews/setup" element={<InterviewSetup />} />
          <Route path="/interviews/campaign/:campaignId" element={<InterviewCampaign />} />
          <Route path="/interviews/room/:roundId" element={<InterviewRoom />} />
          <Route path="/interviews/round/:roundId/report" element={<InterviewReport />} />
        </Route>

        {/* Admin routes */}
        <Route element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/scenarios" element={<AdminScenarios />} />
          <Route path="/admin/technologies" element={<AdminTechnologies />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="/admin/labs" element={<AdminLabs />} />
          <Route path="/admin/monitoring" element={<AdminMonitoring />} />
          <Route path="/admin/subscriptions" element={<AdminSubscriptions />} />
          <Route path="/admin/certificates" element={<AdminCertificates />} />
          <Route path="/admin/invoices" element={<AdminInvoices />} />
          <Route path="/admin/jira" element={<AdminJira />} />
          <Route path="/admin/threads" element={<AdminThreads />} />
          <Route path="/admin/settings" element={<AdminSettings />} />
          <Route path="/admin/coupons" element={<AdminCoupons />} />
          <Route path="/admin/analytics" element={<AdminAnalytics />} />
          <Route path="/admin/teams" element={<AdminTeams />} />
          <Route path="/admin/security" element={<AdminSecurity />} />
          <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />
          <Route path="/admin/interviews" element={<AdminInterviews />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
