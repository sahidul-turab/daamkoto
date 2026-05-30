import {
  Box,
  CircuitBoard,
  Cpu,
  Fan,
  HardDrive,
  MemoryStick,
  MonitorPlay,
  Power,
  type LucideIcon,
} from "lucide-react";

// Map the icon-name strings used in config.ts / buildConfig.ts to components.
const ICONS: Record<string, LucideIcon> = {
  Box,
  CircuitBoard,
  Cpu,
  Fan,
  HardDrive,
  MemoryStick,
  MonitorPlay,
  Power,
};

export function CategoryIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  const Cmp = ICONS[name] ?? Box;
  return <Cmp className={className} />;
}
