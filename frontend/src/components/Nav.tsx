import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export function Nav() {
  const { user, clearAuth, isAdmin } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    clearAuth()
    navigate('/login')
  }

  return (
    <nav className="bg-indigo-900 text-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/contracts" className="font-semibold tracking-tight text-lg">
          YunoJuno
        </Link>
        <Link to="/contracts" className="text-indigo-200 hover:text-white text-sm">
          Contracts
        </Link>
        {isAdmin && (
          <>
            <Link to="/billing" className="text-indigo-200 hover:text-white text-sm">
              Billing
            </Link>
            <Link to="/developers" className="text-indigo-200 hover:text-white text-sm">
              Developers
            </Link>
          </>
        )}
      </div>
      <div className="flex items-center gap-4 text-sm">
        <span className="text-indigo-300">{user?.email}</span>
        <button
          onClick={handleLogout}
          className="text-indigo-200 hover:text-white underline"
        >
          Sign out
        </button>
      </div>
    </nav>
  )
}
