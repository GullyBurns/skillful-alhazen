import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Domain Modeling | Skillful-Alhazen',
  description: 'Design process tracking for Alhazen knowledge domain skills',
};

export default function DomainModelingLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
