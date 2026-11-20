import React from 'react';

const paths = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  estimate: 'M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M8 7h8 M8 12h2m4 0h2m-8 5h2m4 0h2',
  folder: 'M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  settings: 'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-4 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0m4-4a4 4 0 0 1 0 8',
  sheet: 'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8m-8 4h8m-4-4v7',
  building: 'M3 21h18M5 21V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v16M13 10a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v11M8 7h2M8 11h2M8 15h2M16 12h2M16 16h2',
  menu: 'M4 6h16M4 12h16M4 18h16',
  logout: 'M11 4H5v16h6m3-12 4 4-4 4m-5-4h11',
  download: 'M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4',
  plus: 'M12 5v14M5 12h14',
  pin: 'M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
  refresh: 'M20 6v5h-5M4 18v-5h5M5 9a7.5 7.5 0 0 1 12.5-3L20 11M4 13l2.5 5A7.5 7.5 0 0 0 19 15',
  check: 'm5 12 4 4L19 6',
  left: 'm15 6-6 6 6 6',
  right: 'm9 6 6 6-6 6',
  eye: 'M2 12s4-6 10-6 10 6 10 6-4 6-10 6-10-6-10-6z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
  eyeOff: 'm3 3 18 18M10.6 6.1 12 6c6 0 10 6 10 6a15 15 0 0 1-3 3.2M6.5 7.8A17 17 0 0 0 2 12s4 6 10 6c1.4 0 2.7-.3 3.9-.8',
  calendar: 'M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z M7 3v4m10-4v4M3 10h18m-13 5h2m4 0h2',
  mail: 'M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z M3 7l9 7 9-7',
  close: 'm6 6 12 12M18 6 6 18',
};
const routeIcons = {'/dashboard':'dashboard','/admin':'dashboard','/projects':'folder','/new-estimate':'estimate','/admin/users':'users','/admin/source':'sheet','/admin/rates':'estimate'};
export default function Icon({ name, route, size = 19 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name || routeIcons[route] || 'settings']} /></svg>;
}
