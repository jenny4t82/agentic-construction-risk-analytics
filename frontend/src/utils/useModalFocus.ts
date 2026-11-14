import { useEffect, type RefObject } from 'react';

/** Contain focus and make everything outside the active dialog inert. */
export function useModalFocus(active: boolean, ref: RefObject<HTMLElement | null>, close: () => void) {
  useEffect(() => {
    const dialog = ref.current;
    if (!active || !dialog) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const siblings: { element: HTMLElement; inert: boolean }[] = [];
    let node: HTMLElement = dialog;
    while (node.parentElement) {
      for (const sibling of node.parentElement.children) {
        if (sibling !== node && sibling instanceof HTMLElement && !sibling.hasAttribute('data-modal-backdrop')) {
          siblings.push({ element: sibling, inert: sibling.inert });
          sibling.setAttribute('inert', '');
        }
      }
      node = node.parentElement;
      if (node === document.body) break;
    }
    const candidates = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'button, a[href], input, select, textarea, [tabindex]'
    )).filter(el => el.tabIndex >= 0 && !el.matches(':disabled') && !el.closest('[inert]') && el.getClientRects().length > 0);
    const focusFirst = () => (candidates()[0] ?? dialog).focus();
    const topmostDialog = () => Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]')).at(-1);
    const keydown = (event: KeyboardEvent) => {
      if (topmostDialog() !== dialog) return;
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
      if (event.key === 'Tab') {
        const items = candidates();
        const index = items.indexOf(document.activeElement as HTMLElement);
        event.preventDefault();
        (items[(index + (event.shiftKey ? -1 : 1) + items.length) % items.length] ?? dialog).focus();
      }
    };
    const contain = (event: FocusEvent) => {
      if (topmostDialog() !== dialog) return;
      if (!dialog.contains(event.target as Node)) {
        const focusedDialog = (event.target as HTMLElement | null)?.closest('[role="dialog"][aria-modal="true"]');
        if (focusedDialog && topmostDialog() === focusedDialog) return;
        focusFirst();
      }
    };
    document.addEventListener('keydown', keydown, true);
    document.addEventListener('focusin', contain);
    focusFirst();
    return () => {
      document.removeEventListener('keydown', keydown, true);
      document.removeEventListener('focusin', contain);
      siblings.forEach(({ element, inert }) => { element.inert = inert; });
      if (opener?.isConnected && !opener.closest('[inert]') && opener.getClientRects().length) opener.focus();
    };
  }, [active, ref, close]);
}
