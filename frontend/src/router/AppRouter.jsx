import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Suspense, useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { lazyWithRetry } from '../utils/lazyWithRetry'
import ErrorBoundary from '../components/ErrorBoundary'

// Layouts (always loaded)
import MainLayout from '../components/layout/MainLayout'
import AdminLayout from '../components/layout/AdminLayout'
import PublicLayout from '../components/layout/PublicLayout'

// Eagerly loaded pages (critical path)
import Home from '../pages/Home'
import Login from '../pages/auth/Login'
import Register from '../pages/auth/Register'

// Lazy-loaded pages (code-split)
const ForgotPassword = lazyWithRetry(() => import('../pages/auth/ForgotPassword'))
const ResetPassword = lazyWithRetry(() => import('../pages/auth/ResetPassword'))
const Pricing = lazyWithRetry(() => import('../pages/Pricing'))
const Dashboard = lazyWithRetry(() => import('../pages/Dashboard'))
const Technologies = lazyWithRetry(() => import('../pages/Technologies'))
const TechnologyDetail = lazyWithRetry(() => import('../pages/TechnologyDetail'))
const Scenarios = lazyWithRetry(() => import('../pages/Scenarios'))
const ScenarioDetail = lazyWithRetry(() => import('../pages/ScenarioDetail'))
const LabRunner = lazyWithRetry(() => import('../pages/LabRunner'))
const JiraTicketPage = lazyWithRetry(() => import('../pages/JiraTicketPage'))
const Leaderboard = lazyWithRetry(() => import('../pages/Leaderboard'))
const Profile = lazyWithRetry(() => import('../pages/Profile'))
const Subscriptions = lazyWithRetry(() => import('../pages/Subscriptions'))
const Bookmarks = lazyWithRetry(() => import('../pages/Bookmarks'))
const About = lazyWithRetry(() => import('../pages/About'))
const Blog = lazyWithRetry(() => import('../pages/Blog'))
const BlogPost = lazyWithRetry(() => import('../pages/BlogPost'))
const OAuthCallback = lazyWithRetry(() => import('../pages/auth/OAuthCallback'))
const LabHistory = lazyWithRetry(() => import('../pages/LabHistory'))
const Achievements = lazyWithRetry(() => import('../pages/Achievements'))
const SessionReplay = lazyWithRetry(() => import('../pages/SessionReplay'))
const Community = lazyWithRetry(() => import('../pages/Community'))
const CertificateVerify = lazyWithRetry(() => import('../pages/CertificateVerify'))
const PaymentPage = lazyWithRetry(() => import('../pages/PaymentPage'))
const Privacy = lazyWithRetry(() => import('../pages/Privacy'))
const Terms = lazyWithRetry(() => import('../pages/Terms'))
const RefundCancellation = lazyWithRetry(() => import('../pages/RefundCancellation'))
const AcceptableUse = lazyWithRetry(() => import('../pages/AcceptableUse'))
const Contact = lazyWithRetry(() => import('../pages/Contact'))
const ContactSales = lazyWithRetry(() => import('../pages/ContactSales'))
const FAQ = lazyWithRetry(() => import('../pages/FAQ'))
const NotFound = lazyWithRetry(() => import('../pages/NotFound'))
const AdminDashboard = lazyWithRetry(() => import('../pages/admin/AdminDashboard'))
const AdminScenarios = lazyWithRetry(() => import('../pages/admin/AdminScenarios'))
const AdminLabProvisioning = lazyWithRetry(() => import('../pages/admin/AdminLabProvisioning'))
const AdminTechnologies = lazyWithRetry(() => import('../pages/admin/AdminTechnologies'))
const AdminCertifications = lazyWithRetry(() => import('../pages/admin/AdminCertifications'))
const AdminUsers = lazyWithRetry(() => import('../pages/admin/AdminUsers'))
const AdminLabs = lazyWithRetry(() => import('../pages/admin/AdminLabs'))
const AdminSubscriptions = lazyWithRetry(() => import('../pages/admin/AdminSubscriptions'))
const AdminThreads = lazyWithRetry(() => import('../pages/admin/AdminThreads'))
const AdminJira = lazyWithRetry(() => import('../pages/admin/AdminJira'))
const AdminItsm = lazyWithRetry(() => import('../pages/admin/AdminItsm'))
const AdminCoupons = lazyWithRetry(() => import('../pages/admin/AdminCoupons'))
const AdminAnalytics = lazyWithRetry(() => import('../pages/admin/AdminAnalytics'))
const AdminFunnel = lazyWithRetry(() => import('../pages/admin/AdminFunnel'))
const AdminTeams = lazyWithRetry(() => import('../pages/admin/AdminTeams'))
const AdminSecurity = lazyWithRetry(() => import('../pages/admin/AdminSecurity'))
const AdminAuditLogs = lazyWithRetry(() => import('../pages/admin/AdminAuditLogs'))
const AdminInvoices = lazyWithRetry(() => import('../pages/admin/AdminInvoices'))
const AdminMonitoring = lazyWithRetry(() => import('../pages/admin/AdminMonitoring'))
const Team = lazyWithRetry(() => import('../pages/Team'))
const AdminSettings = lazyWithRetry(() => import('../pages/admin/AdminSettings'))
const AdminCampaigns = lazyWithRetry(() => import('../pages/admin/AdminCampaigns'))
const AdminSales = lazyWithRetry(() => import('../pages/admin/AdminSales'))
const InterviewHub = lazyWithRetry(() => import('../pages/interviews/InterviewHub'))
const InterviewSetup = lazyWithRetry(() => import('../pages/interviews/InterviewSetup'))
const InterviewCampaign = lazyWithRetry(() => import('../pages/interviews/InterviewCampaign'))
const InterviewRoom = lazyWithRetry(() => import('../pages/interviews/InterviewRoom'))
const InterviewReport = lazyWithRetry(() => import('../pages/interviews/InterviewReport'))
const AdminInterviews = lazyWithRetry(() => import('../pages/admin/AdminInterviews'))
const AdminCertificates = lazyWithRetry(() => import('../pages/admin/AdminCertificates'))
const InterviewLanding = lazyWithRetry(() => import('../pages/interviews/InterviewLanding'))
const InterviewAnalytics = lazyWithRetry(() => import('../pages/interviews/InterviewAnalytics'))
const InterviewTemplates = lazyWithRetry(() => import('../pages/interviews/InterviewTemplates'))
const RecruiterCompare = lazyWithRetry(() => import('../pages/interviews/RecruiterCompare'))
const InterviewInvite = lazyWithRetry(() => import('../pages/interviews/InterviewInvite'))
const AsyncVideoRoom = lazyWithRetry(() => import('../pages/interviews/AsyncVideoRoom'))
const VMwareSimulator = lazyWithRetry(() => import('../pages/vmware/VMwareSimulator'))
const Unsubscribe = lazyWithRetry(() => import('../pages/Unsubscribe'))
const Changelog = lazyWithRetry(() => import('../pages/Changelog'))
const Tutorials = lazyWithRetry(() => import('../pages/tutorials/Tutorials'))
const TutorialDetail = lazyWithRetry(() => import('../pages/tutorials/TutorialDetail'))
const Certifications = lazyWithRetry(() => import('../pages/certifications/Certifications'))
const CertificationDetail = lazyWithRetry(() => import('../pages/certifications/CertificationDetail'))
const Playgrounds = lazyWithRetry(() => import('../pages/playgrounds/Playgrounds'))
const PlaygroundDetail = lazyWithRetry(() => import('../pages/playgrounds/PlaygroundDetail'))
const Journeys = lazyWithRetry(() => import('../pages/journeys/Journeys'))
const JourneyDetail = lazyWithRetry(() => import('../pages/journeys/JourneyDetail'))
const Projects = lazyWithRetry(() => import('../pages/projects/Projects'))
const ProjectDetail = lazyWithRetry(() => import('../pages/projects/ProjectDetail'))
const SimulatorLauncher = lazyWithRetry(() => import('../pages/SimulatorLauncher'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
        {/* surface-400, not surface-500: measured against the runtime tokens in
            index.css, surface-500 body copy is 6.18:1 on the dark bg but only
            3.66:1 in light mode (--s-500 120,135,155 on --s-950 255,255,255),
            under the 4.5:1 AA floor. surface-400 measures 9.35:1 dark / 6.46:1
            light. Fixed at the call site rather than by redefining --s-500,
            which is shared with borders and disabled states. */}
        <span className="text-sm text-surface-400">Loading...</span>
      </div>
    </div>
  )
}

