import type { ReactNode } from 'react';

interface PageShellProps {
  children: ReactNode;
  className?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  eyebrow?: string;
}

export function PageShell({ children, className = '' }: PageShellProps) {
  return (
    <div data-testid="page-shell" className={`page-shell ${className}`.trim()}>
      {children}
    </div>
  );
}

export function PageHeader({ title, description, icon, eyebrow }: PageHeaderProps) {
  return (
    <header className="page-header">
      {eyebrow && <span className="page-header-eyebrow">{eyebrow}</span>}
      <div className="page-header-title">
        {icon && <span className="page-header-icon">{icon}</span>}
        <h1>{title}</h1>
      </div>
      {description && <p>{description}</p>}
    </header>
  );
}
