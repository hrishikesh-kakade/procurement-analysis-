import { NavLink, Outlet } from "react-router-dom";
import { ANALYTICS, useAuth } from "./auth";
import { label } from "./format";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦", end: true },
  { to: "/suppliers", label: "Suppliers", icon: "⌂" },
  { to: "/requisitions", label: "Requisitions", icon: "✎" },
  { to: "/purchase-orders", label: "Purchase Orders", icon: "▤" },
  { to: "/rfqs", label: "RFQs", icon: "⇄" },
  { to: "/analytics", label: "Analytics", icon: "◔", roles: ANALYTICS },
  { to: "/assistant", label: "AI Assistant", icon: "✦", roles: ANALYTICS },
  { to: "/knowledge", label: "Knowledge Base", icon: "❏" },
  { to: "/users", label: "Users", icon: "☺", roles: ["admin"] },
];

export default function Layout() {
  const { user, logout, can } = useAuth();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">P</span>
          <div>
            <strong>Procurement</strong>
            <small>Intelligence Platform</small>
          </div>
        </div>
        <nav>
          {NAV.filter((item) => !item.roles || can(...(item.roles as any))).map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "nav active" : "nav")}>
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="user-box">
          <div className="avatar">{user?.full_name?.[0]?.toUpperCase()}</div>
          <div className="user-meta">
            <strong>{user?.full_name}</strong>
            <small>{label(user?.role)}</small>
          </div>
          <button className="icon-btn light" onClick={logout} title="Sign out" aria-label="Sign out">⏻</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
