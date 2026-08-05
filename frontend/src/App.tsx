import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Home } from "./pages/Home";
import { MatchingPage } from "./pages/MatchingPage";
import { PlanManejoPage } from "./pages/PlanManejoPage";
import { SecopPage } from "./pages/SecopPage";

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/secop" element={<SecopPage />} />
        <Route path="/matching" element={<MatchingPage />} />
        <Route path="/plan" element={<PlanManejoPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
