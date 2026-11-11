import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { RequireAdmin, RequireAuth } from "./context/AuthContext";
import { Dashboard } from "./pages/Dashboard";
import { CreateTourCode } from "./pages/CreateTourCode";
import { TourPackages } from "./pages/TourPackages";
import { Pilgrims } from "./pages/Pilgrims";
import { Settings } from "./pages/Settings";
import { Users } from "./pages/Users";
import { Login } from "./pages/Login";
import { AcceptInvite } from "./pages/AcceptInvite";

export const router = createBrowserRouter([
  { path: "/login", Component: Login },
  { path: "/invite/:token", Component: AcceptInvite },
  {
    Component: RequireAuth,
    children: [
      {
        path: "/",
        Component: Layout,
        children: [
          { index: true, Component: Dashboard },
          { path: "create", Component: CreateTourCode },
          { path: "packages", Component: TourPackages },
          { path: "pilgrims", Component: Pilgrims },
          { path: "settings", Component: Settings },
          { Component: RequireAdmin, children: [{ path: "users", Component: Users }] },
        ],
      },
    ],
  },
]);
