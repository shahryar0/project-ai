const sectionTitles: Record<string, string> = {
  overview: "Overview",
  connectors: "Connectors",
  employees: "AI Employees",
  swarms: "Agent Swarms",
  tasks: "Tasks & Workflows",
  approvals: "Approvals",
  activity: "Activity Monitor",
  history: "Execution History",
  analytics: "Usage & Analytics",
  settings: "Settings",
};

export default async function SectionPage({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  const title = sectionTitles[section];

  if (!title) {
    return (
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold">Page not found</h1>
        <p className="mt-2 text-sm text-zinc-600">That workspace page does not exist.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-sm text-zinc-600">
        The workspace shell is ready. This section will be connected to the backend in a later phase.
      </p>
    </div>
  );
}
