// Small History API router for this application's fixed, flat page routes.
import { Children, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
const RouterContext = createContext(null);
const currentLocation = () => ({ pathname: window.location.pathname, search: window.location.search, hash: window.location.hash, state: window.history.state });
export function BrowserRouter({ children }) {
  const [location, setLocation] = useState(currentLocation);
  useEffect(() => {
    const changed = () => setLocation(currentLocation());
    window.addEventListener('popstate', changed);
    window.addEventListener('buildsmart-navigation', changed);
    return () => { window.removeEventListener('popstate', changed); window.removeEventListener('buildsmart-navigation', changed); };
  }, []);
  const navigate = useCallback((to, options = {}) => {
    if (typeof to === 'number') { window.history.go(to); return; }
    const url = new URL(to, window.location.href);
    if (url.origin !== window.location.origin) throw new Error('Only local page navigation is supported');
    window.history[options.replace ? 'replaceState' : 'pushState'](options.state || null, '', url.pathname + url.search + url.hash);
    setLocation(currentLocation());
    window.scrollTo(0, 0);
  }, []);
  const value = useMemo(() => ({ location, navigate }), [location, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}
export function useNavigate() { return useContext(RouterContext).navigate; }
export function useLocation() { return useContext(RouterContext).location; }
export function Route() { return null; }
export function Routes({ children }) {
  const { pathname } = useLocation();
  const routes = Children.toArray(children);
  const match = routes.find(r => r.props.path === pathname) || routes.find(r => r.props.path === '*');
  return match?.props.element || null;
}
export function Navigate({ to, replace = false }) {
  const navigate = useNavigate();
  useEffect(() => { navigate(to, { replace }); }, [navigate, to, replace]);
  return null;
}
