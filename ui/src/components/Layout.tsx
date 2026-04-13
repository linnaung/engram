import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { LogoIcon } from './Logo'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/chat', label: 'Chat' },
  { to: '/graph', label: 'Graph' },
  { to: '/ontology', label: 'Ontology' },
  { to: '/memories', label: 'Memories' },
]

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-stone-50">
      <nav className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-screen-2xl mx-auto px-6">
          <div className="flex items-center justify-between h-14">
            <NavLink to="/" className="flex items-center gap-2.5">
              <LogoIcon size={28} />
              <span className="text-sm font-semibold text-black tracking-tight">Engram</span>
            </NavLink>
            <div className="flex gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `px-3.5 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-black text-white'
                        : 'text-neutral-500 hover:text-black hover:bg-neutral-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-screen-2xl mx-auto">
        {children}
      </main>
    </div>
  )
}
