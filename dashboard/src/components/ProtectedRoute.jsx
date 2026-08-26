import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProtectedRoute({ children }) {
  const { session, loading, supabaseConfigured } = useAuth();
  const location = useLocation();

  if (!supabaseConfigured) {
    return children;
  }

  if (loading) {
    return (
      <div className="auth-loading">
        <p>Loading session…</p>
      </div>
    );
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
