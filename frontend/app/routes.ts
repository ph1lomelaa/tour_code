import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { CreateTourCode } from "./pages/CreateTourCode";
import { TourPackages } from "./pages/TourPackages";
import { Pilgrims } from "./pages/Pilgrims";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: "create", Component: CreateTourCode },
      { path: "packages", Component: TourPackages },
      { path: "pilgrims", Component: Pilgrims },
    ],
  },
]);
