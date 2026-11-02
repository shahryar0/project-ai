"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { OrganizationSwitcher, UserButton } from "@clerk/nextjs";

const sections = [
  { label: "WORKSPACE", links: [
    { label: "Overview", href: "/overview" },
    { label: "Connectors", href: "/connectors" },
    { label: "AI Employees", href: "/employees" },
    { label: "Agent Swarms", href: "/swarms" },
    { label: "Tasks & Workflows", href: "/tasks" },
    { label: "Approvals", href: "/approvals" },
  ] },
  { label: "INSIGHTS", links: [
    { label: "Activity Monitor", href: "/activity" },
    { label: "Execution History", href: "/history" },
    { label: "Usage & Analytics", href: "/analytics" },
  ] },
  { label: "PREFERENCES", links: [{ label: "Settings", href: "/settings" }] },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex min-h-screen w-64 shrink-0 flex-col border-r border-zinc-200 bg-white px-4 py-5">
      <Link href="/overview" className="mb-6 px-2 text-lg font-semibold tracking-tight text-zinc-950">
        Cognitive
      </Link>
      <div className="mb-6">
        <OrganizationSwitcher
          afterCreateOrganizationUrl="/overview"
          afterSelectOrganizationUrl="/overview"
          appearance={{ elements: { rootBox: "w-full", organizationSwitcherTrigger: "w-full justify-between" } }}
        />
      </div>
      <nav aria-label="Main navigation" className="flex-1 space-y-6">
        {sections.map((section) => (
          <section key={section.label}>
            <h2 className="mb-2 px-2 text-xs font-medium tracking-wide text-zinc-500">{section.label}</h2>
            <ul className="space-y-1">
              {section.links.map((link) => {
                const active = pathname === link.href;
                return (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      aria-current={active ? "page" : undefined}
                      className={`block rounded-md px-2 py-2 text-sm ${active ? "bg-zinc-100 font-medium text-zinc-950" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950"}`}
                    >
                      {link.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </nav>
      <div className="mt-6 flex items-center gap-3 border-t border-zinc-200 px-2 pt-4">
        <UserButton />
        <span className="text-sm text-zinc-600">Account</span>
      </div>
    </aside>
  );
}
