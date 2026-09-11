export default function TrustAgentLogo({ label = true }) {
  return <div className="brand" aria-label="TrustAgent home">
    <svg className="brand-mark" viewBox="0 0 40 40" role="img" aria-label="TrustAgent shield logo">
      <defs>
        <linearGradient id="trustagent-gradient" x1="6" y1="4" x2="34" y2="36" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7dd3fc" />
          <stop offset="1" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      <path d="M20 3.5 34 9v9.2c0 8.7-5.5 15.5-14 18.3C11.5 33.7 6 26.9 6 18.2V9l14-5.5Z" fill="url(#trustagent-gradient)" />
      <path d="m13.5 19.8 4.1 4.2 9-9.2" fill="none" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3.2" />
    </svg>
    {label && <span className="brand-name">TrustAgent</span>}
  </div>
}