function useHydrated() {
  const [hydrated, setHydrated] = useState(() => useAuthStore.persist.hasHydrated())
  useEffect(() => {
    if (hydrated) return
    setHydrated(useAuthStore.persist.hasHydrated())
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true))
    return unsub
  }, [hydrated])
  return hydrated
}

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  const hydrated = useHydrated()
  const location = useLocation()
  if (!hydrated) return <PageLoader />
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return children
}

function AdminRoute({ children }) {
  const { isAuthenticated, user } = useAuthStore()
  const hydrated = useHydrated()
  const location = useLocation()
  if (!hydrated) return <PageLoader />
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  if (!user?.is_staff) return <Navigate to="/dashboard" replace />
  return children
}

export default function AppRouter() {
  // Route-level error boundary keyed by pathname: a crash on one page (e.g. a
  // future render loop) shows the recovery UI for THAT page, and simply
  // navigating elsewhere remounts a fresh boundary instead of leaving the whole
  // app wedged on the global "Something went wrong" screen until a full reload.
  const location = useLocation()
  return (
    <ErrorBoundary key={location.pathname}>
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
        <Route path="/refunds" element={<RefundCancellation />} />
        <Route path="/acceptable-use" element={<AcceptableUse />} />
        {/* DO NOT delete for having zero in-app links — that is by design. The only
            producer is backend marketing_unsubscribe_url() (apps/notifications/
            unsubscribe.py:29), i.e. a link inside an email. Removing this page
            breaks CAN-SPAM / RFC 8058 list-unsubscribe compliance and no frontend
            test would go red. Note the backend also builds a SEPARATE POST-able
            one-click API URL (unsubscribe.py:48) for mail providers; the two are
            not interchangeable and must not be collapsed. Allowlisted in
            routeReachability.test.js rather than linked. */}
        <Route path="/unsubscribe" element={<Unsubscribe />} />
        <Route path="/changelog" element={<PublicLayout><Changelog /></PublicLayout>} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/contact-sales" element={<ContactSales />} />
        <Route path="/support" element={<Navigate to="/contact" replace />} />
        <Route path="/faq" element={<FAQ />} />
        <Route path="/mock-interviews" element={<InterviewLanding />} />
        <Route path="/verify-certificate" element={<CertificateVerify />} />
        <Route path="/tutorials" element={<Tutorials />} />
        <Route path="/tutorials/:slug" element={<TutorialDetail />} />
        <Route path="/certifications" element={<Certifications />} />
        <Route path="/certifications/:slug" element={<CertificationDetail />} />
        <Route path="/playgrounds" element={<Playgrounds />} />
        <Route path="/playgrounds/:slug" element={<PlaygroundDetail />} />
        {/* §C4 — Learning Journeys. API + seed + Dashboard next-step already
            existed; these routes were the missing browse surface. */}
        <Route path="/journeys" element={<Journeys />} />
        <Route path="/journeys/:slug" element={<JourneyDetail />} />
        {/* §C3 — Capstone projects catalog (was technology-tab only). */}
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:slug" element={<ProjectDetail />} />
        <Route path="/interviews/invite/:token" element={<InterviewInvite />} />
        <Route path="/payment" element={<ProtectedRoute><PaymentPage /></ProtectedRoute>} />
        <Route path="/jira/:issueKey" element={<ProtectedRoute><JiraTicketPage /></ProtectedRoute>} />
        <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
        {/* Not duplicates (audit §H8 assumed they were). VMwareSimulator:835 reads
            `searchParams.get('session') || paramSessionId`, and both forms have live
            producers: /vmware/:sessionId from LabJourneyStrip.jsx:20 and
            TerraformWorkspaceIde.jsx:244, /vmware-sim?session= from the pure-VMware
            redirect at LabRunner.jsx:772. Deleting either strips a real entry point. */}
        <Route path="/vmware/:sessionId" element={<ProtectedRoute><VMwareSimulator /></ProtectedRoute>} />
        <Route path="/vmware-sim" element={<ProtectedRoute><VMwareSimulator /></ProtectedRoute>} />

        {/* No standalone /aws-sim/* route (audit §H5). Its only producer,
            awsConsoleUrlForResource(), was exported but never imported, and the
            standalone AwsConsole renders zero lab chrome — no Hints/Check/Extend/
            Stop/Back — so anyone reaching it was stranded. The console is alive on
            the embedded path only: AwsLabOverlay declares its own /aws-sim/* route
            inside a MemoryRouter (AwsLabOverlay.jsx:94), which is what
            serviceFromPath() in AwsConsole matches against. */}

        {/* Protected routes */}
        <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/technologies" element={<Technologies />} />
          <Route path="/technologies/:slug" element={<TechnologyDetail />} />
          <Route path="/simulators" element={<SimulatorLauncher />} />
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
          <Route path="/interviews/round/:roundId" element={<InterviewRoom />} />
          <Route path="/interviews/round/:roundId/report" element={<InterviewReport />} />
          <Route path="/interviews/analytics" element={<InterviewAnalytics />} />
          <Route path="/interviews/templates" element={<InterviewTemplates />} />
          <Route path="/interviews/compare" element={<RecruiterCompare />} />
          <Route path="/interviews/async/:roundId" element={<AsyncVideoRoom />} />
        </Route>

        {/* Admin routes */}
        <Route element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/scenarios" element={<AdminScenarios />} />
          <Route path="/admin/lab-provisioning" element={<AdminLabProvisioning />} />
          <Route path="/admin/technologies" element={<AdminTechnologies />} />
          <Route path="/admin/certifications" element={<AdminCertifications />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="/admin/labs" element={<AdminLabs />} />
          <Route path="/admin/monitoring" element={<AdminMonitoring />} />
          <Route path="/admin/subscriptions" element={<AdminSubscriptions />} />
          <Route path="/admin/certificates" element={<AdminCertificates />} />
          <Route path="/admin/invoices" element={<AdminInvoices />} />
          <Route path="/admin/jira" element={<AdminJira />} />
          <Route path="/admin/itsm" element={<AdminItsm />} />
          <Route path="/admin/threads" element={<AdminThreads />} />
          <Route path="/admin/settings" element={<AdminSettings />} />
          <Route path="/admin/campaigns" element={<AdminCampaigns />} />
          <Route path="/admin/sales" element={<AdminSales />} />
          <Route path="/admin/coupons" element={<AdminCoupons />} />
          <Route path="/admin/analytics" element={<AdminAnalytics />} />
          <Route path="/admin/funnel" element={<AdminFunnel />} />
          <Route path="/admin/teams" element={<AdminTeams />} />
          <Route path="/admin/security" element={<AdminSecurity />} />
          <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />
          <Route path="/admin/interviews" element={<AdminInterviews />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
    </ErrorBoundary>
  )
}
