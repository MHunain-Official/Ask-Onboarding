import { Badge } from "@/components/ui/badge";
import type { UserRole } from "@/lib/types";

const ROLE_LABELS: Record<UserRole, string> = {
  employee: "Employee",
  manager: "Manager",
  admin: "Admin",
};

const ROLE_VARIANTS: Record<UserRole, "secondary" | "outline" | "default"> = {
  employee: "secondary",
  manager: "outline",
  admin: "default",
};

export function RoleBadge({ role }: { role: UserRole }) {
  return <Badge variant={ROLE_VARIANTS[role]}>{ROLE_LABELS[role]}</Badge>;
}
