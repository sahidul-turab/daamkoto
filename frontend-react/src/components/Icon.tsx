import {
  BatteryCharging,
  Box,
  CircuitBoard,
  Cpu,
  Fan,
  HardDrive,
  Headphones,
  Keyboard,
  MemoryStick,
  Monitor,
  MonitorPlay,
  Mouse,
  Power,
  type LucideIcon,
} from "lucide-react";

// Map the icon-name strings used in config.ts / buildConfig.ts to components.
// An unmapped name silently renders a generic Box, so every icon referenced in
// config.ts must be registered here or the category loses its identity in the
// tab bar without anything failing.
const ICONS: Record<string, LucideIcon> = {
  BatteryCharging,
  Box,
  CircuitBoard,
  Cpu,
  Fan,
  HardDrive,
  Headphones,
  Keyboard,
  MemoryStick,
  Monitor,
  MonitorPlay,
  Mouse,
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
