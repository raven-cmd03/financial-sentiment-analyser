import type { ReactNode } from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

interface ThemeProviderProps {
  children: ReactNode;
}

/**
 * Wraps the app in next-themes so every screen gets dark/light toggling,
 * persists the choice in localStorage, and respects `prefers-color-scheme`
 * on first visit.
 */
export default function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      storageKey="fs-theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
