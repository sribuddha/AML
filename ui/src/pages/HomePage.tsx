import { Link } from "react-router-dom"
import PageShell from "../components/PageShell"

const CARDS = [
  { to: "/compliance", emoji: "🛡️", title: "Compliance", desc: "Review suspicious activity reports and take action" },
  { to: "/operations", emoji: "⚙️", title: "Operations", desc: "Upload transaction files and manage upload history" },
  { to: "/operations/rules", emoji: "📋", title: "Rules", desc: "Manage AML detection rules" },
  { to: "/customers", emoji: "👥", title: "Customers", desc: "Search and view customer profiles" },
  { to: "/transactions", emoji: "💳", title: "Transactions", desc: "Browse and search transaction records" },
]

export default function HomePage() {
  return (
    <PageShell title="AML Monitor" description="Anti-Money Laundering Transaction Monitoring System">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {CARDS.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="block bg-white border border-slate-200 rounded-lg p-5 hover:border-blue-300 hover:shadow-md transition-all group"
          >
            <div className="text-2xl mb-3">{card.emoji}</div>
            <h3 className="text-base font-semibold text-slate-800 group-hover:text-blue-600 transition-colors">
              {card.title}
            </h3>
            <p className="text-sm text-slate-500 mt-1">{card.desc}</p>
          </Link>
        ))}
      </div>
    </PageShell>
  )
}
