import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAwsStore } from './store/awsStore'
import { Flash } from './ui/primitives'
import TopNav from './layout/TopNav'
import LeftNav from './layout/LeftNav'
import CloudShell from './layout/CloudShell'
import { SERVICE_KEYS } from './layout/serviceNav'
import '../../styles/aws-sim.css'

import ConsoleHome from './pages/ConsoleHome'
import Ec2Dashboard from './pages/ec2/Ec2Dashboard'
import InstanceList from './pages/ec2/InstanceList'
import InstanceDetail from './pages/ec2/InstanceDetail'
import LaunchWizard from './pages/ec2/LaunchWizard'
import { SecurityGroupList, KeyPairList, VolumeList, ElasticIpList, AmiList } from './pages/ec2/Ec2Lists'
import { BucketList, BucketDetail } from './pages/s3/S3Pages'
import { IamDashboard, UserList, GroupList, RoleList, PolicyList } from './pages/iam/IamPages'
import { VpcDashboard, VpcList, SubnetList, RouteTableList, InternetGatewayList } from './pages/vpc/VpcPages'
import { CloudWatchOverview, AlarmList } from './pages/cloudwatch/CloudWatchPages'
import { BillingDashboard, GenericResourceDetail, GenericResourceList, GenericServiceHome } from './pages/generic/GenericServicePages'

// Which service the URL belongs to (drives the left nav).
function serviceFromPath(pathname) {
  const m = pathname.match(/\/aws-sim\/([^/]+)/)
  if (!m) return null
  const seg = m[1]
  if (SERVICE_KEYS.includes(seg)) return seg
  return null
}

export default function AwsConsole({ embedded = false }) {
  const location = useLocation()
  const darkMode = useAwsStore((s) => s.darkMode)
  const flash = useAwsStore((s) => s.flash)
  const dismissFlash = useAwsStore((s) => s.dismissFlash)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [cloudShellOpen, setCloudShellOpen] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)

  const service = serviceFromPath(location.pathname)
  const rootClass = `aws-sim ${darkMode ? 'aws-dark' : ''}${embedded ? ' aws-embedded' : ''}`
  const rootStyle = embedded
    ? { height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }
    : { height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }

  // Global keyboard shortcuts. Alt+S / "/" focus search (handled in TopNav).
  // Here: "?" toggles the shortcut reference; Escape closes overlays.
  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable
      if (e.key === '?' && !typing) { e.preventDefault(); setShowShortcuts((o) => !o) }
      else if (e.key === 'Escape') {
        if (showShortcuts) setShowShortcuts(false)
        else if (cloudShellOpen) setCloudShellOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cloudShellOpen, showShortcuts])

  return (
    <div className={rootClass} style={rootStyle}>
      <TopNav onToggleSidebar={() => setSidebarOpen((o) => !o)} onToggleCloudShell={() => setCloudShellOpen((o) => !o)} />
      <div className="aws-sim-body">
        {service && sidebarOpen && <LeftNav service={service} />}
        <div className="aws-sim-main" style={{ paddingBottom: cloudShellOpen ? 340 : 0 }}>
          {flash.length > 0 && (
            <div style={{ padding: '12px 20px 0' }}><Flash items={flash} onDismiss={dismissFlash} /></div>
          )}
          <Routes>
            <Route index element={<Navigate to="console/home" replace />} />
            <Route path="console/home" element={<ConsoleHome />} />

            <Route path="ec2/home" element={<Ec2Dashboard />} />
            <Route path="ec2/instances" element={<InstanceList />} />
            <Route path="ec2/instances/:id" element={<InstanceDetail />} />
            <Route path="ec2/launch" element={<LaunchWizard />} />
            <Route path="ec2/amis" element={<AmiList />} />
            <Route path="ec2/volumes" element={<VolumeList />} />
            <Route path="ec2/security-groups" element={<SecurityGroupList />} />
            <Route path="ec2/elastic-ips" element={<ElasticIpList />} />
            <Route path="ec2/key-pairs" element={<KeyPairList />} />

            <Route path="s3" element={<BucketList />} />
            <Route path="s3/buckets/:name" element={<BucketDetail />} />

            <Route path="iam/home" element={<IamDashboard />} />
            <Route path="iam/users" element={<UserList />} />
            <Route path="iam/users/:name" element={<UserList />} />
            <Route path="iam/groups" element={<GroupList />} />
            <Route path="iam/roles" element={<RoleList />} />
            <Route path="iam/policies" element={<PolicyList />} />

            <Route path="vpc/home" element={<VpcDashboard />} />
            <Route path="vpc/vpcs" element={<VpcList />} />
            <Route path="vpc/subnets" element={<SubnetList />} />
            <Route path="vpc/route-tables" element={<RouteTableList />} />
            <Route path="vpc/internet-gateways" element={<InternetGatewayList />} />
            <Route path="vpc/security-groups" element={<SecurityGroupList />} />

            <Route path="cloudwatch/home" element={<CloudWatchOverview />} />
            <Route path="cloudwatch/alarms" element={<AlarmList />} />

            <Route path="billing/home" element={<BillingDashboard />} />
            <Route path=":service/home" element={<GenericServiceHome />} />
            <Route path=":service/:resource" element={<GenericResourceList />} />
            <Route path=":service/:resource/:id" element={<GenericResourceDetail />} />

            <Route path="*" element={<Navigate to="console/home" replace />} />
          </Routes>
          <footer style={{ padding: '16px 20px', borderTop: '1px solid var(--aws-border-light)', fontSize: 12, color: 'var(--aws-text-secondary)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span>© 2024, Amazon Web Services, Inc. or its affiliates. (FixitLab simulation)</span>
            <span style={{ display: 'flex', gap: 16 }}>
              <span style={{ cursor: 'pointer' }}>Privacy</span>
              <span style={{ cursor: 'pointer' }}>Terms</span>
              <span style={{ cursor: 'pointer' }}>Cookie preferences</span>
              <span style={{ cursor: 'pointer' }} onClick={() => setShowShortcuts(true)}>Keyboard shortcuts (?)</span>
            </span>
          </footer>
        </div>
      </div>
      {cloudShellOpen && <CloudShell onClose={() => setCloudShellOpen(false)} />}
      {showShortcuts && (
        <div onClick={() => setShowShortcuts(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--aws-content-bg)', color: 'var(--aws-text-primary)', borderRadius: 6, padding: 24, width: 420, maxWidth: '90vw', boxShadow: 'var(--aws-shadow-lg)' }}>
            <h2 style={{ marginTop: 0 }}>Keyboard shortcuts</h2>
            {[
              ['/', 'Focus global search'],
              ['Alt + S', 'Focus global search'],
              ['?', 'Toggle this shortcut reference'],
              ['Esc', 'Close menus, dialogs, CloudShell'],
            ].map(([k, d]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--aws-border-light)' }}>
                <kbd style={{ fontFamily: 'var(--aws-font-mono)', background: 'var(--aws-page-bg)', padding: '2px 8px', borderRadius: 4, border: '1px solid var(--aws-border)' }}>{k}</kbd>
                <span>{d}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
