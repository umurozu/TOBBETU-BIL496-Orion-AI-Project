import { Layout } from './components/layout/Layout';
import { AuthView } from './views/auth/AuthView';
import { useAuthStore } from './store/authStore';
import { CookieBanner } from './components/common/CookieBanner';

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return (
    <div className="h-screen w-full bg-slate-50 flex flex-col overflow-hidden font-sans text-slate-900">
      {isAuthenticated ? <Layout /> : <AuthView />}
      <CookieBanner />
    </div>
  );
}

export default App;
