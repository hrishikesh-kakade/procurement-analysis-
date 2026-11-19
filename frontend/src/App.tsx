import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ANALYTICS, useAuth } from "./auth";
import Layout from "./Layout";
import Analytics from "./pages/Analytics";
import Assistant from "./pages/Assistant";
import Dashboard from "./pages/Dashboard";
import Knowledge from "./pages/Knowledge";
import Login from "./pages/Login";
import PurchaseOrders from "./pages/PurchaseOrders";
import Requisitions from "./pages/Requisitions";
import Rfqs from "./pages/Rfqs";
import Suppliers from "./pages/Suppliers";
import Users from "./pages/Users";
import { Spinner } from "./ui";

function Protected({ roles, children }: { roles?: any[]; children: ReactNode }) {
  const { user, loading, can } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !can(...roles)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="suppliers" element={<Suppliers />} />
        <Route path="requisitions" element={<Requisitions />} />
        <Route path="purchase-orders" element={<PurchaseOrders />} />
        <Route path="rfqs" element={<Rfqs />} />
        <Route path="analytics" element={<Protected roles={ANALYTICS}><Analytics /></Protected>} />
        <Route path="assistant" element={<Protected roles={ANALYTICS}><Assistant /></Protected>} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="users" element={<Protected roles={["admin"]}><Users /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
