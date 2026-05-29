import { BrowserRouter, Routes, Route } from "react-router-dom"
import ErrorBoundary from "./components/ErrorBoundary"
import Layout from "./components/Layout"
import HomePage from "./pages/HomePage"
import TransactionsPage from "./pages/TransactionsPage"
import CustomersPage from "./pages/CustomersPage"
import CustomerDetailPage from "./pages/CustomerDetailPage"
import CompliancePage from "./pages/CompliancePage"
import OperationsPage from "./pages/OperationsPage"
import RulesPage from "./pages/RulesPage"
import TestPage from "./pages/TestPage"
import NotFoundPage from "./pages/NotFoundPage"

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:customerId" element={<CustomerDetailPage />} />
            <Route path="/compliance" element={<CompliancePage />} />
            <Route path="/operations" element={<OperationsPage />} />
            <Route path="/operations/rules" element={<RulesPage />} />
            <Route path="/test" element={<TestPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
