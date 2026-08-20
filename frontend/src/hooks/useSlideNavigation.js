import { useState, useCallback, useRef } from "react";

export function useSlideNavigation(initialPage = 1, totalPages = 0) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [total, setTotal] = useState(totalPages);
  const pendingRef = useRef(null);

  const goTo = useCallback((n) => {
    const target = Number(n);
    if (!Number.isFinite(target)) return;
    if (!total || total < 1) {
      pendingRef.current = target;
      return;
    }
    setCurrentPage(Math.max(1, Math.min(target, total)));
  }, [total]);

  const setTotalPages = useCallback((nextTotal) => {
    const t = Number(nextTotal) || 0;
    setTotal(t);
    if (t < 1) return;
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending != null) {
      setCurrentPage(Math.max(1, Math.min(pending, t)));
    } else {
      setCurrentPage((prev) => Math.max(1, Math.min(prev, t)));
    }
  }, []);

  return { currentPage, totalPages: total, setTotalPages, goTo };
}
