import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface CollapsibleProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

export function Collapsible({ title, children, defaultOpen = false }: CollapsibleProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-app-border rounded-lg bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full p-3 text-xs font-medium text-app-text hover:bg-app-bg-tertiary/20 transition-colors"
      >
        {title}
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {isOpen && <div className="p-3 pt-0">{children}</div>}
    </div>
  );
}

export default Collapsible;