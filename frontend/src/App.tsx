import { useAuth } from "./auth/AuthContext";
import { DevLoginPage } from "./pages/DevLoginPage";
import { HomePage } from "./pages/HomePage";

export function App() {
  const { currentUser, loading } = useAuth();

  if (loading) return null;
  return currentUser ? <HomePage /> : <DevLoginPage />;
}
