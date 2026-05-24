import { Link } from "react-router-dom";

const cards = [
  {
    to: "/compliance",
    icon: "\u{1F6E1}\uFE0F",
    title: "Compliance",
    description: "Review suspicious activity reports and resolve flagged transactions",
  },
  {
    to: "/operations",
    icon: "\uD83D\uDCE4",
    title: "Operations",
    description: "Upload and manage transaction data files",
  },
  {
    to: "/operations/rules",
    icon: "\u2699\uFE0F",
    title: "Rules",
    description: "Configure detection rules that drive the AML engine",
  },
  {
    to: "/customers",
    icon: "\uD83D\uDC65",
    title: "Customers",
    description: "Browse customer profiles, account history, and activity",
  },
  {
    to: "/transactions",
    icon: "\uD83D\uDCCB",
    title: "Transactions",
    description: "View and search all processed transaction records",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">Dashboard</h2>
        <p className="text-sm text-slate-500 mt-0.5">Select a module to get started</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="block bg-white border border-slate-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-sm transition-all group"
          >
            <div className="flex items-start gap-4">
              <span className="text-2xl">{card.icon}</span>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-slate-800 group-hover:text-blue-600 transition-colors">
                  {card.title}
                </h3>
                <p className="text-sm text-slate-500 mt-1 leading-relaxed">
                  {card.description}
                </p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
