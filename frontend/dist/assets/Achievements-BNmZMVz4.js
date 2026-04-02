import{f as N,r as l,z as d,j as e,p as k,x as z,w as f,v as C,k as A}from"./index-CZEVIwuu.js";import{l as g}from"./labs-ClzOpAhD.js";import{a as b}from"./Skeleton-CcmCZ4N6.js";import{A as v}from"./constants-QTM5UTFt.js";import{D as L}from"./download-IVoNjbRd.js";function U(){const{user:a}=N(),[i,c]=l.useState([]),[S,u]=l.useState(null),[j,w]=l.useState(!0),[x,m]=l.useState(!1);l.useEffect(()=>{g.getAchievements().then(c).catch(()=>d.error("Failed to load achievements")).finally(()=>w(!1))},[]);const r=i.filter(t=>t.earned),h=i.filter(t=>!t.earned),y=async()=>{m(!0);try{const t=await g.getAchievementsCertificate();u(t);const s=D(t),n=new Blob([s],{type:"text/html"}),p=URL.createObjectURL(n),o=document.createElement("a");o.href=p,o.download=`FixitLab_Certificate_${t.username}.html`,o.click(),URL.revokeObjectURL(p),d.success("Certificate downloaded! Open it in a browser and print to PDF.")}catch{d.error("Failed to generate certificate")}finally{m(!1)}};return j?e.jsxs("div",{className:"max-w-5xl mx-auto space-y-6",children:[e.jsx(b,{lines:3}),e.jsx("div",{className:"grid sm:grid-cols-2 lg:grid-cols-3 gap-4",children:[...Array(6)].map((t,s)=>e.jsx(b,{lines:2},s))})]}):e.jsxs("div",{className:"max-w-5xl mx-auto space-y-8 animate-fade-in",children:[e.jsxs("div",{className:"flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4",children:[e.jsxs("div",{children:[e.jsxs("h1",{className:"text-2xl font-bold text-white flex items-center gap-3",children:[e.jsx(k,{className:"text-accent-amber",size:28})," Achievements"]}),e.jsxs("p",{className:"text-surface-400 mt-1",children:[r.length," of ",i.length," unlocked"]})]}),r.length>0&&e.jsxs("button",{onClick:y,disabled:x,className:"btn-primary flex items-center gap-2 text-sm",children:[x?e.jsx("div",{className:"w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"}):e.jsx(L,{size:16}),"Download Certificate"]})]}),e.jsxs("div",{className:"glass-card p-5",children:[e.jsxs("div",{className:"flex items-center justify-between text-sm mb-2",children:[e.jsx("span",{className:"text-surface-400",children:"Overall Progress"}),e.jsxs("span",{className:"text-white font-semibold",children:[r.length,"/",i.length]})]}),e.jsx("div",{className:"h-3 bg-surface-800 rounded-full overflow-hidden",children:e.jsx("div",{className:"h-full bg-gradient-to-r from-accent-cyan to-accent-amber rounded-full transition-all duration-700",style:{width:`${r.length/Math.max(i.length,1)*100}%`}})})]}),r.length>0&&e.jsxs("div",{children:[e.jsxs("h2",{className:"text-lg font-semibold text-white mb-4 flex items-center gap-2",children:[e.jsx(z,{size:18,className:"text-accent-amber"})," Unlocked"]}),e.jsx("div",{className:"grid sm:grid-cols-2 lg:grid-cols-3 gap-4",children:r.map(t=>{const s=v[t.key]||{},n=s.icon||f;return e.jsx("div",{className:`glass-card p-5 border ${s.border||"border-surface-700"} hover:scale-[1.02] transition-all`,children:e.jsxs("div",{className:"flex items-start gap-3",children:[e.jsx("div",{className:`w-12 h-12 rounded-xl ${s.bg} flex items-center justify-center shrink-0`,children:e.jsx(n,{size:24,className:s.color})}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("h3",{className:"text-sm font-semibold text-white",children:t.label}),e.jsx("p",{className:"text-xs text-surface-500 mt-0.5",children:s.desc}),e.jsxs("p",{className:"text-[10px] text-surface-600 mt-1.5 flex items-center gap-1",children:[e.jsx(C,{size:10}),t.earned_at?new Date(t.earned_at).toLocaleDateString():"Earned"]})]})]})},t.key)})})]}),h.length>0&&e.jsxs("div",{children:[e.jsxs("h2",{className:"text-lg font-semibold text-surface-400 mb-4 flex items-center gap-2",children:[e.jsx(A,{size:18})," Locked"]}),e.jsx("div",{className:"grid sm:grid-cols-2 lg:grid-cols-3 gap-4",children:h.map(t=>{const s=v[t.key]||{},n=s.icon||f;return e.jsx("div",{className:"glass-card p-5 opacity-50 hover:opacity-70 transition-opacity",children:e.jsxs("div",{className:"flex items-start gap-3",children:[e.jsx("div",{className:"w-12 h-12 rounded-xl bg-surface-800 flex items-center justify-center shrink-0",children:e.jsx(n,{size:24,className:"text-surface-600"})}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("h3",{className:"text-sm font-semibold text-surface-500",children:t.label}),e.jsx("p",{className:"text-xs text-surface-600 mt-0.5",children:s.desc})]})]})},t.key)})})]})]})}function D(a){const i=a.achievements.map(c=>`<div style="display:inline-block;margin:6px 8px;padding:6px 14px;background:#1e293b;border:1px solid #334155;border-radius:8px;font-size:13px;color:#e2e8f0;">${c.name}<br><span style="font-size:10px;color:#94a3b8;">${c.earned_at||""}</span></div>`).join("");return`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FixitLab Certificate - ${a.username}</title>
<style>
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
  body { margin:0; padding:40px; background:#0f172a; font-family:'Segoe UI',system-ui,sans-serif; color:#e2e8f0; }
  .cert { max-width:800px; margin:0 auto; border:3px solid #06b6d4; border-radius:16px; padding:48px; background:linear-gradient(135deg,#0f172a,#1e293b); position:relative; overflow:hidden; }
  .cert::before { content:''; position:absolute; top:-40px; right:-40px; width:200px; height:200px; background:radial-gradient(circle,rgba(6,182,212,0.1),transparent); border-radius:50%; }
  .logo { text-align:center; margin-bottom:24px; }
  .logo span { display:inline-block; width:48px; height:48px; line-height:48px; text-align:center; background:linear-gradient(135deg,#06b6d4,#4338ca); border-radius:12px; font-size:24px; font-weight:bold; color:white; }
  h1 { text-align:center; font-size:28px; color:#06b6d4; margin:0 0 8px; }
  h2 { text-align:center; font-size:16px; color:#94a3b8; font-weight:normal; margin:0 0 32px; }
  .user { text-align:center; font-size:32px; font-weight:bold; color:white; margin:24px 0; }
  .stats { display:flex; justify-content:center; gap:32px; margin:24px 0; }
  .stat { text-align:center; }
  .stat-val { font-size:28px; font-weight:bold; color:#06b6d4; }
  .stat-label { font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:1px; }
  .achievements { text-align:center; margin:24px 0; }
  .achievements h3 { color:#f59e0b; margin-bottom:12px; }
  .footer { text-align:center; margin-top:32px; font-size:11px; color:#475569; border-top:1px solid #334155; padding-top:16px; }
</style>
</head>
<body>
<div class="cert">
  <div class="logo"><span>F</span></div>
  <h1>FixitLab Certificate of Achievement</h1>
  <h2>This certifies that</h2>
  <div class="user">${a.username}</div>
  <div class="stats">
    <div class="stat"><div class="stat-val">${a.total_scenarios_completed}</div><div class="stat-label">Scenarios Completed</div></div>
    <div class="stat"><div class="stat-val">${a.total_score}</div><div class="stat-label">Total Score</div></div>
    <div class="stat"><div class="stat-val">${a.total_achievements}</div><div class="stat-label">Achievements Earned</div></div>
  </div>
  <div class="achievements">
    <h3>Achievements</h3>
    ${i||'<p style="color:#64748b;">No achievements yet</p>'}
  </div>
  <div class="footer">
    Certificate ID: ${a.certificate_id}<br>
    Generated on ${new Date(a.generated_at).toLocaleDateString("en-US",{year:"numeric",month:"long",day:"numeric"})}<br>
    FixitLab — Real-world Linux & DevOps Troubleshooting Platform
  </div>
</div>
</body>
</html>`}export{U as default};
