import React, { useState } from 'react';
import {
  ArrowDown, ArrowRight, BarChart3, BatteryCharging, Building2, Check, CircleHelp,
  FileCheck2, Gauge, Menu, Network, ShieldCheck, Sun, Thermometer,
  X,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import '../public-site.css';

const links = [
  ['Product', '/product'], ['Solutions', '/solutions'], ['How it works', '/how-it-works'],
  ['Commercial plans', '/commercial-plans'], ['Responsible AI', '/responsible-ai'], ['Contact', '/contact'],
];

function Brand() {
  return <a href="#/" className="public-brand" aria-label="CampusGrid home"><span className="public-brand-mark"><BatteryCharging size={21} /></span><span>CampusGrid<span className="public-brand-ai"> AI</span></span></a>;
}

function PublicHeader() {
  const [open, setOpen] = useState(false);
  const { status, homePath } = useAuth();
  return <header className="public-header"><div className="public-header-inner">
    <Brand />
    <nav className={`public-nav ${open ? 'is-open' : ''}`} aria-label="Main navigation">
      {links.map(([label, path]) => <a key={path} href={`#${path}`} onClick={() => setOpen(false)}>{label}</a>)}
    </nav>
    <div className="public-header-actions">
      <a className="public-login" href={`#${status === 'signed_in' ? homePath : '/login'}`}>{status === 'signed_in' ? 'Open EMS' : 'Login'}</a>
      <a className="public-button public-button-small" href="#/contact">Request a pilot <ArrowRight size={15} /></a>
    </div>
    <button className="public-mobile-toggle" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
  </div></header>;
}

function SectionEyebrow({ children }) { return <p className="public-eyebrow"><span />{children}</p>; }

function SectionHeading({ eyebrow, title, children, centered = false }) {
  return <div className={`public-section-heading ${centered ? 'is-centered' : ''}`}>
    {eyebrow && <SectionEyebrow>{eyebrow}</SectionEyebrow>}
    <h2>{title}</h2>{children && <p>{children}</p>}
  </div>;
}

function HeroFlow() {
  const steps = [
    { icon: BarChart3, title: 'Energy data', detail: 'Meter · tariff · assets' },
    { icon: Gauge, title: 'Forecast & optimize', detail: 'Models · constraints' },
    { icon: FileCheck2, title: 'Review recommendation', detail: 'Evidence · approval' },
  ];
  return <div className="hero-visual" aria-label="CampusGrid recommendation workflow">
    <div className="hero-visual-top"><span className="hero-live-dot" />DECISION SUPPORT WORKFLOW<span className="hero-visual-period">CAMPUS ENERGY</span></div>
    <div className="hero-flow">
      {steps.map(({ icon: Icon, title, detail }, i) => <React.Fragment key={title}>
        <div className={`hero-flow-step ${i === 2 ? 'hero-flow-human' : ''}`}><span className="hero-flow-icon"><Icon size={19} /></span><span><strong>{title}</strong><small>{detail}</small></span>{i === 2 && <span className="hero-approval"><Check size={13} /> HUMAN</span>}</div>
        {i < steps.length - 1 && <div className="hero-flow-connector"><span /><ArrowDown size={15} /></div>}
      </React.Fragment>)}
    </div>
    <div className="hero-visual-note"><ShieldCheck size={16} /><span>Recommendations for people to review. No automatic equipment control.</span></div>
    <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
  </div>;
}

function Hero() {
  const { status, homePath } = useAuth();
  return <section className="public-hero" id="top"><div className="public-container hero-layout">
    <div className="hero-copy"><SectionEyebrow>ENERGY MANAGEMENT FOR LARGE FACILITIES</SectionEyebrow>
      <h1>Make campus energy decisions <span>with greater clarity.</span></h1>
      <p className="hero-lede">CampusGrid helps university facility teams understand energy use, anticipate demand, and review explainable operating recommendations.</p>
      <p className="hero-role-note"><span className="role-dot" />Decision support for your team. People stay in control.</p>
      <div className="hero-actions"><a href="#/contact" className="public-button">Request a campus pilot <ArrowRight size={17} /></a><a href="#/product" className="public-button public-button-outline">Explore the product <ArrowDown size={16} /></a></div>
      <div className="hero-proof"><span><Check size={15} /> Human reviewed</span><span><Check size={15} /> Constraint aware</span><span><Check size={15} /> Designed for campuses</span></div>
      {status === 'signed_in' && <a className="hero-app-link" href={`#${homePath}`}>You’re signed in · Open the CampusGrid EMS <ArrowRight size={14} /></a>}
    </div>
    <HeroFlow />
  </div><div className="hero-bottom-rule"><span>MEASURE</span><i /><span>PREDICT</span><i /><span>OPTIMIZE</span><i /><span>EXPLAIN</span></div></section>;
}

function ProblemSection() {
  const items = [
    { icon: Building2, title: 'Many moving parts', text: 'Buildings, schedules, HVAC, solar and storage all shape a campus energy profile.' },
    { icon: BarChart3, title: 'Planning takes coordination', text: 'Teams need to consider demand, tariffs and operating constraints together.' },
    { icon: CircleHelp, title: 'Recommendations need context', text: 'A useful plan should show its assumptions and give people a clear way to review it.' },
  ];
  return <section className="public-section problem-section"><div className="public-container">
    <SectionHeading eyebrow="THE CHALLENGE" title="Campus energy is a coordination problem." centered>Facility teams make decisions across changing loads, tariffs and on-site resources. CampusGrid brings the planning context into one reviewable workflow.</SectionHeading>
    <div className="problem-grid">{items.map(({ icon: Icon, title, text }, i) => <article className="problem-card" key={title}><span className="problem-number">0{i + 1}</span><span className="public-icon"><Icon size={21} /></span><h3>{title}</h3><p>{text}</p></article>)}</div>
  </div></section>;
}

function ProductSection() {
  const items = [
    { icon: BarChart3, label: '01 / MEASURE', title: 'Understand the energy picture', text: 'Review consumption, tariff inputs and available campus energy data.' },
    { icon: Gauge, label: '02 / PREDICT', title: 'Anticipate demand', text: 'Forecast energy demand and solar output to inform planning.' },
    { icon: BatteryCharging, label: '03 / OPTIMIZE', title: 'Explore operating plans', text: 'Use mathematical optimization to evaluate dispatch recommendations against defined constraints.' },
    { icon: FileCheck2, label: '04 / EXPLAIN', title: 'Give decisions context', text: 'Present reasoning, supporting information and an approval path for facility teams.' },
  ];
  return <section className="public-section product-section" id="product"><div className="public-container">
    <SectionHeading eyebrow="THE CAMPUSGRID WORKFLOW" title="From energy data to a decision your team can review." centered>One connected workflow supports facility planning while keeping operational decisions with people.</SectionHeading>
    <div className="product-flow">{items.map(({ icon: Icon, label, title, text }, i) => <React.Fragment key={label}><article className="product-step"><span className="product-step-icon"><Icon size={22} /></span><span className="product-step-label">{label}</span><h3>{title}</h3><p>{text}</p></article>{i < items.length - 1 && <div className="product-step-arrow"><ArrowRight size={18} /></div>}</React.Fragment>)}</div>
    <div className="product-agent-note"><Network size={18} /><p><strong>Coordinated agent workflow</strong><span>Forecasting, digital-twin simulation, policy retrieval, and dispatch explanation contribute to the planning flow.</span></p><a href="#/how-it-works">How it works <ArrowRight size={15} /></a></div>
  </div></section>;
}

function AgentsSection() {
  const agents = [
    { n: '01', icon: BarChart3, title: 'Telemetry & forecasting', text: 'Estimates upcoming demand and solar generation from available inputs.' },
    { n: '02', icon: Thermometer, title: 'Digital twin', text: 'Simulates building thermal conditions to help review comfort constraints.' },
    { n: '03', icon: FileCheck2, title: 'Policy retrieval', text: 'Finds relevant tariff and policy material to support planning.' },
    { n: '04', icon: BatteryCharging, title: 'Dispatch & explanation', text: 'Optimizes a proposed schedule and presents its rationale for review.' },
  ];
  return <section className="public-section agents-section" id="how-it-works"><div className="public-container agents-layout">
    <div><SectionHeading eyebrow="HOW IT WORKS" title="Specialized components. A shared planning goal.">The existing CampusGrid workflow coordinates four agents in a defined sequence. The system uses their outputs to prepare recommendations for a facility team.</SectionHeading><a href="#/login" className="text-link">Sign in to explore the EMS <ArrowRight size={15} /></a></div>
    <div className="agent-list">{agents.map(({ n, icon: Icon, title, text }) => <article className="agent-row" key={n}><span className="agent-count">{n}</span><span className="agent-icon"><Icon size={19} /></span><div><h3>{title}</h3><p>{text}</p></div><span className="agent-connector" /></article>)}</div>
  </div></section>;
}

function ResponsibleSection() {
  const principles = [
    ['Human approval', 'Recommendations are presented for review; facility managers remain responsible for decisions.'],
    ['Operational constraints', 'Plans are evaluated against configured system limits and feasibility checks.'],
    ['Explainability & traceability', 'The product is designed to show supporting reasoning and retain decision records where enabled.'],
    ['Clear product boundaries', 'CampusGrid is decision support; it does not automatically operate physical equipment.'],
  ];
  return <section className="public-section responsible-section" id="responsible-ai"><div className="public-container responsible-layout">
    <div className="responsible-emblem"><span className="emblem-grid" /><ShieldCheck size={48} strokeWidth={1.35} /><span>HUMAN<br />IN CONTROL</span></div>
    <div><SectionHeading eyebrow="RESPONSIBLE DECISION SUPPORT" title="AI assistance. Human control.">Energy recommendations affect real operations. CampusGrid is designed to support people with reviewable recommendations, not make unsupervised equipment decisions.</SectionHeading>
      <div className="principle-grid">{principles.map(([title, text]) => <div className="principle" key={title}><span><Check size={14} /></span><p><strong>{title}</strong><small>{text}</small></p></div>)}</div>
    </div>
  </div></section>;
}

function SolutionsSection() {
  const initial = { icon: Building2, title: 'Universities & educational campuses', text: 'The initial market: multi-building campuses coordinating demand, comfort and on-site energy resources.', tag: 'INITIAL MARKET' };
  const future = [
    { icon: ShieldCheck, title: 'Hospitals', text: 'Potential future fit for complex facilities with critical loads.' },
    { icon: Sun, title: 'Hotels', text: 'Potential future fit for facilities with significant HVAC demand.' },
    { icon: Gauge, title: 'Industrial facilities', text: 'Potential future fit for sites focused on energy and demand planning.' },
  ];
  return <section className="public-section solutions-section" id="solutions"><div className="public-container">
    <SectionHeading eyebrow="WHO WE SERVE" title="Built around campus operations." centered>Start with the environment CampusGrid is designed for, then expand through customer discovery and validation.</SectionHeading>
    <article className="solution-primary"><span className="solution-icon"><Building2 size={25} /></span><div><span className="solution-tag">{initial.tag}</span><h3>{initial.title}</h3><p>{initial.text}</p></div><ArrowRight className="solution-arrow" size={20} /></article>
    <div className="future-heading"><span>FUTURE EXPANSION</span><i /> <small>Requires further validation and product adaptation</small></div>
    <div className="future-grid">{future.map(({ icon: Icon, title, text }) => <article className="future-card" key={title}><Icon size={19} /><h3>{title}</h3><p>{text}</p></article>)}</div>
  </div></section>;
}

function PlansSection() {
  const plans = [
    { id: '01', title: 'Energy assessment', price: 'LKR 150,000–300,000', cadence: 'one-time engagement', description: 'Understand the site and identify where a pilot can create measurable value.', includes: ['Bill and energy-data review', 'Tariff validation', 'Energy profile analysis', 'Opportunity identification', 'Pilot planning'] },
    { id: '02', title: 'Campus pilot', price: 'LKR 250,000–500,000', cadence: '8–12 weeks · one site', description: 'Evaluate CampusGrid with existing data and recommendations in shadow mode.', includes: ['Baseline establishment', 'Existing data integration', 'Forecasting & recommendations', 'Shadow-mode evaluation', 'Results report'] , featured: true },
    { id: '03', title: 'Campus SaaS', price: 'LKR 75,000–150,000', cadence: 'per month · proposed', description: 'Ongoing decision support for teams after a successful pilot and agreed scope.', includes: ['Energy dashboard', 'Forecasting & optimization', 'Recommendation audit trail', 'Reports & support', 'Performance reviews'] },
  ];
  return <section className="public-section plans-section" id="commercial-plans"><div className="public-container">
    <SectionHeading eyebrow="COMMERCIAL PLANS" title="Start with evidence. Grow with value." centered>Assessment → Pilot → Subscription. Scope and pricing should be confirmed with each customer.</SectionHeading>
    <div className="plans-grid">{plans.map((plan) => <article key={plan.id} className={`plan-card ${plan.featured ? 'plan-featured' : ''}`}>
      <div className="plan-card-top"><span>{plan.id} / ENGAGEMENT</span>{plan.featured && <span className="plan-recommended">START HERE</span>}</div><h3>{plan.title}</h3><p className="plan-description">{plan.description}</p>
      <p className="plan-price">{plan.price}</p><p className="plan-cadence">{plan.cadence}</p><div className="plan-divider" /><p className="plan-includes">INCLUDES</p><ul>{plan.includes.map((item) => <li key={item}><Check size={15} />{item}</li>)}</ul>
      <a className={plan.featured ? 'public-button' : 'public-button public-button-outline'} href="#/contact">Discuss this option <ArrowRight size={15} /></a>
    </article>)}</div>
    <p className="pricing-disclaimer"><ShieldCheck size={16} /> Illustrative pricing for pilot and commercialization discussions. Final scope and price depend on site requirements.</p>
    <article className="enterprise-card"><span className="enterprise-icon"><Building2 size={20} /></span><div><h3>Enterprise / Multi-site</h3><p>Multiple sites, custom integrations, advanced reporting and deployment configuration.</p></div><a href="#/contact" className="text-link">Talk to us <ArrowRight size={15} /></a><span className="enterprise-price">Custom pricing</span></article>
  </div></section>;
}

function AdoptionSection() {
  const steps = ['Energy assessment', 'Pilot deployment', 'Shadow-mode validation', 'Measured results', 'ROI review', 'Campus subscription', 'Multi-campus expansion'];
  return <section className="public-section adoption-section"><div className="public-container"><div className="adoption-header"><div><SectionHeading eyebrow="A LOW-RISK START" title="Prove the fit before you scale.">A clear adoption path helps campus teams evaluate value before committing to a wider rollout.</SectionHeading></div><a href="#/contact" className="public-button public-button-light">Plan a pilot <ArrowRight size={16} /></a></div>
    <div className="adoption-steps">{steps.map((step, i) => <div className="adoption-step" key={step}><span>{String(i + 1).padStart(2, '0')}</span><p>{step}</p>{i < steps.length - 1 && <ArrowRight size={15} />}</div>)}</div>
  </div></section>;
}

function RoiSection() {
  return <section className="public-section roi-section"><div className="public-container roi-layout">
    <div><SectionHeading eyebrow="MEASURED VALUE" title="Build the business case from your campus baseline.">A pilot compares an agreed baseline with observed results. Any financial estimate depends on the site and operating decisions.</SectionHeading><p className="roi-caveat"><ShieldCheck size={17} /> Illustrative scenario only. Actual results depend on tariff structure, energy profile, available assets, data quality, and operational decisions.</p></div>
    <div className="roi-panel"><div className="roi-panel-label">ILLUSTRATIVE CAMPUS SCENARIO <span>NOT A GUARANTEE</span></div><div className="roi-number-row"><p>Monthly energy bill</p><strong>LKR 6,000,000</strong></div><div className="roi-number-row"><p>Example measured improvement</p><strong>3–6%</strong></div><div className="roi-result"><span>Potential gross monthly impact</span><strong>LKR 180,000–360,000</strong></div><p className="roi-footnote">Pilot establishes the customer’s baseline and measures actual results before any ongoing commercial commitment.</p></div>
  </div></section>;
}

function PilotSection() {
  const steps = ['Customer data', 'CampusGrid analysis', 'Recommendations', 'Facility team review', 'Human decision', 'Operational action', 'Measured result'];
  return <section className="public-section pilot-section"><div className="public-container pilot-layout">
    <div><SectionHeading eyebrow="PILOT IN SHADOW MODE" title="Start with recommendations. Validate value before automation.">CampusGrid works alongside your facility team. The pilot can evaluate recommendations without connecting to equipment controls.</SectionHeading><a href="#/contact" className="text-link">Request a pilot <ArrowRight size={15} /></a></div>
    <div className="pilot-flow">{steps.map((step, i) => <React.Fragment key={step}><div className={`pilot-node ${i === 4 ? 'pilot-human' : ''}`}><span>{String(i + 1).padStart(2, '0')}</span>{step}{i === 4 && <ShieldCheck size={16} />}</div>{i < steps.length - 1 && <div className="pilot-line" />}</React.Fragment>)}</div>
  </div></section>;
}

function ContactSection() {
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  async function submit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const values = new FormData(form);
    setBusy(true);
    setSubmitted(false);
    setFeedback(null);
    const payload = {
      full_name: values.get('name'), organization: values.get('organization'),
      job_title: values.get('jobTitle') || null, email: values.get('email'), phone: values.get('phone') || null,
      building_count: values.get('buildings') || null, monthly_bill_range: values.get('bill') || null,
      has_solar: values.has('solar'), has_battery: values.has('battery'),
      metering_system: values.get('metering') || null, message: values.get('message') || null,
      website: values.get('website') || '',
    };
    try {
      await api.submitPilotInquiry(payload);
      setSubmitted(true);
      setFeedback({ type: 'success', text: 'Your inquiry was accepted by the configured email service. The CampusGrid team can follow up using the email address you provided.' });
      form.reset();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'We could not deliver your inquiry. Please try again later.' });
    } finally {
      setBusy(false);
    }
  }
  return <section className="public-section contact-section" id="contact"><div className="public-container contact-layout">
    <div className="contact-copy"><SectionHeading eyebrow="LET’S EXPLORE A PILOT" title="See how CampusGrid could fit your campus.">Share a little about your site. Your inquiry is sent to the CampusGrid contact mailbox through the configured backend email service.</SectionHeading>
      <div className="contact-assurances"><p><Check size={16} /> Start with existing energy data</p><p><Check size={16} /> Agree the baseline and pilot scope</p><p><Check size={16} /> Review recommendations with your team</p></div>
      <div className="contact-note"><ShieldCheck size={18} /><p><strong>Human-led evaluation</strong><span>CampusGrid provides decision support. Your facility team remains in control.</span></p></div>
    </div>
    <form className="pilot-form" onSubmit={submit} onChange={() => { if (submitted || feedback) { setSubmitted(false); setFeedback(null); } }}>
      <div className="form-heading"><span>01 / PILOT INQUIRY</span><h3>Tell us about your site</h3><p>Required fields are marked with <b>*</b>.</p></div>
      <div className="form-grid">
        <label className="pilot-honeypot" aria-hidden="true">Leave this field empty<input name="website" tabIndex={-1} autoComplete="off" /></label>
        <label>Full name *<input name="name" autoComplete="name" required maxLength={120} placeholder="Your name" /></label>
        <label>Organization *<input name="organization" required maxLength={160} placeholder="University or organization" /></label>
        <label>Job title<input name="jobTitle" maxLength={120} placeholder="e.g. Facilities Manager" /></label>
        <label>Work email *<input name="email" type="email" autoComplete="email" required maxLength={254} placeholder="name@organization.lk" /></label>
        <label>Phone<input name="phone" type="tel" autoComplete="tel" maxLength={30} placeholder="Optional" /></label>
        <label>Number of buildings<select name="buildings" defaultValue=""><option value="">Select a range</option><option>1–3</option><option>4–10</option><option>11–25</option><option>More than 25</option></select></label>
        <label>Approx. monthly energy bill<select name="bill" defaultValue=""><option value="">Select a range</option><option>Under LKR 1 million</option><option>LKR 1–5 million</option><option>LKR 5–10 million</option><option>Over LKR 10 million</option><option>Not sure</option></select></label>
        <label>Existing energy / metering system<input name="metering" maxLength={160} placeholder="Optional" /></label>
        <fieldset className="form-fieldset"><legend>On-site energy assets</legend><label className="form-check"><input name="solar" type="checkbox" /> Solar PV</label><label className="form-check"><input name="battery" type="checkbox" /> Battery storage</label></fieldset>
        <label className="form-message">Message<textarea name="message" rows="3" maxLength={1200} placeholder="What would you like to evaluate?" /></label>
      </div>
      <button className="public-button form-submit" type="submit" disabled={busy}>{busy ? 'Sending inquiry…' : 'Request a CampusGrid pilot'} {!busy && <ArrowRight size={16} />}</button>
      {feedback && <p role={feedback.type === 'error' ? 'alert' : 'status'} className={'form-status ' + (feedback.type === 'error' ? 'is-error' : 'is-success')}>{feedback.text}</p>}
      <p className="form-privacy">Your details are used to respond to this inquiry and are not stored in the CampusGrid database.</p>
    </form>
  </div></section>;
}

