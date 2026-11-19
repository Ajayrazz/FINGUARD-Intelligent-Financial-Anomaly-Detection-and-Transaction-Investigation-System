import { useEffect } from "react";

/** Sets the browser tab title (WCAG 2.4.2 page titled). */
export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · FinGuard`;
  }, [title]);
}
