import { useState, useCallback } from "react";

export function useSlideNavigation(initialPage = 1, totalPages = 20) {
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [total, setTotal] = useState(totalPages);

  const goTo = useCallback(
    (n) => {
      const t = total || 20;
      setCurrentPage(Math.max(1, Math.min(n, t)));
    },
    [total]
  );

  return { currentPage, totalPages: total, setTotalPages: setTotal, goTo };
}
