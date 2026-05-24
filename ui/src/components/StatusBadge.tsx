const statusColors: Record<string, string> = {
  clean: "bg-green-100 text-green-700",
  complete: "bg-green-100 text-green-700",
  confirmed: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  processing: "bg-yellow-100 text-yellow-700",
  pending_review: "bg-yellow-100 text-yellow-700",
  pending_human: "bg-yellow-100 text-yellow-700",
  uploaded: "bg-yellow-100 text-yellow-700",
  flagged: "bg-red-100 text-red-700",
  failed: "bg-red-100 text-red-700",
  escalated: "bg-red-100 text-red-700",
  dismissed: "bg-slate-100 text-slate-600",
  inactive: "bg-slate-100 text-slate-600",
};

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colors = statusColors[status] || "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
