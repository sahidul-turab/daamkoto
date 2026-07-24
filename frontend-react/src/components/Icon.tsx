import {
  Armchair,
  BatteryCharging,
  Box,
  CircuitBoard,
  Cpu,
  Fan,
  Gamepad2,
  HardDrive,
  Headphones,
  Keyboard,
  MemoryStick,
  Monitor,
  MonitorPlay,
  Mouse,
  Power,
  Printer,
  Speaker,
  Square,
  Webcam,
  type LucideIcon,
} from "lucide-react";

// Map the icon-name strings used in config.ts / buildConfig.ts to components.
// An unmapped name silently renders a generic Box, so every icon referenced in
// config.ts must be registered here or the category loses its identity in the
// tab bar without anything failing.
const ICONS: Record<string, LucideIcon> = {
  Armchair,
  BatteryCharging,
  Box,
  CircuitBoard,
  Cpu,
  Fan,
  Gamepad2,
  HardDrive,
  Headphones,
  Keyboard,
  MemoryStick,
  Monitor,
  MonitorPlay,
  Mouse,
  Power,
  Printer,
  Speaker,
  Square,
  Webcam,
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
