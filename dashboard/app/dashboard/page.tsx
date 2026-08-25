import LicitacionesTable from "@/components/licitaciones-table";

export const dynamic = "force-dynamic";

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <LicitacionesTable />
    </main>
  );
}
