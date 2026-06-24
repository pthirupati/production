/** PeopleSoft Fluid UI seed data — merged with backend session in the simulator. */

export const PS_FLUID_TILES = [
  { id: 'pay', title: 'My Pay', subtitle: 'Review paycheck & direct deposit', icon: '💵', color: '#1b3a5c' },
  { id: 'benefits', title: 'My Benefits', subtitle: 'Open enrollment & plans', icon: '🏥', color: '#c74634' },
  { id: 'time', title: 'My Time', subtitle: 'Report & view time', icon: '⏱', color: '#2d6a4f' },
  { id: 'directory', title: 'Company Directory', subtitle: 'Find colleagues', icon: '📇', color: '#5c4ee5' },
  { id: 'training', title: 'Training', subtitle: 'Learning & development', icon: '📚', color: '#e09f3e' },
  { id: 'expenses', title: 'Expenses', subtitle: 'Travel & expense reports', icon: '✈️', color: '#457b9d' },
  { id: 'jobs', title: 'Job Openings', subtitle: 'Internal recruiting', icon: '💼', color: '#6d597a' },
  { id: 'jobdata', title: 'Job Data', subtitle: 'Work location & employment', icon: '📋', color: '#1b3a5c' },
]

export const PS_NAV_MENU = [
  { label: 'Home', items: [] },
  { label: 'Employee Self Service', items: ['Personal Details', 'Benefits', 'Time', 'Payroll', 'Travel and Expenses'] },
  { label: 'Workforce Administration', items: ['Job Information', 'Personal Information', 'Organizational Relationships'] },
  { label: 'Payroll for North America', items: ['Employee Pay Data', 'Payroll Processing', 'Pay Period Calendars'] },
  { label: 'Benefits', items: ['Administer Base Benefits', 'eBenefits', 'Open Enrollment'] },
  { label: 'Time and Labor', items: ['Report Time', 'View Time', 'Process Time'] },
  { label: 'Recruiting', items: ['Find Job Openings', 'Create Job Opening', 'Search Applicants'] },
]

export const PS_JOB_DATA = {
  emplId: '00001234',
  name: 'Jane Smith',
  effectiveDate: '2026-01-01',
  company: 'FIXIT',
  businessUnit: 'ITOPS',
  department: 'Infrastructure',
  location: 'Hyderabad',
  jobCode: 'SYSADMIN',
  salaryPlan: 'IND-IT-01',
  status: 'Active',
}

export const PS_BENEFITS_STEPS = [
  { key: 'personal', label: 'Personal Information' },
  { key: 'health', label: 'Health Benefits' },
  { key: 'life', label: 'Life and AD&D' },
  { key: 'disability', label: 'Disability' },
  { key: 'savings', label: 'Savings' },
  { key: 'review', label: 'Review and Submit' },
]

export const PS_HEALTH_PLANS = [
  { id: 'ppo', name: 'PPO Select', deductible: '$1,500', oop: '$6,000', premium: '$142/mo' },
  { id: 'hdhp', name: 'HDHP + HSA', deductible: '$3,000', oop: '$7,500', premium: '$98/mo' },
  { id: 'hmo', name: 'HMO Classic', deductible: '$500', oop: '$4,000', premium: '$165/mo' },
]

export const PS_PAYCHECK = {
  company: 'FixitLab India Pvt Ltd',
  periodStart: '2026-06-01',
  periodEnd: '2026-06-15',
  payDate: '2026-06-20',
  earnings: [
    { type: 'Regular Pay', hours: 80, amount: 4250.0 },
    { type: 'Overtime', hours: 4, amount: 318.75 },
  ],
  taxes: [
    { type: 'Federal Income Tax', amount: -612.0 },
    { type: 'State Income Tax', amount: -198.5 },
  ],
  deductions: [
    { type: '401(k)', amount: -255.0 },
    { type: 'Medical PPO', amount: -71.0 },
  ],
  netPay: 3432.25,
  ytdNet: 41287.5,
  deposit: 'HDFC ****4821',
}

export const PS_PROCESS_INSTANCES = [
  { instance: 104821, process: 'GP_PAYROLL', description: 'Pay Calculation', server: 'PSNT', status: 'Success', runDt: '2026-06-20 02:15' },
  { instance: 104819, process: 'AE_TM_APRV', description: 'Time Approval', server: 'PSNT', status: 'Error', runDt: '2026-06-19 18:42' },
  { instance: 104815, process: 'IB_SYNC', description: 'Integration Sync', server: 'PSWEB', status: 'Running', runDt: '2026-06-19 16:00' },
]
