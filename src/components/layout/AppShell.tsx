import type { PropsWithChildren } from 'react'

const AppShell = ({ children }: PropsWithChildren) => {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      {children}
    </div>
  )
}

export default AppShell
