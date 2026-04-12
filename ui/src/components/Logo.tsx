export function LogoIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="8" fill="#6366f1"/>
      <circle cx="16" cy="8" r="2.5" fill="#c7d2fe" opacity="0.9"/>
      <circle cx="8" cy="16" r="2" fill="#a5b4fc" opacity="0.8"/>
      <circle cx="24" cy="16" r="2" fill="#a5b4fc" opacity="0.8"/>
      <circle cx="10" cy="24" r="2.5" fill="#e0e7ff" opacity="0.7"/>
      <circle cx="22" cy="24" r="2.5" fill="#e0e7ff" opacity="0.7"/>
      <circle cx="16" cy="20" r="3" fill="white" opacity="0.95"/>
      <line x1="16" y1="8" x2="8" y2="16" stroke="#c7d2fe" strokeWidth="1.2" opacity="0.6"/>
      <line x1="16" y1="8" x2="24" y2="16" stroke="#c7d2fe" strokeWidth="1.2" opacity="0.6"/>
      <line x1="8" y1="16" x2="16" y2="20" stroke="#a5b4fc" strokeWidth="1.2" opacity="0.5"/>
      <line x1="24" y1="16" x2="16" y2="20" stroke="#a5b4fc" strokeWidth="1.2" opacity="0.5"/>
      <line x1="16" y1="20" x2="10" y2="24" stroke="#e0e7ff" strokeWidth="1" opacity="0.4"/>
      <line x1="16" y1="20" x2="22" y2="24" stroke="#e0e7ff" strokeWidth="1" opacity="0.4"/>
      <line x1="8" y1="16" x2="10" y2="24" stroke="#e0e7ff" strokeWidth="1" opacity="0.3"/>
      <line x1="24" y1="16" x2="22" y2="24" stroke="#e0e7ff" strokeWidth="1" opacity="0.3"/>
    </svg>
  )
}

export function LogoFull({ size = 48 }: { size?: number }) {
  const textSize = size * 0.35
  return (
    <div className="flex items-center gap-2">
      <LogoIcon size={size} />
      <span style={{ fontSize: textSize }} className="font-bold text-zinc-900 tracking-tight">
        Engram
      </span>
    </div>
  )
}
