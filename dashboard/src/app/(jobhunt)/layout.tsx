import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Job Hunt Dashboard | Skillful-Alhazen",
  description: "Track job applications, analyze skill gaps, and manage your learning plan",
};

export default function JobhuntLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <>{children}</>;
}
