import { Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div>
      <div className="flex justify-between items-center p-4 border-b">
        <h1 className="text-xl font-bold">Financial Agent</h1>
        <span>Financial Analysis</span>
      </div>
      <Outlet />
    </div>
  )
}