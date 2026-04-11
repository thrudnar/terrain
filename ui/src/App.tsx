import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { Dashboard } from "./views/Dashboard";
import { OpportunityList } from "./views/OpportunityList";
import { OpportunityDetail } from "./views/OpportunityDetail";
import { InterestingCompanies } from "./views/InterestingCompanies";
import { PromptComparison } from "./views/PromptComparison";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/opportunities" element={<OpportunityList />} />
            <Route path="/opportunities/:id" element={<OpportunityDetail />} />
            <Route path="/companies" element={<InterestingCompanies />} />
            <Route path="/compare" element={<PromptComparison />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