function Footer() {
  const { status, homePath } = useAuth();
  return <footer className="public-footer"><div className="public-container"><div className="footer-main"><div className="footer-brand-block"><Brand /><p>Energy management decision support<br />designed for large facilities.</p></div><div className="footer-links"><div><span>EXPLORE</span><a href="#/product">Product</a><a href="#/solutions">Solutions</a><a href="#/how-it-works">How it works</a></div><div><span>COMMERCIAL</span><a href="#/commercial-plans">Plans</a><a href="#/contact">Request a pilot</a><a href="#/responsible-ai">Responsible AI</a></div><div><span>ACCESS</span><a href={`#${status === 'signed_in' ? homePath : '/login'}`}>{status === 'signed_in' ? 'Open EMS' : 'Login'}</a><a href="#/contact">Contact</a></div></div></div><div className="footer-bottom"><span>© 2026 CampusGrid AI</span><span>Prototype product experience · Pricing and pilot details are proposed</span></div></div></footer>;
}

export default function PublicLandingPage({ route = '/' }) {
  return <div className="public-site"><a href="#public-main" className="sr-only-focusable public-skip-link">Skip to content</a><PublicHeader /><main id="public-main" tabIndex={-1}>
    {route === '/' && <Hero />}
    <ProblemSection />
    <ProductSection />
    <AgentsSection />
    <ResponsibleSection />
    <SolutionsSection />
    <PlansSection />
    <AdoptionSection />
    <RoiSection />
    <PilotSection />
    <ContactSection />
  </main><Footer /></div>;
}
