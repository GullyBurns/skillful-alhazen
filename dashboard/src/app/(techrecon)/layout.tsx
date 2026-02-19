import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TechRecon Dashboard | Skillful-Alhazen",
  description: "Browse and visualize technology reconnaissance knowledge graphs",
};

export default function TechreconLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <>{children}</>;
}
