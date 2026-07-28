'use client';

import { useEffect, useState } from 'react';

/**
 * True below the width where the two-pane split stops working.
 *
 * Below ~900px two panes side by side each get a column too narrow to read,
 * and stacking them produces two scroll boxes inside the page scroll — a
 * reader ends up scrolling a small window to follow a long clause. The layout
 * changes shape rather than shrinking: one page scroll, and the contract is a
 * tab away.
 */
export function useIsNarrow(breakpoint = 900): boolean {
  const [narrow, setNarrow] = useState(false);

  useEffect(() => {
    const query = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, [breakpoint]);

  return narrow;
}
