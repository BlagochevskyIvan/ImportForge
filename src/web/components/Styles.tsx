// Plain CSS in a Server Component, without a styling runtime.
export default function Styles() {
  return <style>{`
    :root { color-scheme:light; --ink:#172b28; --muted:#586b65; --green:#21584b; --paper:#f6f7f2; --line:#dce3db; --accent:#d7e8b7; }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; background:var(--paper); color:var(--ink); font-family:Arial,Helvetica,sans-serif; line-height:1.6; }
    a { color:var(--green); text-underline-offset:4px; }
    button,input { font:inherit; }
    :focus-visible { outline:3px solid #739b38; outline-offset:4px; }
    button { cursor:pointer; }
    button:disabled { cursor:wait; opacity:.6; }
    h1,h2,h3,p { margin-top:0; }
    h1,h2,h3 { line-height:1.15; letter-spacing:-.035em; }
    h1 { font-size:clamp(2.4rem,5vw,4.7rem); font-weight:600; }
    h2 { font-size:clamp(1.6rem,3vw,2.4rem); font-weight:600; }
    h3 { font-size:1.2rem; }
    .container { width:min(1120px,calc(100% - 48px)); margin:auto; }
    .skip { position:absolute; top:-100px; left:20px; z-index:10; padding:10px; background:white; }
    .skip:focus { top:10px; }
    .header { min-height:88px; display:flex; align-items:center; justify-content:space-between; gap:20px; border-bottom:1px solid var(--line); }
    .brand { display:inline-flex; align-items:center; gap:10px; color:var(--ink); text-decoration:none; font-size:1.25rem; font-weight:700; letter-spacing:-.04em; }
    .brand-icon { display:grid; place-items:center; width:34px; height:34px; border-radius:9px; background:var(--green); color:var(--accent); font-size:20px; }
    .nav,.actions { display:flex; align-items:center; flex-wrap:wrap; gap:12px; }
    .nav a { font-size:.9rem; text-decoration:none; }
    .button { display:inline-flex; justify-content:center; align-items:center; min-height:46px; padding:10px 22px; gap:8px; border:1px solid var(--green); border-radius:7px; background:var(--green); color:white; font-weight:600; text-decoration:none; line-height:1.4; }
    .button:hover { background:#163f35; }
    .button.secondary { background:transparent; color:var(--green); border-color:var(--line); }
    .button.secondary:hover { background:#e9eee3; }
    .button.small { min-height:40px; padding:8px 16px; font-size:.9rem; }
    .hero { display:grid; grid-template-columns:1.15fr 1fr; gap:70px; align-items:center; padding:90px 0 80px; }
    .eyebrow { display:flex; gap:8px; align-items:center; font-size:.74rem; font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:var(--green); margin-bottom:24px; }
    .dot { width:7px; height:7px; background:#729d3b; border-radius:50%; }
    .lead { font-size:1.1rem; color:var(--muted); max-width:48ch; }
    .hero .actions { margin-top:32px; }
    .small-text { font-size:.85rem; color:var(--muted); }
    .hero-note { margin-top:20px; }
    .flow { background:#e9eee2; border:1px solid #d5dfce; border-radius:14px; padding:30px; }
    .flow-top { display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #ced9c7; padding-bottom:18px; margin-bottom:25px; font-size:.8rem; }
    .flow-file { background:white; border:1px solid var(--line); border-radius:8px; padding:20px; display:flex; align-items:center; gap:16px; }
    .file-icon { color:var(--green); font-family:monospace; font-weight:bold; font-size:1.2rem; }
    .flow-arrow { color:#719467; text-align:center; padding:8px; }
    .flow-result { border-left:3px solid #6f963e; background:#f7faef; padding:18px; border-radius:4px; }
    .flow-result p,.flow-file p { margin:0; }
    .muted { color:var(--muted); }
    .features { display:grid; grid-template-columns:repeat(3,1fr); gap:30px; padding:35px 0 60px; border-top:1px solid var(--line); }
    .feature-number { color:#668452; font-size:.8rem; display:block; margin-bottom:18px; }
    .features p { color:var(--muted); font-size:.93rem; }
    .footer { border-top:1px solid var(--line); padding:24px 0; color:var(--muted); font-size:.8rem; display:flex; justify-content:space-between; gap:20px; }
    .auth-layout { min-height:calc(100vh - 180px); display:grid; grid-template-columns:1fr 1fr; gap:80px; align-items:center; padding:60px 0; }
    .auth-aside h1 { font-size:clamp(2.5rem,4vw,3.7rem); max-width:10ch; }
    .auth-aside .lead { max-width:34ch; }
    .auth-aside .aside-note { margin-top:40px; border-left:2px solid #a4b88d; padding-left:20px; max-width:37ch; color:var(--muted); }
    .card { border:1px solid var(--line); border-radius:12px; background:white; padding:32px; }
    .card h2 { font-size:1.65rem; margin-bottom:10px; }
    .form { display:grid; gap:18px; }
    .field { display:grid; gap:6px; font-size:.9rem; font-weight:600; }
    input { border:1px solid #c7d1c6; border-radius:6px; padding:11px 12px; background:white; width:100%; min-width:0; color:var(--ink); }
    input:hover { border-color:#8fa48c; }
    input:disabled { background:#f4f5f1; }
    .hint { color:var(--muted); font-size:.78rem; font-weight:400; }
    .form-footer { margin:24px 0 0; text-align:center; font-size:.88rem; color:var(--muted); }
    .notice { border-radius:6px; padding:12px 15px; margin:0 0 20px; font-size:.9rem; overflow-wrap:anywhere; }
    .notice.error { color:#8b302d; background:#fdf0ec; border:1px solid #f1d2c8; }
    .notice.success { color:#285b32; background:#eff7e6; border:1px solid #d1e3bc; }
    .session { padding:60px 0; max-width:600px; }
    .dashboard { padding:45px 0 70px; }
    .dashboard-title { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:35px; }
    .dashboard h1 { font-size:clamp(2rem,4vw,3rem); margin-bottom:12px; overflow-wrap:anywhere; }
    .dashboard-title p { margin-bottom:0; }
    .section-head { display:flex; justify-content:space-between; gap:16px; align-items:center; margin-bottom:22px; }
    .section-head h2 { font-size:1.5rem; margin:0; }
    .supplier-form { margin-bottom:28px; max-width:640px; }
    .empty { padding:60px 20px; border:1px dashed #bfceba; border-radius:10px; text-align:center; }
    .empty p { margin-bottom:0; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:8px; background:white; }
    table { width:100%; border-collapse:collapse; text-align:left; font-size:.93rem; }
    th { background:#edf1e7; font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
    td,th { padding:17px 20px; border-bottom:1px solid var(--line); }
    tr:last-child td { border-bottom:0; }
    td { overflow-wrap:anywhere; max-width:320px; }
    .badge { display:inline-block; font-size:.75rem; border-radius:20px; padding:3px 10px; background:#edf4e4; color:#426b35; white-space:nowrap; }
    .badge.inactive { background:#f2f0e9; color:#716b51; }
    .pagination { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:20px; font-size:.85rem; }
    @media(max-width:760px) {
      .container { width:calc(100% - 32px); }
      .header { min-height:76px; gap:12px; flex-wrap:wrap; padding:16px 0; }
      .nav { gap:12px; }
      .nav .button { padding:8px 12px; }
      .hero { grid-template-columns:1fr; gap:40px; padding:50px 0; }
      .flow { padding:24px; }
      .features { grid-template-columns:1fr; gap:10px; padding-bottom:30px; }
      .feature-number { margin-bottom:8px; }
      .auth-layout { grid-template-columns:1fr; gap:25px; padding:36px 0; }
      .auth-aside h1 { max-width:none; font-size:2.4rem; }
      .auth-aside .aside-note { display:none; }
      .card { padding:24px; }
      .dashboard-title { align-items:flex-start; flex-direction:column; }
      .section-head { align-items:flex-start; flex-wrap:wrap; }
      .footer { flex-direction:column; gap:4px; }
      td,th { padding:13px; }
      table { min-width:560px; }
    }
    @media(prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
  `}</style>;
}
