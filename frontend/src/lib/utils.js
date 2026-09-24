import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind classes conditionally without style conflicts.
 * Core helper used across all shadcn/ui components.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
