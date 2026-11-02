import { auth } from "@clerk/nextjs/server";
import { AppSidebar } from "@/components/app-sidebar";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  await auth.protect();

  return (
    <div className="flex min-h-screen bg-zinc-50 text-zinc-950">
      <AppSidebar />
      <main className="min-w-0 flex-1 p-6 md:p-10">{children}</main>
    </div>
  );
}
