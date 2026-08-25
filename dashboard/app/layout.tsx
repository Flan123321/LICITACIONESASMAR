import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Licitaciones | Dashboard",
  description:
    "Dashboard de licitaciones filtradas del Mercado Público de Chile",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-slate-100 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
